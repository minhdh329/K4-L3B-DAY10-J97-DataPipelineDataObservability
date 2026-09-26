# Member Role Report — Day 10: Data Pipeline & Data Observability

> Báo cáo cá nhân của Dương Hải Minh, tập trung vào vai trò trưởng nhóm và phần orchestration/integration của pipeline.

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Dương Hải Minh |
| MSSV | 2A202602680 |
| Khóa/Lớp | K4 |
| Tên nhóm | J97 |
| Vai trò chính | Trưởng nhóm |
| Repository | K4-L3B-DAY10-J97-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Cấu hình và tiện ích pipeline | `src/core/config.py`, `src/core/utils.py` | Biến môi trường, project paths | `Settings`, đường dẫn artifact, helper đọc/ghi | Hoàn thành |
| Baseline orchestration | `src/pipelines/phase1.py`, `script/run_phase1.py` | Raw records và settings | Clean dataset, Chroma index, metrics, quality reports, `data/reports/phase1_report.md` | Hoàn thành |
| Corruption/repair orchestration | `src/pipelines/corruption_flow.py`, `script/run_corruption_flow.py` | Baseline artifacts và raw snapshot | Corrupted/repaired artifacts, metrics và `corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Debug tích hợp kiểu dữ liệu giữa pandas và ChromaDB | `retrieval/index.py` | Chuyển `published` từ `Timestamp` sang chuỗi để index chạy được |
| Kiểm tra liên module | ingestion, evaluation, observability, retrieval | Chạy end-to-end baseline và corruption flow bằng Python 3.13 |
| Tái tạo artifact và đối chiếu số liệu | Toàn bộ pipeline | Xác nhận 24 clean rows, 10 evaluation questions và kết quả 3 trạng thái |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Nối baseline pipeline | `src/pipelines/phase1.py` | 24 clean rows, Chroma collection `papers-baseline`, baseline metrics | `script/run_phase1.py` exit code 0 |
| Nối corruption và repair flow | `src/pipelines/corruption_flow.py` | Corrupted/repaired metrics và comparison report | `script/run_corruption_flow.py` exit code 0 |
| Chuẩn hóa artifact và report output | `src/core/config.py`, `src/core/utils.py`, `src/observability/reporting.py` | Các file CSV/JSON/Markdown được ghi đúng thư mục | Kiểm tra tồn tại artifact trong `data/` |

Output cụ thể: baseline có `retrieval_hit_rate = 1.000`; corrupted giảm còn `0.500`; repaired phục hồi về `1.000`. Quality status tương ứng là `True`, `False`, `True`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Pipeline cần chạy được từ raw data đến vector index, evaluation và quality report, sau đó phải tái sử dụng cùng test set để đo ảnh hưởng của corruption và khả năng repair. Vai trò orchestration đảm bảo các module chạy đúng thứ tự và artifact của bước trước là input hợp lệ cho bước sau.

### Cách triển khai

`phase1.py` load settings, chọn raw snapshot hoặc fetch source, clean dữ liệu, ghi CSV/JSON, build Chroma baseline, tạo hoặc dùng benchmark test set, evaluation, quality/freshness check và report. `corruption_flow.py` đọc clean artifact, tạo corrupted dataset, re-index và evaluate, sau đó dựng repaired dataset trực tiếp từ `data/raw/crossref_records.json` thay vì sửa ngược trên dữ liệu bẩn. Cuối cùng flow ghi metrics và báo cáo so sánh ba trạng thái.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | `Settings`, `data/raw/crossref_records.json`, clean dataset, `test_set.json`, baseline metrics |
| Output | `data/clean/`, `data/embeddings/`, `data/results/`, `data/quality/`, `data/reports/` |
| Module phụ thuộc | ingestion, retrieval, evaluation, observability, `core.utils` |
| Module sử dụng output | Chroma index, evaluation, quality checks và comparison report |
| Điều kiện lỗi cần xử lý | Thiếu raw/clean artifact, API fallback, metadata không phải kiểu Chroma hỗ trợ, quality failure do duplicate/summary rỗng |

### Cách xác minh

```powershell
$env:PYTHONPATH="src"
.\.venv313\Scripts\python.exe script\run_phase1.py
.\.venv313\Scripts\python.exe script\run_corruption_flow.py
```

- **Kết quả mong đợi:** Hai script exit code 0 và tạo đủ artifact baseline/corrupted/repaired.
- **Kết quả thực tế:** Baseline hoàn thành với 24 clean rows; corruption flow hoàn thành với hit rate `1.000 / 0.500 / 1.000`.
- **Artifact/log:** `data/results/*_metrics.json`, `data/results/corruption_log.json`, `data/reports/phase1_report.md`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Khi dữ liệu đã bị corruption, cần chọn cách phục hồi để kết quả không chỉ là che lỗi trên DataFrame bẩn.
- **Các phương án đã cân nhắc:** (1) sửa trực tiếp các dòng bị lỗi theo corruption log; (2) dựng lại clean DataFrame từ raw snapshot đáng tin cậy.
- **Phương án đã chọn:** Dùng phương án (2), gọi `load_raw_records` rồi `build_clean_dataframe` để tạo repaired dataset mới.
- **Lý do:** Raw snapshot là lineage anchor, giúp repair reproducible và tránh giữ lại các biến đổi không mong muốn. Đổi lại, cách này cần chạy lại cleaning và embedding.
- **Bằng chứng quyết định phù hợp:** Repaired quality là `True`, số dòng trở lại 24 và retrieval hit rate phục hồi từ `0.500` lên `1.000`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** `ValueError: Expected metadata value to be a str, int, float, bool, SparseVector, list, or None, got 2026-09-15 00:00:00 which is a Timestamp in add.`
- **Lệnh hoặc bước tái hiện:** Chạy `script/run_phase1.py` khi build Chroma index.
- **Nguyên nhân gốc:** `published` được pandas đọc thành `Timestamp`, trong khi Chroma metadata chỉ nhận primitive value hoặc list.
- **Cách xử lý:** Chuẩn hóa `published` thành `str(row["published"])` trong `LocalEmbeddingIndex._build_documents`.
- **Cách xác minh sau khi sửa:** Chạy lại baseline và corruption flow; cả hai exit code 0, Chroma index và metrics được tạo.
- **Điều học được:** Contract kiểu dữ liệu cần được kiểm tra tại ranh giới giữa DataFrame và hệ thống lưu trữ bên ngoài, không chỉ ở bước cleaning.

## 7. Hiểu biết về luồng end-to-end

1. Crossref API hoặc raw snapshot được parse thành `PaperRecord`, sau đó cleaning tạo `text_for_embedding`; embedding model `all-MiniLM-L6-v2` biến các text này thành vector và Chroma lưu vector cùng metadata.
2. Evaluation set gồm 10 câu hỏi thuộc `summary`, `authors`, `date`, `categories`. Mỗi câu có `ground_truth_doc_ids`; retrieval hit được tính khi một ID đích xuất hiện trong các document được retrieve, còn token F1/judge đánh giá chất lượng câu trả lời so với ground truth.
3. Quality checks kiểm tra tính hợp lệ hiện tại của schema và dữ liệu như row count, not-null, uniqueness và độ dài summary. Freshness monitoring đo tuổi dữ liệu qua `age_days`, đếm dòng quá 180 ngày và kiểm tra stale ratio không vượt 25%.
4. Cùng một test set bắt buộc được giữ nguyên để thay đổi metric phản ánh sự thay đổi của dữ liệu/index, không phải do câu hỏi hoặc ground truth khác nhau.
5. Repair thành công khi raw-derived dataset trở lại 24 dòng, quality pass, freshness pass, artifact repaired được ghi đầy đủ và metric retrieval phục hồi về baseline.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.000 | 0.500 | 1.000 | Corruption làm mất hoặc làm sai tài liệu truy hồi; repair phục hồi hoàn toàn trong lần chạy này. |
| `mean_token_f1` | 0.207 | 0.141 | 0.207 | Giảm khoảng 0.067 khi bẩn và trở lại đúng mức baseline. |
| `judge_accuracy` | 0.200 | 0.200 | 0.200 | Không thay đổi; judge fallback/LLM chưa phân biệt được ba trạng thái ở metric này. |
| `mean_judge_score` | 1.400 | 1.400 | 1.400 | Không thay đổi, nên không dùng metric này làm bằng chứng chính của recovery. |
| Quality checks | True | False | True | Corrupted fail do duplicate `paper_id` và summary rỗng; repaired pass. |
| Freshness status | True | True | True | Corrupted có 2/21 stale rows, ratio 9.52%, vẫn dưới ngưỡng 25%. |

### Kết luận từ số liệu

1. Drop records, blank summary và duplicate rows → quality giảm từ `True` xuống `False`, corrupted còn 21 dòng và có 4 duplicate violations → retrieval hit rate giảm từ `1.000` xuống `0.500`.
2. Rebuild từ raw snapshot → quality trở lại `True`, 24 dòng unique và freshness `True` → retrieval hit rate và token F1 trở lại đúng mức baseline.

Corruption ảnh hưởng rõ nhất theo quality signal là `blank_summary` kết hợp `duplicate_rows`: quality report ghi 4 summary ngắn và 4 unexpected duplicate values. Theo agent metric, tác động tổng hợp của việc drop/mutate/duplicate làm hit rate mất 50 điểm phần trăm.

Kết quả khác kỳ vọng là freshness vẫn `True` ở corrupted dù có stale dates, vì chỉ có 2/21 dòng stale, tương đương 9.52%, thấp hơn ngưỡng 25%. `judge_accuracy` và `mean_judge_score` cũng không đổi; đây là giới hạn của fallback judge/evaluation hiện tại, không phải bằng chứng rằng corruption không ảnh hưởng.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Orchestration phải quản lý rõ contract giữa raw, clean, vector index và evaluation artifact; một lỗi kiểu dữ liệu ở ranh giới Chroma có thể làm dừng toàn pipeline.
2. Quality gate giúp phát hiện lỗi cấu trúc như duplicate ID và summary rỗng trước khi dữ liệu được phục vụ, còn freshness cần một SLA riêng vì dataset có thể vẫn hợp lệ nhưng đã cũ.
3. RAG agent phụ thuộc trực tiếp vào chất lượng và đầy đủ của corpus: dữ liệu bẩn làm retrieval hit rate và token F1 giảm dù pipeline không nhất thiết crash.

### Nếu có thêm thời gian

Mình sẽ thêm pytest cho từng stage và một lệnh CI chạy cả baseline/corruption flow, đồng thời cải thiện judge để phân biệt rõ các trạng thái. Chỉ số đo gồm exit code, coverage, quality pass rate và độ chênh giữa baseline/corrupted/repaired metrics.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Dương Hải Minh
**Ngày xác nhận:** 2026-09-26
