# Chạy baseline pipeline

Từ thư mục gốc trong PowerShell:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_phase1.py
```

Hoặc gọi trực tiếp:

```python
from core.config import load_settings
from pipelines.phase1 import run_phase1_pipeline

result = run_phase1_pipeline(load_settings())
print(result["metrics"])
print(result["report_path"])
```

Luồng thực thi:

1. **Ingest:** dùng `crossref_records.json` nếu đã có; nếu chỉ có JSON response
   thì bóc tách lại. Khi chưa có snapshot hoặc `REFRESH_SOURCE=true`, gọi API.
   Lỗi kết nối/HTTP có thể dùng snapshot hiện có; lỗi khi không có snapshot
   được trả về cho người chạy.
2. **Clean:** chuẩn hóa, khử trùng lặp, tính lại `age_days` theo thời điểm chạy;
   lưu CSV/JSON sạch.
3. **Quality Gate trước indexing:** chạy GX và freshness. Nếu không đạt, ghi
   báo cáo `BLOCKED`, ném `RuntimeError`, không gọi Chroma hoặc đánh giá.
4. **Index:** MiniLM tạo embedding 384 chiều và lưu collection `papers-baseline`
   trong ChromaDB trên đĩa. Chạy lại sẽ thay thế collection baseline.
5. **Testset:** dùng snapshot 10 câu hợp lệ nếu các DOI còn trong corpus; sinh
   lại khi thiếu/hỏng/sai DOI, vừa tải nguồn mới hoặc `REFRESH_TEST_SET=true`.
6. **Evaluate và báo cáo:** lưu metrics, đáp án từng câu và báo cáo Markdown,
   gồm cả kết quả GX/freshness đã kiểm tra trước indexing.

Báo cáo chính: `data/reports/phase1_report.md`. Các file liên quan:

- `data/clean/papers_clean.csv`, `papers_clean.json`
- `data/chroma/`, `data/embeddings/papers_embeddings.json`
- `data/eval/test_set.json`
- `data/results/baseline_metrics.json`, `baseline_answers.json`
- `data/quality/baseline_quality_report.json`, `freshness_report.json`

Lần đầu cần mạng để tải MiniLM từ Hugging Face. Những lần sau có thể đặt
`HF_HUB_OFFLINE=1` nếu mô hình đã cache và dùng snapshot dữ liệu. Chroma dùng
[PersistentClient](https://docs.trychroma.com/reference/python) để lưu trên đĩa.

Baseline mặc định không cần API key của LLM: câu trả lời được trích xuất từ
metadata và điểm số được tính cục bộ. `RUN_LLM_JUDGE=true` bật judge LLM đã cấu
hình; `RUN_RAGAS=true` bật đánh giá Ragas tùy chọn. Judge mặc định là heuristic
theo Token F1; các điểm judge đó không phải đánh giá độc lập bởi LLM.

Hit Rate phản ánh kết quả truy hồi kết hợp vector search và tra cứu chính xác
theo tiêu đề. Token F1 dùng token tách bởi khoảng trắng, không phân biệt hoa
thường và tính cả số lần xuất hiện. Vì QA hiện trả chuỗi rỗng khi categories
thiếu, hai câu categories có thể đạt F1 bằng 0 dù tìm đúng DOI. Báo cáo nêu
rõ những giới hạn này.

Kiểm thử:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```
