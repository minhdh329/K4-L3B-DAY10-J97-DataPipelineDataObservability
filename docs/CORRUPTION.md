# Giả lập lỗi dữ liệu

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_corruption.py
```

Lệnh đọc `data/clean/papers_clean.json`, gọi
`corrupt_clean_dataframe(clean_df, log_path)` và ghi:

- `data/clean/papers_clean_corrupted.csv`
- `data/clean/papers_clean_corrupted.json`
- `data/results/corruption_log.json`

Hàm làm việc trên bản sao, không thay đổi dữ liệu sạch gốc. Quy tắc chọn dòng
là cố định, không dùng random; cùng input tạo cùng output và log. Input cần ít
nhất 5 dòng, DOI duy nhất, các trường văn bản/ngày/tuổi dữ liệu hợp lệ.

| Sự cố | Quy tắc | Số dòng với snapshot 24 bài |
| --- | --- | ---: |
| drop_latest_records | Xóa 20% dòng mới nhất theo published, hòa ngày thì xếp theo DOI | 5 |
| blank_summary | Xóa trắng summary ở 10% số dòng còn lại | 2 |
| inject_noise | Thêm chuỗi rác vào đầu summary ở nhóm 10% tiếp theo | 2 |
| truncate_title | Cắt title còn tối đa 7 ký tự ở nhóm 10% tiếp theo | 2 |
| stale_date | Lùi published 365 ngày ở 30% số dòng còn lại | 6 |
| duplicate_rows | Sao chép thêm 10% số dòng còn lại, giữ nguyên DOI | 2 |

Các tỷ lệ đều làm tròn lên (`ceil`). Ba nhóm sửa summary/title khác nhau;
nhóm ngày cũ bắt đầu sau ba nhóm đó và có thể quay vòng với input nhỏ.
Số dòng đầu ra là `24 - 5 + 2 = 21`. Dòng trùng sao chép trạng thái đã bị sửa.

Khi lùi ngày, hàm tăng `age_days` thêm 365 để giữ nguyên thời điểm tham chiếu
của snapshot sạch, không phụ thuộc đồng hồ lúc chạy. Đây là lùi 365 ngày so
với ngày xuất bản gốc. Các dòng bị sửa được tính lại `summary_chars` và
`text_for_embedding` để lỗi đi vào dữ liệu dùng cho embedding.

Log chứa `input_rows`, `output_rows`, `parameters`, `counts` và `events`.
Mỗi event có:

- `event_id`, `operation`, `paper_id`.
- `source_position`: vị trí dòng trong input, tính từ 0, không phụ thuộc nhãn index.
- `output_position`: vị trí dòng trong output, hoặc null nếu bị xóa.
- `before`, `after`: toàn bộ bản ghi trước/sau thao tác; after là null khi xóa.

Events theo đúng thứ tự thao tác, nên nếu một dòng chịu nhiều lỗi, before của
thao tác sau khớp after của thao tác trước. Với duplicate_rows, before là dòng
nguồn đã bị sửa và after là bản sao được thêm vào output.

Lệnh này chỉ tạo dữ liệu lỗi và log. Để chạy indexing/evaluation/repair, xem
[luồng corruption và repair](CORRUPTION_FLOW.md).
GX hiện có thể phát hiện summary rỗng và DOI trùng, freshness phát hiện ngày
cũ; noise và title ngắn cần các phép kiểm tra riêng nếu muốn phát hiện bằng GX.

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -p test_corruption.py -v
```
