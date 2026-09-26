# Quality gate với Great Expectations 1.x

`run_data_quality_checks(df, settings, stage)` tạo Ephemeral Context, Pandas
Data Source, DataFrame Asset và whole-dataframe Batch theo
[hướng dẫn GX Core](https://docs.greatexpectations.io/docs/core/connect_to_data/dataframes/).

Bốn loại Expectation được áp dụng với yêu cầu mọi dòng phải đạt:

- Số dòng từ 5 đến 5000, bao gồm hai đầu mút.
- `paper_id`, `title`, `text_for_embedding` không null hoặc chỉ chứa khoảng trắng.
- `paper_id` không trùng lặp.
- `summary` dài ít nhất 30 ký tự. Có thêm kiểm tra not-null cho summary vì
  Expectation độ dài không kiểm định các giá trị null.

`evaluate_freshness_sla()` tính `stale_rows / total_rows`, với dòng cũ là dòng có
`age_days > 180` (ngưỡng ngày lấy từ `settings.freshness_threshold_days`). Đúng
25% vẫn đạt; trên 25% thì `is_fresh=False`. Dữ liệu rỗng hoặc tuổi dữ liệu
thiếu/không hợp lệ cũng không đạt SLA. Hàm dùng `age_days` được tính tại bước
cleaning; cần chạy lại cleaning nếu kiểm định snapshot ở ngày khác.

Kết quả có `success = gx_success and is_fresh`, `freshness`, `results`,
`statistics`, `missing_columns`, `stage` và `checked_at`. Thiếu cột bắt buộc
trả về kết quả thất bại. Dữ liệu đầu vào không bị chỉnh sửa. Báo cáo được lưu
ở `data/quality/<stage>_quality_report.json`.

Chạy kiểm định trên dữ liệu sạch hiện có:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_quality.py
```

Lệnh lưu báo cáo baseline và freshness; exit code là 1 nếu không đạt.
Khi nối vào pipeline trước khi tạo Vector Database, kiểm tra kết quả rõ ràng:

```python
quality = run_data_quality_checks(df, settings, stage="baseline")
if not quality["success"]:
    raise RuntimeError("Quality gate failed; vector indexing stopped.")
index = LocalEmbeddingIndex.build(df, settings)
```

`run_phase1_pipeline(settings)` đã tích hợp điều kiện này trước indexing và
ghi báo cáo `BLOCKED` khi không đạt. Hàm kiểm định riêng không tự gọi indexing.
Xem [hướng dẫn baseline](PHASE1.md). Kiểm thử độc lập bằng:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -p test_quality.py -v
```
