from __future__ import annotations

import json
import logging
from pathlib import Path
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from typing import Any
import urllib.parse

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records, parse_crossref_payload
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def get_diff_records(settings: Settings) -> list[dict[str, Any]]:
    """So sánh từng bản ghi giữa 3 trạng thái: Baseline vs Corrupted vs Repaired."""
    baseline_records: list[dict[str, Any]] = []
    corrupted_records: list[dict[str, Any]] = []
    repaired_records: list[dict[str, Any]] = []

    if settings.paths.clean_json.exists():
        baseline_records = read_json(settings.paths.clean_json)
    if settings.paths.corrupted_clean_json.exists():
        corrupted_records = read_json(settings.paths.corrupted_clean_json)
    if settings.paths.repaired_clean_json.exists():
        repaired_records = read_json(settings.paths.repaired_clean_json)

    base_map = {r["paper_id"]: r for r in baseline_records}
    corr_map = {r["paper_id"]: r for r in corrupted_records}
    rep_map = {r["paper_id"]: r for r in repaired_records}

    # Đếm số lần xuất hiện ở corrupted để phát hiện duplicate
    corr_counts: dict[str, int] = {}
    for r in corrupted_records:
        corr_counts[r["paper_id"]] = corr_counts.get(r["paper_id"], 0) + 1

    all_ids = list(base_map.keys())

    diff_list: list[dict[str, Any]] = []
    for pid in all_ids:
        base = base_map.get(pid, {})
        corr = corr_map.get(pid)
        rep = rep_map.get(pid, {})

        changes: list[str] = []
        status = "unchanged"

        if corr is None:
            status = "dropped"
            changes.append("❌ Bị drop khỏi cơ sở dữ liệu (mất 20% bài mới)")
        else:
            if corr_counts.get(pid, 0) > 1:
                changes.append(f"👥 Bị trùng lặp bản ghi ({corr_counts[pid]} lần xuất hiện)")
                status = "corrupted"

            if len(corr.get("title", "")) < 8 and len(base.get("title", "")) >= 8:
                changes.append("✂️ Tiêu đề bị cắt ngắn < 8 ký tự")
                status = "corrupted"

            if not corr.get("summary", "").strip():
                changes.append("🈳 Tóm tắt bị xóa rỗng hoàn toàn")
                status = "corrupted"
            elif "[NOISE_" in corr.get("summary", ""):
                changes.append("👾 Tóm tắt bị chèn chuỗi ký tự rác vô nghĩa")
                status = "corrupted"

            if corr.get("published") != base.get("published"):
                changes.append(f"⏳ Ngày xuất bản bị lùi: {base.get('published')} -> {corr.get('published')}")
                status = "corrupted"

        is_restored = False
        if rep:
            is_restored = (
                rep.get("title") == base.get("title")
                and rep.get("summary") == base.get("summary")
                and rep.get("published") == base.get("published")
            )

        diff_list.append(
            {
                "paper_id": pid,
                "title": base.get("title", ""),
                "status": status,
                "changes": changes,
                "is_restored": is_restored,
                "baseline": base,
                "corrupted": corr,
                "repaired": rep,
            }
        )

    return diff_list


class DashboardRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, settings: Settings | None = None, **kwargs):
        self.settings = settings or load_settings()
        super().__init__(*args, **kwargs)

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _send_html(self, content: str, status: int = HTTPStatus.OK) -> None:
        payload = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path in {"/", "/index.html"}:
            html_file = TEMPLATES_DIR / "index.html"
            if html_file.exists():
                self._send_html(html_file.read_text(encoding="utf-8"))
            else:
                self._send_html("<h1>Template index.html not found!</h1>", status=HTTPStatus.NOT_FOUND)
            return

        if path == "/api/data":
            baseline_data = (
                read_json(self.settings.paths.clean_json) if self.settings.paths.clean_json.exists() else []
            )
            corrupted_data = (
                read_json(self.settings.paths.corrupted_clean_json)
                if self.settings.paths.corrupted_clean_json.exists()
                else []
            )
            repaired_data = (
                read_json(self.settings.paths.repaired_clean_json)
                if self.settings.paths.repaired_clean_json.exists()
                else []
            )
            corruption_log = (
                read_json(self.settings.paths.corruption_log) if self.settings.paths.corruption_log.exists() else {}
            )

            metrics = {
                "baseline": read_json(self.settings.paths.baseline_metrics)
                if self.settings.paths.baseline_metrics.exists()
                else {},
                "corrupted": read_json(self.settings.paths.corrupted_metrics)
                if self.settings.paths.corrupted_metrics.exists()
                else {},
                "repaired": read_json(self.settings.paths.repaired_metrics)
                if self.settings.paths.repaired_metrics.exists()
                else {},
            }

            quality = {
                "baseline": read_json(self.settings.paths.baseline_quality_report)
                if self.settings.paths.baseline_quality_report.exists()
                else {},
                "corrupted": read_json(self.settings.paths.corrupted_quality_report)
                if self.settings.paths.corrupted_quality_report.exists()
                else {},
                "repaired": read_json(self.settings.paths.quality_dir / "repaired_quality_report.json")
                if (self.settings.paths.quality_dir / "repaired_quality_report.json").exists()
                else {},
            }

            freshness = {
                "baseline": read_json(self.settings.paths.freshness_report)
                if self.settings.paths.freshness_report.exists()
                else {},
                "corrupted": read_json(self.settings.paths.quality_dir / "corrupted_freshness_report.json")
                if (self.settings.paths.quality_dir / "corrupted_freshness_report.json").exists()
                else {},
                "repaired": read_json(self.settings.paths.quality_dir / "repaired_freshness_report.json")
                if (self.settings.paths.quality_dir / "repaired_freshness_report.json").exists()
                else {},
            }

            system_state = "normal"
            if len(repaired_data) > 0:
                system_state = "repaired"
            elif len(corrupted_data) > 0:
                system_state = "corrupted"

            response_data = {
                "system_state": system_state,
                "counts": {
                    "baseline": len(baseline_data),
                    "corrupted": len(corrupted_data),
                    "repaired": len(repaired_data),
                },
                "baseline": baseline_data,
                "corrupted": corrupted_data,
                "repaired": repaired_data,
                "corruption_log": corruption_log,
                "metrics": metrics,
                "quality": quality,
                "freshness": freshness,
            }
            self._send_json(response_data)
            return

        if path == "/api/diff":
            diff_data = get_diff_records(self.settings)
            self._send_json(diff_data)
            return

        self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/action/corrupt":
            try:
                if not self.settings.paths.clean_json.exists():
                    raw_records = fetch_source_records(self.settings)
                    df_clean = build_clean_dataframe(raw_records, now_utc())
                    write_csv(df_clean, self.settings.paths.clean_csv)
                    df_clean.to_json(
                        self.settings.paths.clean_json, orient="records", indent=2, date_format="iso"
                    )
                else:
                    df_clean = pd.read_json(self.settings.paths.clean_json)

                df_corrupted = corrupt_clean_dataframe(df_clean, self.settings.paths.corruption_log)
                write_csv(df_corrupted, self.settings.paths.corrupted_clean_csv)
                df_corrupted.to_json(
                    self.settings.paths.corrupted_clean_json, orient="records", indent=2, date_format="iso"
                )

                LocalEmbeddingIndex.build(
                    df=df_corrupted,
                    settings=self.settings,
                    embeddings_output_path=self.settings.paths.corrupted_embeddings_json,
                )
                q_res = run_data_quality_checks(df_corrupted, self.settings, report_name="corrupted")
                build_freshness_report(
                    df_corrupted,
                    self.settings,
                    self.settings.paths.quality_dir / "corrupted_freshness_report.json",
                )

                log_data = (
                    read_json(self.settings.paths.corruption_log)
                    if self.settings.paths.corruption_log.exists()
                    else {}
                )

                self._send_json(
                    {
                        "success": True,
                        "message": "Đã tiêm 6 kịch bản lỗi thành công vào DataFrame!",
                        "corrupted_count": len(df_corrupted),
                        "gx_success": q_res.get("gx_success"),
                        "is_fresh": q_res.get("is_fresh"),
                        "corruption_log": log_data,
                    }
                )
            except Exception as exc:
                logger.exception("Error during corruption action: %s", exc)
                self._send_json({"success": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        if path == "/api/action/recover":
            try:
                if self.settings.paths.raw_records_json.exists():
                    raw_source = load_raw_records(self.settings.paths.raw_records_json)
                elif self.settings.paths.raw_api_response.exists():
                    raw_payload = read_json(self.settings.paths.raw_api_response)
                    raw_source = parse_crossref_payload(raw_payload)
                else:
                    raw_source = fetch_source_records(self.settings)

                run_date = now_utc()
                df_repaired = build_clean_dataframe(raw_source, run_date)
                write_csv(df_repaired, self.settings.paths.repaired_clean_csv)
                df_repaired.to_json(
                    self.settings.paths.repaired_clean_json, orient="records", indent=2, date_format="iso"
                )

                LocalEmbeddingIndex.build(
                    df=df_repaired,
                    settings=self.settings,
                    embeddings_output_path=self.settings.paths.repaired_embeddings_json,
                )
                q_res = run_data_quality_checks(df_repaired, self.settings, report_name="repaired")
                f_res = build_freshness_report(
                    df_repaired,
                    self.settings,
                    self.settings.paths.quality_dir / "repaired_freshness_report.json",
                )

                base_metrics = (
                    read_json(self.settings.paths.baseline_metrics)
                    if self.settings.paths.baseline_metrics.exists()
                    else {}
                )
                corr_metrics = (
                    read_json(self.settings.paths.corrupted_metrics)
                    if self.settings.paths.corrupted_metrics.exists()
                    else {}
                )
                rep_metrics = (
                    read_json(self.settings.paths.repaired_metrics)
                    if self.settings.paths.repaired_metrics.exists()
                    else base_metrics
                )
                corr_quality = (
                    read_json(self.settings.paths.corrupted_quality_report)
                    if self.settings.paths.corrupted_quality_report.exists()
                    else {}
                )
                corr_fresh = (
                    read_json(self.settings.paths.quality_dir / "corrupted_freshness_report.json")
                    if (self.settings.paths.quality_dir / "corrupted_freshness_report.json").exists()
                    else {}
                )

                generate_corruption_report(
                    report_path=self.settings.paths.comparison_report,
                    baseline_metrics=base_metrics,
                    corrupted_metrics=corr_metrics,
                    repaired_metrics=rep_metrics,
                    corrupted_quality=corr_quality,
                    repaired_quality=q_res,
                    corrupted_freshness=corr_fresh,
                    repaired_freshness=f_res,
                )

                self._send_json(
                    {
                        "success": True,
                        "message": "Cơ chế Idempotent Recovery đã khôi phục 100% dữ liệu sạch từ Raw Snapshot!",
                        "repaired_count": len(df_repaired),
                        "gx_success": q_res.get("gx_success"),
                        "is_fresh": f_res.get("is_fresh"),
                    }
                )
            except Exception as exc:
                logger.exception("Error during recovery action: %s", exc)
                self._send_json({"success": False, "error": str(exc)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
            return

        self._send_json({"error": "Endpoint not found"}, status=HTTPStatus.NOT_FOUND)


def find_free_port(start_port: int = 8080, max_attempts: int = 20) -> int:
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            result = sock.connect_ex(("127.0.0.1", port))
            if result != 0:
                return port
    return start_port


def start_server(host: str = "127.0.0.1", port: int = 8080) -> None:
    settings = load_settings()
    actual_port = find_free_port(port)

    def handler_factory(*args, **kwargs):
        return DashboardRequestHandler(*args, settings=settings, **kwargs)

    server = ThreadingHTTPServer((host, actual_port), handler_factory)
    print(f"\n{'='*70}")
    print(f"🚀 RAG DATA OBSERVABILITY DASHBOARD ĐANG CHẠY")
    print(f"👉 Mở trình duyệt tại: http://localhost:{actual_port}")
    print(f"👉 API endpoint: http://localhost:{actual_port}/api/data")
    print(f"{'='*70}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nĐang tắt dashboard server...")
        server.server_close()


if __name__ == "__main__":
    start_server()

