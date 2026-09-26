# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | J97     |
| Repository         | https://github.com/minhdh329/K4-L3B-DAY10-J97-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26               |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Dương Hải Minh | 2A202602680 | Trưởng nhóm / Pipeline Integrator | `src/core/config.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` |
| 2 | Đỗ Trương Thành Ân | 2A202602899 | Data Foundation & Recovery | `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`, raw data snapshot & repair |
| 3 | Mai Hoàng Anh | 2A202602857 | RAG & Vector Index | `src/retrieval/index.py`, `src/retrieval/embeddings.py`, ChromaDB collections |
| 4 | Ngô Minh Thu | 2A202602679 | Observability & Evaluation | `src/observability/quality.py` (GX 1.x), `src/evaluation/testset.py`, Markdown reports |

## 2. Tóm tắt kết quả

**Tóm tắt của nhóm:**
Nhóm J97 đã hoàn thành trọn vẹn Data Pipeline & Data Observability System cho bài báo khoa học từ Crossref REST API. Baseline pipeline đã tự động thu thập 24 bài báo, làm sạch dữ liệu, xây dựng vector index ChromaDB với mô hình `all-MiniLM-L6-v2`, và đánh giá 10 câu hỏi benchmark đạt Retrieval Hit Rate 1.000, Token F1 1.000 và LLM Judge Score 5.00/5.0. 

Khi kích hoạt corruption flow (tiêm 6 kịch bản lỗi: xóa bài mới, làm rỗng summary, tiêm noise ký tự, cắt ngắn title, đẩy lùi ngày công bố), Data Quality Gate (Great Expectations 1.x) lập tức cảnh báo **FAILED** và Freshness SLA bị chuyển sang trạng thái **STALE** (59.09% bài quá 180 ngày). Nếu không dừng pipeline, hệ thống RAG chịu hiện tượng **Silent Failure**: Hit Rate tụt từ 100% xuống 60.0% và Judge Score giảm còn 3.80/5.0 mà không gây crash runtime. 

Thông qua cơ chế **Idempotent Repair** (dựng lại toàn bộ dataset sạch từ raw snapshot bất biến `crossref_records.json` thay vì vá lỗi chắp vá), nhóm đã phục hồi hoàn toàn 100% tất cả các chỉ số chất lượng dữ liệu và RAG evaluation metrics về mức Baseline ban đầu.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref API
    -> raw response/raw records
    -> cleaning và data modeling
    -> embedding + ChromaDB index
    -> evaluation baseline
    -> quality/freshness reports
    -> corruption
    -> re-index và re-evaluate
    -> repair từ dữ liệu nguồn
    -> comparison report
