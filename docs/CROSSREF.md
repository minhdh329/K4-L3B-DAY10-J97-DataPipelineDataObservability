# Thu thập metadata Crossref

Chạy riêng bước ingestion từ thư mục gốc (PowerShell, dùng môi trường đã cài dependencies):

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_ingestion.py
```

Lệnh gọi API công khai, không cần khóa API hoặc LLM. Query, filter và số lượng lấy từ
`load_settings()` trong `src/core/config.py`; mặc định tối đa 24 kết quả.
Mỗi lần chạy thành công thay thế hai snapshot:

- `data/raw/crossref_response.json`: toàn bộ nội dung JSON của HTTP response,
  lưu trực tiếp bằng `response.content`, không định dạng lại hoặc loại trường.
- `data/raw/crossref_records.json`: danh sách `PaperRecord` được bóc tách từ response đó.
  `load_raw_records(path)` đọc lại snapshot này để chạy offline.

Quy tắc chuẩn hóa:

- `paper_id`: DOI viết thường, bỏ tiền tố URL DOI hoặc `doi:`.
- `title`, `summary`: bỏ thẻ HTML/JATS, giải mã HTML entities và gộp khoảng trắng;
  giữ ranh giới giữa các đoạn văn.
- `authors`: ghép tên và họ; hỗ trợ tác giả tổ chức qua trường `name`.
- `categories`: lấy từ `subject`, bỏ mục rỗng và trùng lặp; không có thì để `[]`.
- `published`: ưu tiên `published`, `published-online`, `published-print`, rồi `issued`.
  Xuất `YYYY-MM-DD`; thiếu tháng/ngày thì quy ước là `01`. Ngày thiếu hoặc sai để `""`.
  Không dùng ngày tạo metadata thay cho ngày xuất bản.
- Bỏ bản ghi không có DOI hợp lệ hoặc tiêu đề. Các trường tùy chọn thiếu giữ rỗng.
  `pdf_url` chỉ được điền khi nguồn có link với kiểu `application/pdf`.

Giữ các trường bổ sung của `PaperRecord` để tương thích pipeline hiện có:
`primary_category`, `updated` (ngày deposited, nếu không có thì published),
`abs_url`, `pdf_url`, `comment`.

Request có timeout và tối đa 3 lần retry, xử lý 429/5xx tạm thời và `Retry-After`.
Một lần lấy hỗ trợ 1–1000 kết quả để giữ một response nguyên bản trong một file;
không gộp nhiều trang thành JSON giả lập. Tham khảo
[tài liệu REST API Crossref](https://www.crossref.org/documentation/retrieve-metadata/rest-api/tips-for-using-the-crossref-rest-api/).

Chạy kiểm thử:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

## Làm sạch dữ liệu

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_cleaning.py
```

Lệnh đọc `crossref_records.json`, tạo `data/clean/papers_clean.csv` và
`data/clean/papers_clean.json`. Hai file raw được giữ nguyên.

`build_clean_dataframe(records, run_date)` gộp khoảng trắng thừa, chuẩn hóa DOI
thành chữ thường, làm sạch danh sách tác giả/lĩnh vực và giữ bản ghi hợp lệ đầu
tiên cho mỗi DOI. Bản ghi thiếu DOI, tiêu đề hoặc ngày xuất bản hợp lệ bị loại.
Các trường tùy chọn như summary và categories có thể rỗng.

Ngày xuất bản được hiểu là 00:00 UTC; `run_date` được quy về UTC (nếu không có
múi giờ thì hiểu là UTC). `age_days = (run_date - published).days`, giữ cả giá trị
âm khi ngày xuất bản nằm trong tương lai. Kết quả sắp xếp theo ngày xuất bản
giảm dần, rồi DOI tăng dần. `text_for_embedding` có đúng năm dòng:

```text
Title: <title>
Authors: <authors_joined>
Published: <published>
Categories: <categories_joined>
Summary: <summary>
```

Tác giả và lĩnh vực được nối bằng dấu phẩy. Dataframe còn có `summary_chars`
để phục vụ bước kiểm tra chất lượng.
