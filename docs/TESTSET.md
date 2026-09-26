# Bộ câu hỏi Ground Truth

Chạy từ thư mục gốc sau khi đã tạo dữ liệu sạch:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_testset.py
```

`build_test_set(df, output_path)` tạo đúng 10 câu hỏi trong
`data/eval/test_set.json`, có ID từ `eval_001` đến `eval_010`:

| Dạng | Số câu | Ground truth |
| --- | ---: | --- |
| summary | 3 | Câu đầu của summary, dùng helper `first_sentence` |
| authors | 3 | Danh sách tác giả nối bằng dấu phẩy |
| date | 2 | Ngày xuất bản dạng `YYYY-MM-DD` |
| categories | 2 | Danh sách lĩnh vực nối bằng dấu phẩy |

10 không chia hết cho 4 nên phân bổ 3–3–2–2. Câu hỏi được tạo luân phiên theo
dạng, chọn DOI theo thứ tự ổn định và ưu tiên bài chưa được sử dụng. Không lặp
cặp `(question_type, paper_id)`. Với dữ liệu hiện tại, 10 câu tham chiếu 10 DOI
khác nhau. Mỗi câu có đúng các trường `id`, `question_type`, `question`,
`ground_truth`, `ground_truth_doc_ids`.

Hàm yêu cầu ít nhất 3 bài khác DOI có tiêu đề và đủ metadata cho từng dạng:
3 bài có summary, 3 bài có authors, 2 bài có ngày hợp lệ. Hỗ trợ cả cột
`authors_joined`/`categories_joined` lẫn danh sách `authors`/`categories`.
Input không đủ sẽ báo `ValueError` trước khi ghi file. DataFrame nguồn không
bị sửa và file raw/clean được giữ nguyên.

Snapshot Crossref hiện tại thiếu categories ở toàn bộ 24 bài. Vì vậy, hai câu
categories hỏi về lĩnh vực **được ghi trong metadata nguồn** và có ground truth
`Not provided in source metadata.`. Đây là kiểm tra nhận biết thiếu thông tin,
không phải nhãn chuyên môn suy đoán. Nếu có ít nhất hai bài chứa categories,
hàm ưu tiên dùng metadata có thật cho cả hai câu.

Lưu ý khi đánh giá: `retrieval/qa.py` hiện trả chuỗi rỗng nếu categories rỗng;
hai câu nhận biết thiếu thông tin sẽ cần câu trả lời phù hợp để được điểm.
Helper tách câu dùng dấu `.`, `!`, `?` theo sau bởi khoảng trắng; đây là quy tắc
đơn giản, có thể tách sớm ở các chữ viết tắt.

Kiểm thử riêng bước tạo bộ câu hỏi:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -p test_testset.py -v
```