```

### Trách nhiệm của từng khối

| Khối             | Input          | Xử lý chính             | Output/artifact          | Owner          |
| ----------------- | -------------- | -------------------------- | ------------------------ | -------------- |
| Ingestion         | Crossref REST API / Offline Fallback | Fetch, retry/backoff, parse raw JSON | `data/raw/crossref_records.json`, `crossref_response.json` | Đỗ Trương Thành Ân |
| Cleaning          | Raw records, run_date | Schema normalization, calculate `age_days` & `text_for_embedding` | `data/clean/papers_clean.csv`, `papers_clean.json` | Đỗ Trương Thành Ân |
| Embedding/index   | Cleaned DataFrame | Vectorize text với MiniLM, lưu ChromaDB | `data/embeddings/` (collections: baseline, corrupted, repaired) | Mai Hoàng Anh |
| Evaluation        | Cleaned DataFrame, ChromaDB index | Build 10 benchmark QAs, calculate Hit Rate, Token F1, LLM Judge Score | `data/eval/test_set.json`, `data/results/*_metrics.json` | Ngô Minh Thu |
| Observability     | Cleaned DataFrame | Great Expectations 1.x Ephemeral context & Freshness SLA SLA (>180 days) | `data/quality/*_quality_report.json`, `*freshness_report.json` | Ngô Minh Thu |
| Corruption/repair | Baseline clean dataset / Raw snapshot | Inject 6 corruption scenarios & Idempotent re-clean from raw snapshot | `data/clean/*_corrupted.json`, `*_repaired.json`, `corruption_log.json` | Đỗ Trương Thành Ân / Dương Hải Minh |
| Orchestration     | Config & Project Paths | Điều phối luồng Phase 1 và Corruption Flow | `data/reports/phase1_report.md`, `corruption_report.md` | Dương Hải Minh |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình             | Giá trị sử dụng |
| ---------------------------- | ------------------- |
| `LLM_PROVIDER`             | `mock` (hoặc google_genai / openai nếu dùng LLM thực) |
| `LLM_MODEL`                | `mock-judge` |
| Embedding model              | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k`           | 3 |
| Freshness threshold          | 180 days (max stale ratio: 25.0%) |
| Random seed, nếu có        | 42 |

### Lệnh cài đặt

```bash
python -m pip install -e .
```

### Lệnh chạy

Baseline:

```bash
uv run python script/run_phase1.py
```

Hoặc với môi trường `pip` đã kích hoạt:

```bash
python script/run_phase1.py
```

Corruption flow:

```bash
uv run python script/run_corruption_flow.py
```

Hoặc với môi trường `pip` đã kích hoạt:

```bash
python script/run_corruption_flow.py
```

### Kết quả tái hiện

| Lệnh             | Trạng thái                                    | Thời điểm chạy gần nhất | Bằng chứng                         |
| ----------------- | ----------------------------------------------- | ----------------------------- | ------------------------------------ |
| Baseline pipeline | Thành công | 2026-09-26 | `data/reports/phase1_report.md`, exit code 0 |
| Corruption flow   | Thành công | 2026-09-26 | `data/reports/corruption_report.md`, exit code 0 |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính                | Giá trị                             |
| --------------------------- | ------------------------------------- |
| Source                      | Crossref REST API (`https://api.crossref.org/works`) |
| Query/filter                | Query: `agentic retrieval augmented generation large language model`<br>Filter: `from-pub-date:2026-03-30,has-abstract:true` |
| Thời điểm lấy dữ liệu | 2026-09-26 (hoặc local fallback snapshot) |
| Số record nhận được    | 24 |
| Cơ chế retry/backoff      | Exponential backoff retry với urllib3, fallback tự động nạp `crossref_response.json` khi offline/lỗi mạng |

### Raw và clean schema

| Trường        | Kiểu dữ liệu | Bắt buộc?  | Ý nghĩa   | Xử lý khi thiếu/sai |
| --------------- | --------------- | ------------ | ----------- | ---------------------- |
| `paper_id` | string | Có | DOI duy nhất của bài báo | Loại bỏ dòng nếu thiếu |
| `title` | string | Có | Tiêu đề bài báo | Fallback sang "Untitled Paper" nếu rỗng |
| `abstract` | string | Không | Tóm tắt gốc từ Crossref | Xóa thẻ XML/HTML rác |
| `summary` | string | Có | Tóm tắt đã làm sạch | Nếu rỗng, fallback tạo từ title |
| `authors_joined` | string | Có | Danh sách tác giả ghép chuỗi | Fallback "Unknown Author" |
| `categories_joined`| string | Có | Danh mục chủ đề | Fallback "General" |
| `published` | string | Có | Ngày xuất bản (YYYY-MM-DD) | Fallback `run_date` |
| `age_days` | int | Có | Tuổi bài báo tính theo ngày | `(run_date - published).days` |
| `text_for_embedding`| string | Có | Chuỗi tổng hợp dùng cho RAG Index | Ghép từ Title, Summary, Authors, Categories, Published |

### Quy tắc cleaning

| Quy tắc                                 | Quality dimension liên quan | Số record bị tác động | Cách xác minh      |
| ---------------------------------------- | ---------------------------- | -------------------------: | -------------------- |
| Loại bỏ HTML/XML tags trong abstract | Validity / Cleanliness | 24 | Regex strip `<[^>]+>` |
| Xóa khoảng trắng thừa và dòng trống | Cleanliness | 24 | `re.sub(r'\s+', ' ', text)` |
| Ép kiểu định dạng ngày published | Consistency | 24 | ISO format YYYY-MM-DD |
| Tính toán `age_days` | Timeliness | 24 | `(run_date - published).days` |
| Tạo `text_for_embedding` tiêu chuẩn | Completeness / Usability | 24 | Format: `Title: ... | Summary: ... | Authors: ... | Categories: ... | Published: ...` |

## 6. Evaluation setup

| Thành phần                             | Cấu hình thực tế          |
| ---------------------------------------- | ----------------------------- |
| Số câu hỏi                            | 10 |
| Các `question_type`                    | 3 summary, 3 authors, 2 date, 2 categories |
| Ground-truth document ID                 | DOI (`paper_id`) được map chính xác cho từng câu hỏi |
| Embedding model                          | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store/collection                  | ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`) |
| Retrieval `top_k`                       | 3 |
| LLM provider/model                       | `mock-judge` |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` |

**Vì sao test set được giữ nguyên:**
Test set cần được giữ cố định giữa 3 trạng thái (Baseline, Corrupted, Repaired) để đóng vai trò là một **Benchmark chuẩn (Controlled Environment)**. Điều này đảm bảo mọi sự thay đổi trong các chỉ số (Hit Rate, Token F1, Judge Score) hoàn toàn phản ánh tác động của chất lượng dữ liệu (Data Quality) chứ không bị nhiễu bởi sự thay đổi của bộ câu hỏi.

## 7. Kết quả baseline

### Artifact checklist

| Artifact                 | Đường dẫn thực tế                | Trạng thái | Ghi chú   |
| ------------------------ | -------------------------------------- | ------------ | ---------- |
| Raw response/records     | `data/raw/crossref_records.json` | Có | Đầy đủ 24 raw records |
| Cleaned dataset          | `data/clean/papers_clean.json` | Có | Đầy đủ 24 cleaned records |
| Embedding manifest/index | `data/embeddings/` | Có | ChromaDB storage |
| Evaluation set           | `data/eval/test_set.json` | Có | 10 benchmark questions |
| Baseline metrics         | `data/results/baseline_metrics.json` | Có | Hiệu năng baseline |
| Quality/freshness        | `data/quality/baseline_quality_report.json` | Có | Quality Gate PASS |
| Baseline report          | `data/reports/phase1_report.md` | Có | Báo cáo Phase 1 |

### Baseline metrics

| Metric                 |       Giá trị | Diễn giải                             |
| ---------------------- | --------------: | --------------------------------------- |
| `retrieval_hit_rate` |     1.0000 | RAG Agent tìm thấy 100% tài liệu chứa đáp án trong Top 3 |
| `mean_token_f1`      |     1.0000 | Độ khớp từ vựng giữa câu trả lời trích xuất và Ground Truth là tuyệt đối |
| `judge_accuracy`     |     1.0000 | 100% câu trả lời đạt điểm tối đa từ LLM Judge |
| `mean_judge_score`   |     5.00 / 5.0 | Điểm trung bình đánh giá chất lượng câu trả lời là 5.0/5.0 |

## 8. Data quality và freshness

### Quality checks

| Check        | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline      | Bằng chứng |
| ------------ | ----------------- | ------------------ | ----------------------- | ------------ |
| Row count between 5 & 5000 | Completeness | [5, 5000] | PASS (24 records) | `baseline_quality_report.json` |
| Non-null `paper_id` | Completeness | 0% null | PASS | `baseline_quality_report.json` |
| Unique `paper_id` | Uniqueness | 0% duplicate | PASS | `baseline_quality_report.json` |
| Non-null `title` | Completeness | 0% null | PASS | `baseline_quality_report.json` |
| Non-null `text_for_embedding` | Completeness | 0% null | PASS | `baseline_quality_report.json` |
| Min length `summary` >= 30 | Validity | >= 30 chars | PASS | `baseline_quality_report.json` |

### Freshness

| Thuộc tính               | Giá trị                           |
| -------------------------- | ----------------------------------- |
| Freshness được đo tại | Clean DataFrame (`data/clean/papers_clean.json`) |
| Timestamp mới nhất       | `2026-07-22` |
| Ngưỡng freshness         | `age_days > 180` (Max stale ratio <= 25.0%) |
| Trạng thái baseline      | **FRESH (PASSED SLA)** |
| Lý do                     | Chỉ có 1/24 bài báo quá 180 ngày (Tỷ lệ stale = 4.17% < 25.0%) |

## 9. Corruption scenarios và repair

| Corruption         | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair   |
| ------------------ | ---------- | ---------------------: | ------------------------ | --------------------- | -------------- |
| Drop latest records | Xóa 20% bài báo mới nhất | 2 record | Mất thông tin mới | Hit Rate giảm còn 0.60 | Re-ingest từ Raw Snapshot |
| Blank summary | Xóa trắng nội dung `summary` | 3 record | Great Expectations FAIL | Token F1 giảm, thông tin rỗng | Re-clean từ Raw Snapshot |
| Inject noise | Thêm ký tự rác `@@@NOISE@@@` | 3 record | Giảm chất lượng embedding | Câu trả lời bị nhiễu | Re-clean từ Raw Snapshot |
| Duplicate records | Nhân đôi bản ghi | 2 record | Great Expectations Unique FAIL | Trùng lặp kết quả search | Re-clean deduplicate |
| Truncate title | Cắt tiêu đề còn 5 ký tự | 2 record | Giảm độ đối khớp title | Nhầm lẫn tài liệu | Re-clean từ Raw Snapshot |
| Stale date | Đẩy lùi ngày published thêm 365 ngày | 13 record | Freshness SLA STALE | Stale ratio nhảy lên 59.09% | Re-compute `published` & `age_days` |

**Corruption log:**
- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: Log ghi nhận chi tiết và đầy đủ 6 tham số corruption cùng số lượng record bị tác động.

**Cơ chế Repair an toàn:**
Hệ thống thực hiện **Idempotent Repair** bằng cách đọc lại snapshot thô bất biến ban đầu `data/raw/crossref_records.json` và chạy lại toàn bộ quy trình cleaning, feature engineering và indexing. Điều này đảm bảo loại bỏ hoàn toàn các lỗi tiêm vào mà không để lại tác dụng phụ (side-effect) hay phụ thuộc vào trạng thái dữ liệu lỗi trước đó.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal            | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét   |
| ------------------------ | -------: | --------: | -------: | -----------------------: | --------------: | ------------ |
| `retrieval_hit_rate`   |   1.0000 |    0.6000 |   1.0000 |                   -40.0% |            100% | Phục hồi hoàn toàn |
| `mean_token_f1`        |   1.0000 |    0.6741 |   1.0000 |                   -32.6% |            100% | Phục hồi hoàn toàn |
| `judge_accuracy`       |   1.0000 |    0.7000 |   1.0000 |                   -30.0% |            100% | Phục hồi hoàn toàn |
| `mean_judge_score`     |     5.00 |      3.80 |     5.00 |                     -1.20 |            100% | Phục hồi hoàn toàn |
| Quality checks pass/fail |   PASSED |   FAILED 🚨|   PASSED |        Chuyển sang FAILED |            100% | Quality Gate bảo vệ hệ thống |
| Freshness status         |    FRESH |    STALE 🚨|    FRESH |        Stale ratio 59.09% |            100% | SLA trở lại mức 4.17% |

**Hai kết luận có quan hệ nhân quả:**
1. **Data Corruption → Silent Failure:** Việc xóa bài mới và làm rỗng summary làm cho Great Expectations báo **FAILED** và Freshness SLA chuyển sang **STALE** (59.09%). Nếu bỏ qua Quality Gate này, RAG Agent không sập chương trình nhưng cho kết quả sai lệch nghiêm trọng (`retrieval_hit_rate` rơi từ 1.000 xuống 0.600).
2. **Idempotent Repair → Full Recovery:** Quy trình Re-clean và Re-index từ Raw Data Snapshot giúp phục hồi 100% các chỉ số Data Quality Gate (PASS), Freshness SLA (FRESH - 4.17%) và RAG Metrics (`retrieval_hit_rate` = 1.000, `mean_judge_score` = 5.00).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** Khi chạy trên Windows, thư viện Great Expectations đôi khi phát sinh `PermissionError: [WinError 5]` khi cố gắng dọn dẹp thư mục tạm cục bộ (`.ge_store`).
- **Nguyên nhân:** Môi trường Windows khóa tập tin tạm đang được tiến trình Python mở, gây cản trở hàm teardown mặc định của GX Ephemeral Context.
- **Cách xử lý:** Nhóm đã cập nhật hàm `run_data_quality_checks` trong `src/observability/quality.py` để bọc lệnh dọn dẹp trong try-except, đồng thời dựa trực tiếp vào giá trị trả về `validation_result.success` và artifact JSON thay vì phụ thuộc vào việc xóa file tạm của OS.
- **Cách xác minh:** Chạy `python script/run_corruption_flow.py` trên cả macOS và Windows, pipeline đều kết thúc thành công với exit code 0 và sinh đầy đủ báo cáo.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng   | Hướng cải thiện có thể kiểm chứng |
| --------------------- | -------------- | ----------------------------------------- |
| Kích thước dataset nhỏ (24 bài báo) | Chưa kiểm thử hết độ mở rộng của ChromaDB khi dữ liệu đạt hàng triệu dòng | Mở rộng ingest script hỗ trợ pagination và batch processing cho 10,000+ records |
| Mock LLM Judge cho evaluation | Đánh giá câu trả lời dựa trên luật so khớp ngữ nghĩa đơn giản | Tích hợp Google Gemini 1.5 Pro / GPT-4o làm LLM Judge thực tế |
| Ephemeral GX Context chưa lưu trữ dashboard HTML | Thiếu giao diện trực quan cho Data Team theo dõi lịch sử quality trends | Triển khai Great Expectations Data Docs tĩnh tự động export sang HTML artifact |

## 13. Checklist trước khi nộp

- [x] Thông tin nhóm và repository chính xác.
- [x] Phân công khớp với module, artifact và kết quả thực tế.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [x] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
