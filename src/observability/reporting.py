from __future__ import annotations

from typing import Any

from core.utils import write_text


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write baseline metrics, provenance, and quality/freshness decisions."""
    passed = bool(quality.get("success"))
    lines = [
        "# Phase 1 — Baseline RAG report", "",
        f"Status: **{'COMPLETED' if passed and metrics else 'BLOCKED'}**", "",
        "## Source and run", "",
        "| Field | Value |", "| --- | --- |",
        *[f"| {_cell(key)} | {_cell(value)} |" for key, value in source_summary.items()],
        "", "## Baseline metrics", "",
    ]
    if metrics:
        lines.extend([
            "| Metric | Value |", "| --- | ---: |",
            f"| Questions | {metrics['samples']} |",
            f"| Retrieval Hit Rate | {metrics['retrieval_hit_rate']:.2%} |",
            f"| Mean Token F1 | {metrics['mean_token_f1']:.4f} |",
            "", "Hit Rate is the proportion of questions whose expected DOI occurs in retrieved results.",
            "Token F1 uses case-insensitive whitespace tokens and counts repeated tokens.",
            "Answers use metadata extraction. Retrieval combines Chroma vector search with exact-title lookup;",
            "this score is not a vector-search-only benchmark or a generative LLM benchmark.",
            "Missing categories can reduce F1 when the reference expects an explicit absence answer.",
            "", f"LLM judge enabled: {metrics.get('llm_judge_enabled', False)}.",
            f"Ragas: {_cell(metrics.get('ragas', {}))}",
        ])
    else:
        lines.append("Evaluation was not run. The quality gate blocked indexing; any older metric files are not results of this run.")
    statistics = quality.get("statistics", {})
    lines.extend([
        "", "## Great Expectations quality gate", "",
        f"- Overall gate: **{'PASS' if passed else 'FAIL'}**",
        f"- GX expectations: {statistics.get('successful_expectations', 0)}/{statistics.get('evaluated_expectations', 0)} passed",
        f"- Missing required columns: {_cell(quality.get('missing_columns', []))}",
        "- Gate runs before creating or replacing the Chroma collection.",
        "", "## Freshness SLA", "",
        f"- Fresh: **{freshness['is_fresh']}**",
        f"- Stale rows: {freshness['stale_rows']}/{freshness['total_rows']} ({freshness['stale_ratio']:.2%})",
        f"- Stale threshold: age_days > {freshness['threshold_days']}",
        f"- Maximum stale ratio: {freshness['max_stale_ratio']:.0%}",
        f"- Invalid ages: {freshness['invalid_age_rows']}",
        f"- Publication range: {freshness.get('oldest_published')} to {freshness.get('latest_published')}",
        "", "## Artifacts", "",
        "- [Raw API response](../raw/crossref_response.json)",
        "- [Raw records](../raw/crossref_records.json)",
        "- [Clean CSV](../clean/papers_clean.csv) / [Clean JSON](../clean/papers_clean.json)",
        "- [GX quality report](../quality/baseline_quality_report.json)",
        "- [Freshness report](../quality/freshness_report.json)",
    ])
    if metrics:
        lines.extend([
            "- [Chroma database](../chroma/) / [Embedding manifest](../embeddings/papers_embeddings.json)",
            "- [Ground truth](../eval/test_set.json)",
            "- [Baseline metrics](../results/baseline_metrics.json)",
            "- [Per-question answers](../results/baseline_answers.json)",
        ])
    write_text(report_path, "\n".join(lines) + "\n")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    *,
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    """Report measured changes without assuming corruption must lower every metric."""
    metrics = [baseline_metrics, corrupted_metrics, repaired_metrics]
    quality = [baseline_quality or {}, corrupted_quality, repaired_quality]
    freshness = [baseline_freshness or {}, corrupted_freshness, repaired_freshness]

    def row(label, values):
        return f"| {label} | " + " | ".join(_cell(value) for value in values) + " |"

    lines = [
        "# Corruption and repair — comparison report", "",
        "All states use the same raw snapshot, run date, embedding model and Ground Truth.",
        "The baseline was measured again for this experiment; old metric files were not reused.",
        "", "## Three-state comparison", "",
        "| Metric | Baseline | Corrupted | Repaired |", "| --- | ---: | ---: | ---: |",
        row("Rows", [item.get("total_rows", "N/A") for item in freshness]),
        row("Questions", [item["samples"] for item in metrics]),
        row("Retrieval Hit Rate", [f"{item['retrieval_hit_rate']:.2%}" for item in metrics]),
        row("Mean Token F1", [f"{item['mean_token_f1']:.4f}" for item in metrics]),
        row("Quality gate", ["PASS" if item.get("success") else "FAIL" if item else "N/A" for item in quality]),
        row("Freshness SLA", ["PASS" if item.get("is_fresh") else "FAIL" if item else "N/A" for item in freshness]),
        row("Stale ratio", [f"{item['stale_ratio']:.2%}" if item else "N/A" for item in freshness]),
        "", "## Measured degradation and recovery", "",
    ]
    for key, label in (("retrieval_hit_rate", "Hit Rate"), ("mean_token_f1", "Token F1")):
        base, bad, fixed = (item[key] for item in metrics)
        lines.append(f"- {label}: corrupted minus baseline = {bad - base:+.4f}; "
                     f"repaired minus corrupted = {fixed - bad:+.4f}; repaired minus baseline = {fixed - base:+.4f}.")
    degraded = any(corrupted_metrics[key] < baseline_metrics[key]
                   for key in ("retrieval_hit_rate", "mean_token_f1"))
    lines.extend([
        "", "## Silent Failure", "",
        "Corrupted indexing and evaluation completed without a runtime error. "
        + ("Answer/retrieval metrics declined." if degraded else "The measured metrics did not decline in this run."),
        "The experiment deliberately bypassed the failed quality gate for corrupted data; "
        "the normal baseline and repair paths still enforce it.",
        "See the corruption log and failed GX expectations for data faults even when a retrieval metric stays high.",
        "", "## Safe repair", "",
        "Repair reads only the original raw snapshot, recomputes clean rows and freshness, and requires a passing quality gate.",
        "Chroma replacement builds a full staging collection before switching names, with rollback on rename failure.",
        "The working clean CSV/JSON and baseline Chroma collection are restored. "
        "Corrupted and repaired collections/artifacts remain separate comparison evidence.",
        "Rebuilding replaces old record IDs instead of appending, removing duplicate and obsolete vectors. "
        "This is a single-process workflow, not a transaction spanning all JSON/CSV files and Chroma.",
        "", "## Interpretation", "",
        "Retrieval combines Chroma vector search and exact-title lookup. Answers are extracted from metadata; "
        "these results do not measure a generative LLM alone.",
        "Two category questions may remain incorrect after repair because source metadata lacks categories.",
        "", "## Artifacts", "",
        "- [Corruption log](../results/corruption_log.json)",
        "- [Baseline metrics](../results/baseline_metrics.json) / [answers](../results/baseline_answers.json)",
        "- [Corrupted metrics](../results/corrupted_metrics.json) / [answers](../results/corrupted_answers.json)",
        "- [Repaired metrics](../results/repaired_metrics.json) / [answers](../results/repaired_answers.json)",
        "- [Corrupted data](../clean/papers_clean_corrupted.json) / [repaired data](../clean/papers_clean_repaired.json)",
        "- [Corrupted GX](../quality/corrupted_quality_report.json) / [repaired GX](../quality/repaired_quality_report.json)",
        "- [Corrupted freshness](../quality/corrupted_freshness_report.json) / [repaired freshness](../quality/repaired_freshness_report.json)",
    ])
    write_text(report_path, "\n".join(lines) + "\n")
