# Corruption → đánh giá → repair

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe script/run_corruption_flow.py
```

`run_corruption_flow_pipeline(settings)` chạy hoàn toàn từ raw snapshot local,
không gọi Crossref hoặc thay đổi raw. Nếu chỉ có `crossref_response.json`, hàm
bóc tách response đó trong bộ nhớ. Không có raw thì dừng với `FileNotFoundError`.
MiniLM phải được tải lần đầu hoặc có sẵn trong cache.

1. Dựng lại baseline từ raw với một `run_date` cố định, chạy GX/freshness và đo
   lại baseline để tránh so sánh với metrics cũ.
2. Giữ nguyên testset hiện có. Nếu chưa có, sinh một lần từ baseline. Testset
   không hợp lệ sẽ gây lỗi trước khi làm bẩn; không tự thay Ground Truth giữa
   ba trạng thái, kể cả khi các cờ refresh đang bật.
3. Tiêm sáu lỗi, lưu corrupted CSV/JSON và log; ghi kết quả GX/freshness.
4. Trong **thử nghiệm này**, cố ý bỏ qua chốt chặn cho dữ liệu bẩn. Lưu index
   `papers-corrupted` làm bằng chứng và thay cả collection đang dùng
   `papers-baseline` cùng clean CSV/JSON bằng dữ liệu bẩn. Đánh giá trên cùng
   testset để quan sát Silent Failure.
5. Trong `finally`, gọi `repair_from_raw_snapshot(settings, run_date)`, nên
   repair vẫn được thử ngay cả khi corrupted indexing/evaluation ném lỗi.
6. Đánh giá bản repaired và ghi `data/reports/corruption_report.md`.

## Phục hồi

`repair_from_raw_snapshot()` trả về `RepairResult` gồm dataframe, index,
quality và freshness. Hàm không đọc dữ liệu sạch/bẩn làm nguồn phục hồi.
Nó đọc lại raw, chạy cleaning, rồi bắt buộc GX/freshness đạt trước khi thay thế
dữ liệu làm việc. Snapshot quá cũ hoặc không đạt chất lượng sẽ không được ép
thành PASS.

Khi đạt, hàm lưu collection/artifacts `repaired` riêng và ghi đè collection
`papers-baseline`, clean CSV/JSON đang dùng. Collection `papers-corrupted`,
corrupted CSV/JSON, metrics và log được giữ để đối chiếu. Ba tên collection
phải khác nhau.

Chroma được thay thế bằng collection staging: tính embedding và thêm đủ
records trước khi chạm vào index cũ, kiểm tra số lượng, đổi tên index cũ
thành backup rồi đổi staging thành tên chính. Nếu bước đổi tên staging lỗi,
khôi phục tên index cũ. Sau thành công mới xóa backup. Cách dựng lại toàn bộ
loại bỏ record IDs cũ và vector trùng/không còn trong raw. API đổi tên dùng
[`collection.modify(name=...)`](https://github.com/chroma-core/docs/blob/main/docs/usage-guide.md).

Với cùng snapshot và run_date, chạy repair nhiều lần cho cùng nội dung và số
DOI; không append thêm vectors. `age_days` sẽ thay đổi hợp lý nếu chạy ở ngày
khác. Đây là workflow một tiến trình; việc ghi nhiều CSV/JSON và Chroma không
phải một giao dịch nguyên tử xuyên tất cả artifacts.

## Kết quả và cách đọc

Báo cáo so sánh số dòng, số câu hỏi, Hit Rate, Token F1, GX và freshness; có
delta corrupted–baseline, repaired–corrupted và repaired–baseline. Các phép
đo được ghi như thực tế, không ép chỉ số corrupted phải giảm.

Baseline này trả lời bằng trích xuất metadata, dùng vector search kết hợp
tra cứu tiêu đề. Dữ liệu nguồn thiếu categories nên F1 sau repair có thể quay
về 0,8 chứ không phải 1,0. LLM judge/Ragas vẫn là bước tùy chọn như Phase 1.

Các artifact chính:

- `data/results/{baseline,corrupted,repaired}_metrics.json`
- `data/results/{baseline,corrupted,repaired}_answers.json`
- `data/clean/papers_clean{,_corrupted,_repaired}.json` và CSV tương ứng
- `data/embeddings/papers_embeddings{,_corrupted,_repaired}.json`
- `data/quality/{baseline,corrupted,repaired}_quality_report.json`
- `data/quality/{corrupted,repaired}_freshness_report.json`
- `data/reports/corruption_report.md`

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```
