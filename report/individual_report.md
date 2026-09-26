# Member Role Report — Day 10: Data Pipeline & Data Observability

> Báo cáo cá nhân của Ngô Minh Thu, tập trung vào vai trò Data Observability, benchmark evaluation và reporting của pipeline.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Ngô Minh Thu |
| MSSV | 2A202602679 |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | J97 |
| Vai trò chính | Observability & Evaluation |
| Repository | `K4-L3B-DAY10-J97-DataPipelineDataObservability` |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Quality Gate và Freshness SLA | `src/observability/quality.py` | Clean DataFrame | Quality/freshness reports cho baseline, corrupted, repaired | Hoàn thành |
| Benchmark test set | `src/evaluation/testset.py` | Clean DataFrame 24 bài báo | `data/eval/test_set.json` gồm 10 câu hỏi | Hoàn thành |
| Reporting | `src/observability/reporting.py` | Metrics, quality và freshness artifacts | `phase1_report.md`, `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Kiểm tra tích hợp | `phase1.py`, `corruption_flow.py` | Mình xác nhận ba trạng thái dùng cùng test set và số liệu report khớp JSON artifacts. |
| Kiểm tra contract | Cleaning, retrieval, corruption | Mình kiểm tra các cột `paper_id`, `summary`, `text_for_embedding`, `age_days` được giữ đúng giữa các bước. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Chạy Quality Gate GX 1.x | `quality.py`, `data/quality/` | Baseline/repaired PASS, corrupted FAIL | `run_data_quality_checks(...)` |
| Theo dõi freshness | Freshness reports | Fresh 4.17% → Stale 33.33% → Fresh 4.17% | `corruption_report.md` |
| Sinh benchmark | `testset.py`, `test_set.json` | 10 câu: 3 summary, 3 authors, 2 date, 2 categories | `build_test_set(...)` trả về 10 items |
| Tổng hợp evidence | `reporting.py`, Markdown reports | Có bảng so sánh metrics và quality signals | Chạy hai script pipeline |

Output cụ thể: `corruption_report.md` ghi nhận retrieval hit rate giảm từ `1.000` xuống `0.600` sau corruption và phục hồi về `1.000` sau repair. Quality Gate đổi từ PASS sang FAIL rồi PASS.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

RAG vẫn có thể chạy khi dữ liệu bị thiếu, trùng, rỗng hoặc cũ, nhưng chất lượng câu trả lời giảm âm thầm. Phần việc của mình là tạo quality signal trước indexing và dùng một benchmark cố định để đo tác động của dữ liệu lỗi.

### Cách triển khai

Mình dùng Great Expectations 1.x với Ephemeral Context để kiểm tra DataFrame: số dòng từ 5 đến 5000, các cột `paper_id`, `title`, `text_for_embedding` không null, `paper_id` không trùng và `summary` dài ít nhất 30 ký tự.

Freshness được tính từ tỷ lệ record có `age_days > 180`. Nếu tỷ lệ vượt 25%, dataset được gắn cờ `is_fresh=False`.

Mình tạo test set bằng cách sort theo `paper_id` để kết quả ổn định giữa các lần chạy. Mỗi câu có DOI ground truth; DOI này được dùng để tính retrieval hit rate, còn ground truth text dùng cho Token F1 và judge score.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame có `paper_id`, `title`, `summary`, `authors_joined`, `categories_joined`, `published`, `age_days`, `text_for_embedding` |
| Output | Quality dict có `success`, `checks`, `freshness`; test set JSON có `id`, `question_type`, `question`, `ground_truth`, `ground_truth_doc_ids` |
| Module phụ thuộc | `ingestion/cleaning.py`, `core/config.py` |
| Module sử dụng output | `phase1.py`, `corruption_flow.py`, evaluation và reporting |
| Điều kiện lỗi | Thiếu cột bắt buộc, ít hơn 10 documents, DOI trùng, summary rỗng hoặc stale ratio vượt SLA |

### Cách xác minh

```powershell
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); print(run_data_quality_checks(pd.read_json(s.paths.clean_json), s, 'test')['success'])"
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); print(len(build_test_set(pd.read_json(s.paths.clean_json), s.paths.eval_testset)))"
```

- **Kết quả mong đợi:** Quality check trả về `True`; test set có 10 câu.
- **Kết quả thực tế:** Baseline trả về `True`; corrupted trả về `False`; repaired trở lại `True`.
- **Artifact/log:** `data/quality/`, `data/eval/test_set.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Quality Gate cần chạy được trên máy các thành viên mà không phụ thuộc GX server hay state cục bộ.
- **Các phương án:** Dùng persistent context hoặc Ephemeral Context.
- **Phương án đã chọn:** Ephemeral Context với pandas datasource và whole-dataframe batch.
- **Lý do:** Phù hợp với DataFrame in-memory, dễ tái lập và không làm lẫn state giữa baseline, corrupted, repaired.
- **Bằng chứng:** Baseline/repaired PASS; corrupted FAIL do summary rỗng, DOI trùng và freshness Stale 33.33%.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** Great Expectations đôi khi in `PermissionError: [WinError 5]` khi dọn temporary directory trên Windows.
- **Cách tái hiện:** Chạy `python script/run_phase1.py` hoặc `python script/run_corruption_flow.py`.
- **Nguyên nhân:** Warning ở bước dọn thư mục tạm của GX/Windows, không phải validation failure.
- **Cách xử lý:** Mình xác minh bằng exit code, trường `success` trong JSON và artifact được sinh ra thay vì chỉ nhìn warning console.
- **Kết quả:** Hai pipeline exit code 0 và sinh đủ metrics/report.

## 7. Hiểu biết về luồng end-to-end

Crossref được lưu ở raw layer, cleaning tạo `text_for_embedding` và `age_days`, MiniLM tạo vector và ChromaDB lưu vector cùng metadata. Test set giữ DOI ground truth để đo retrieval hit và chất lượng câu trả lời. Khi repair, pipeline không vá trực tiếp dữ liệu lỗi mà dựng lại clean dataset từ raw snapshot, index lại và đánh giá lại.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của mình |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.600 | 1.000 | Corpus lỗi làm mất 0.400; repair phục hồi hoàn toàn. |
| `mean_token_f1` | 1.000 | 0.774 | 1.000 | Summary rỗng/noise và document bị mất làm câu trả lời lệch ground truth. |
| `judge_accuracy` | 1.000 | 0.800 | 1.000 | Chất lượng câu trả lời giảm rồi hồi phục sau repair. |
| `mean_judge_score` | 5.000 | 4.000 | 5.000 | Judge score giảm một điểm ở corrupted state. |
| Quality checks | PASS | FAIL | PASS | Gate bắt được summary rỗng và DOI duplicate. |
| Freshness status | Fresh 4.17% | Stale 33.33% | Fresh 4.17% | Stale-date scenario làm tỷ lệ stale vượt SLA. |

Kết quả cho thấy sáu corruption scenario làm quality/freshness signal xấu đi và metrics retrieval/answer cùng giảm. Khi dựng lại từ `data/raw/crossref_records.json`, dataset trở về 24 dòng sạch, quality/freshness trở lại PASS/Fresh và metrics quay về baseline.

Suite hiện đo tác động tổng hợp của sáu lỗi; chưa có artifact tách riêng mức ảnh hưởng của từng lỗi. Baseline đạt 1.0 vì benchmark có title/DOI rõ ràng và logic trả lời thiên về trích xuất metadata, nên benchmark này chưa phản ánh đầy đủ tình huống hỏi mở thực tế.

## 9. Điều học được và hướng cải thiện

1. Raw artifact là nền tảng của repair đáng tin cậy; không có raw lineage thì không thể khôi phục record bị drop một cách chắc chắn.
2. Schema đúng chưa đủ; dữ liệu cũ vẫn làm RAG giảm chất lượng nên cần freshness monitoring riêng.
3. Muốn chứng minh silent failure, cần nối quality signal với retrieval/answer metrics, không chỉ kiểm tra pipeline có chạy hay không.

Nếu có thêm thời gian, mình sẽ thêm câu hỏi paraphrase không chứa nguyên title và chạy riêng từng corruption scenario. Cách này giúp benchmark gần tình huống thực tế hơn và đo rõ tác động của từng lỗi.

## 10. Cam kết của thành viên

- [x] Báo cáo phản ánh phần việc và kết quả mình đã kiểm tra.
- [x] Mình có thể giải thích luồng end-to-end của pipeline.
- [x] Các kết luận đều có metric hoặc artifact để đối chiếu.
- [x] Báo cáo không chứa API key, token hoặc secret.

**Họ và tên:** Ngô Minh Thu

**Ngày xác nhận:** 2026-09-26
