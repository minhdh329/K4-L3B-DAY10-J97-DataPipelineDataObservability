# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Đỗ Trương Thành Ân             |
| MSSV               | 2A202602899                     |
| Khóa/Lớp         | K4-L3B              |
| Tên nhóm         | J97     |
| Vai trò chính    | Data Foundation & Recovery |
| Repository         | https://github.com/minhdh329/K4-L3B-DAY10-J97-DataPipelineDataObservability/tree/ThanhAn |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Raw Data Ingestion & Data Lineage | `src/ingestion/crossref.py`<br>- `parse_crossref_payload`<br>- `fetch_source_records`<br>- `load_raw_records` | Crossref REST API (hoặc local fallback snapshot `crossref_response.json`) | 2 raw artifacts bảo toàn lineage:<br>- `data/raw/crossref_response.json`<br>- `data/raw/crossref_records.json` (24 bài báo) | Hoàn thành |
| Data Cleaning & Text Modeling | `src/ingestion/cleaning.py`<br>- `build_clean_dataframe` | Danh sách `PaperRecord` từ raw records và thời điểm chạy `run_date` (UTC) | Clean DataFrame chuẩn hóa 24 dòng lưu tại:<br>- `data/clean/papers_clean.csv`<br>- `data/clean/papers_clean.json` (có `text_for_embedding`, `age_days`) | Hoàn thành |
| Idempotent Data Recovery Logic | `src/pipelines/corruption_flow.py` (Step 6)<br>& `src/ingestion/cleaning.py` | Snapshot thô bất biến `data/raw/crossref_records.json` | Tập dữ liệu sạch phục hồi nguyên vẹn:<br>- `data/clean/papers_clean_repaired.csv`<br>- `data/clean/papers_clean_repaired.json` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Hỗ trợ tích hợp schema cho Quality Gate | Observability (`src/observability/quality.py`) | Đảm bảo các trường dữ liệu xuất ra từ `cleaning.py` tương thích hoàn toàn với Great Expectations 1.x suite và công thức Freshness SLA (`age_days > 180`). |
| Kiểm thử tính Idempotent của luồng phục hồi | Pipeline Integrator (`src/pipelines/corruption_flow.py`) | Xác minh quy trình Re-clean và Re-index từ raw data có thể chạy lặp lại nhiều lần mà vẫn tạo ra kết quả đồng nhất với baseline ban đầu. |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Thu thập và bảo toàn dữ liệu Crossref | `src/ingestion/crossref.py`<br>`data/raw/crossref_records.json` | Tải và parse thành công 24 bài báo khoa học, lưu trữ bản snapshot thô bất biến để phục vụ data lineage. | `python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"` in ra 24 bài báo. |
| Làm sạch, tính `age_days` & cấu trúc `text_for_embedding` | `src/ingestion/cleaning.py`<br>`data/clean/papers_clean.csv`<br>`data/clean/papers_clean.json` | Chuẩn hóa loại bỏ JATS XML tag, khử trùng lặp theo `paper_id`, tính `age_days`, tạo `text_for_embedding` 5 phần chuẩn. | `python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"` in ra 24 dòng. |
| Tự phục hồi dữ liệu sạch sau sự cố Data Corruption | `src/pipelines/corruption_flow.py`<br>`data/clean/papers_clean_repaired.csv`<br>`data/results/repaired_metrics.json` | Phục hồi toàn diện 24 bản ghi sạch, đưa Retrieval Hit Rate từ 0.6000 về 1.0000 và Token F1 từ 0.6741 về 1.0000. | Chạy `python script/run_corruption_flow.py` và kiểm tra bảng đối chiếu tại `data/reports/corruption_report.md`. |

**Output cụ thể đại diện:**  
Bộ dữ liệu sạch chuẩn hóa, **Single Source of Truth** :`data/clean/papers_clean.csv` / `papers_clean.json` được lấy từ snapshot thô có sẵn `data/raw/crossref_records.json`. Bộ dữ liệu có tác dụng:

- Cung cấp dữ liệu sạch cho bộ chốt kiểm dịch Great Expectations 1.x
- Nguồn nạp vector store ChromaDB 
- Dữ liệu gốc cho cơ chế tự phục hồi (Idempotent Self-Healing) khi dữ liệu vận hành bị corrupted.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

1. **Dữ liệu thô phân tán và chứa nhiều nhiễu:** Dữ liệu metadata từ Crossref API trả về cấu trúc lồng nhau phức tạp, văn bản tóm tắt chứa các thẻ JATS XML (`<jats:p>`, `<jats:italic>`, v.v.), có nguy cơ trùng lặp DOI và thiếu các trường trọng yếu. Nếu đưa trực tiếp vào embedding model, các thẻ XML và nhiễu ngữ nghĩa sẽ làm sai lệch không gian biểu diễn vector.
2. **Nguy cơ gián đoạn do sự cố mạng/API:** Crossref API công cộng thường xuyên áp dụng rate limiting (HTTP 429) hoặc tạm thời mất kết nối (HTTP 503). Pipeline cần có cơ chế retry thông minh và local fallback snapshot để đảm bảo khả năng tái lập và tự vận hành offline.
3. **Mất dấu nguồn gốc dữ liệu (Data Lineage) khi xảy ra sự cố:** Khi dữ liệu bị nhiễm bẩn (Data Corruption), nếu không lưu trữ bản sao thô ban đầu, hệ thống sẽ không có căn cứ để phục hồi chính xác, dẫn đến hiện tượng sai lệch âm thầm (Silent Failure).

### Cách triển khai

1. **Module Thu thập dữ liệu an toàn (`crossref.py`):**
   - Triển khai hàm `fetch_source_records` tích hợp cơ chế Retry với Exponential Backoff (tối đa 3 lần thử) khi gặp lỗi mã 429 hoặc 503.
   - Tích hợp Fallback cơ động: Nếu mất mạng hoặc API không phản hồi, tự động đọc từ snapshot local `data/raw/crossref_response.json`.
   - Hàm `parse_crossref_payload`: Bóc tách chính xác các trường `DOI`, `title`, `abstract`, `author`, `subject`, và chuyển đổi `published.date-parts` thành chuỗi ISO date (`YYYY-MM-DD`). Loại bỏ toàn bộ các thẻ HTML/JATS XML bằng biểu thức chính quy `re.sub(r"<[^>]+>", " ", text)`.
   - Lưu trữ song song 2 raw artifacts: payload JSON gốc từ API và danh sách `PaperRecord` chuẩn hóa vào `data/raw/crossref_records.json`.

2. **Module Làm sạch & Mô hình hóa tiền Embedding (`cleaning.py`):**
   - **Xử lý sạch văn bản:** Loại bỏ khoảng trắng thừa (`normalize_whitespace`), lọc bỏ các bản ghi không hợp lệ (thiếu `paper_id`, `title` hoặc `summary`).
   - **Khử trùng lặp bản ghi:** Sử dụng `df.drop_duplicates(subset=["paper_id"], keep="first")` để đảm bảo mỗi bài báo là duy nhất theo DOI.
   - **Tính toán Freshness:** Tính `age_days = (run_date.date() - pub_date).days` dựa trên mốc UTC thời gian thực thi, cung cấp dữ liệu số liệu cho việc giám sát Freshness SLA.
   - **Cấu trúc hóa `text_for_embedding`:** Ghép nối văn bản theo định dạng 5 phần rõ ràng:
     ```text
     Title: {title}
     Authors: {authors_joined}
     Published: {published_clean}
     Categories: {categories_joined}
     Summary: {summary}
     ```
     Thiết kế này giúp mô hình embedding `all-MiniLM-L6-v2` học được ngữ nghĩa toàn diện bao gồm cả tiêu đề, tác giả, lĩnh vực và nội dung tóm tắt.

3. **Cơ chế Tự phục hồi an toàn (Idempotent Recovery):**
   - Trong `src/pipelines/corruption_flow.py` (Step 6), luồng phục hồi không can thiệp sửa chữa chắp vá trên DataFrame đã bị lỗi mà thực hiện đọc lại từ bản lưu trữ thô bất biến `data/raw/crossref_records.json`.
   - Tái thực thi toàn bộ logic `build_clean_dataframe` với `run_date` chuẩn, ghi đè ra `papers_clean_repaired.csv/json`, sau đó tái xây dựng lại vector index `papers-repaired`. Nhờ đó, quy trình đạt tính chất **Idempotent** (chạy lại n lần vẫn cho cùng 1 kết quả sạch hoàn hảo).

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Payload JSON từ Crossref REST API (hoặc `crossref_response.json`) và tham số `Settings` |
| Output                         | `PaperRecord` dataclass, `data/raw/crossref_records.json`, `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` (24 dòng sạch) |
| Module phụ thuộc             | `core.config.Settings`, `core.utils` (`normalize_whitespace`, `read_json`, `write_json`) |
| Module sử dụng output        | `src/observability/quality.py` (Great Expectations 1.x), `src/retrieval/index.py` (ChromaDB), `src/evaluation/testset.py` |
| Điều kiện lỗi cần xử lý | API rate limit (429), mất kết nối mạng, abstract chứa thẻ JATS XML, ngày xuất bản khuyết thiếu ngày/tháng, bản ghi bị trùng DOI |

### Cách xác minh

```bash
# 1. Kiểm tra Ingestion và Ingestion Fallback
.venv/bin/python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"

# 2. Kiểm tra Data Cleaning và cấu trúc trường
.venv/bin/python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng'); print('Cột:', list(df.columns))"

# 3. Chạy luồng kiểm chứng phục hồi toàn diện
.venv/bin/python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** Tải đủ 24 bài báo; làm sạch ra đúng 24 dòng không trùng lặp, có đủ cột `text_for_embedding` và `age_days`; luồng phục hồi khôi phục 100% hiệu năng so với baseline.
- **Kết quả thực tế:**
  - `Tín hiệu hoàn thành: Đã tải 24 bài báo`
  - `Tín hiệu hoàn thành: Clean thành công 24 dòng`
  - Bảng đối chiếu console và `data/reports/corruption_report.md` xác nhận phục hồi toàn bộ chỉ số về 1.0000.
- **Artifact/log:**
  - `data/raw/crossref_records.json`
  - `data/clean/papers_clean.csv` và `data/clean/papers_clean.json`
  - `data/clean/papers_clean_repaired.csv` và `data/clean/papers_clean_repaired.json`
  - `data/reports/corruption_report.md`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Thiết kế chuỗi văn bản đầu vào cho mô hình vector embedding (`text_for_embedding`) trong file `src/ingestion/cleaning.py`.
- **Các phương án đã cân nhắc:**
  - *Phương án 1 (Minimalist):* Chỉ nhúng duy nhất trường `summary` (tóm tắt nội dung bài báo).
  - *Phương án 2 (Multi-attribute Structured):* Ghép nối có cấu trúc 5 thành phần thông tin metadata: `Title`, `Authors`, `Published`, `Categories`, `Summary`.
- **Phương án đã chọn:** Phương án 2 (Multi-attribute Structured).
- **Lý do:**
  - Nếu chỉ nhúng trường `summary`, không gian vector sẽ hoàn toàn thiếu hụt thông tin về tác giả (`authors`), chủ đề (`categories`), và thời gian công bố (`published`). Khi người dùng hoặc RAG Agent đặt các câu hỏi truy vấn tìm kiếm theo tên nhà khoa học hoặc phân loại bài báo, vector retrieval sẽ bị trượt mục tiêu (Retrieval Miss).
  - Bằng cách định dạng rõ ràng các tiền tố khóa (`Title: ...`, `Authors: ...`), mô hình ngôn ngữ nhỏ `all-MiniLM-L6-v2` có thể phân tách các vùng chú ý ngữ nghĩa (semantic attention) tốt hơn, tăng cường độ chính xác cho cả tìm kiếm tổng quát lẫn tra cứu chi tiết.
- **Bằng chứng quyết định phù hợp:**
  - Trên tập benchmark 10 câu hỏi của `src/evaluation/testset.py` (bao phủ đủ 4 nhóm: `summary`, `authors`, `date`, `categories`), hệ thống đạt **Retrieval Hit Rate = 1.0000 (100%)** và **Mean Token F1 = 1.0000** ở pha Baseline và Repaired. Không có bất kỳ câu hỏi nào bị trượt ngữ cảnh liên quan đến tác giả hay danh mục.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:**
  ```text
  requests.exceptions.ConnectionError: HTTPSConnectionPool(host='api.crossref.org', port=443): Max retries exceeded with url: /works?query=...
  (hoặc ConnectError: [Errno 8] nodename nor servname provided, or not known)
  ```
- **Lệnh hoặc bước tái hiện:** Chạy hàm `fetch_source_records` trong môi trường sandbox cô lập mạng hoặc khi kết nối internet chập chờn, gặp sự cố DNS.
- **Nguyên nhân gốc:** Hàm Ingestion ban đầu phụ thuộc trực tiếp vào network call ra ngoài internet. Khi mạng bị ngắt hoặc Crossref API bị chặn/quá tải, hàm ném ngoại lệ chưa xử lý, làm sập toàn bộ pipeline ngay từ Checkpoint 0 và không thể thực thi các bước làm sạch hay phục hồi dữ liệu tiếp theo.
- **Cách xử lý:**
  1. Thêm khối `try-except` xung quanh request gọi API Crossref với logic thử lại (retry) tối đa 3 lần kèm lũy thừa thời gian chờ (exponential backoff: 1s, 2s, 4s).
  2. Xây dựng cơ chế **Offline Fallback Snapshot**: Nếu cả 3 lần thử đều thất bại, hàm sẽ tự động kiểm tra sự tồn tại của file snapshot thô lưu trữ sẵn `data/raw/crossref_response.json`. Nếu có snapshot, nạp dữ liệu từ snapshot này và ghi nhận log thông báo thay vì ngắt chương trình.
- **Cách xác minh sau khi sửa:** Chạy kiểm thử hàm `fetch_source_records(settings)` khi ngắt kết nối mạng: pipeline lập tức chuyển sang snapshot fallback, phân tích cú pháp thành công 24 bài báo và xuất ra `data/raw/crossref_records.json` với exit code 0.
- **Điều học được:** Trong kỹ nghệ dữ liệu cho production, mọi pipeline thu thập dữ liệu từ bên thứ ba (3rd-party APIs) đều phải được thiết kế theo nguyên lý **Defensive Ingestion** (ingestion phòng vệ): có rate limit handling, timeout hợp lý và bản lưu trữ snapshot để đảm bảo hệ thống có thể chạy độc lập, kiểm thử cục bộ và tự phục hồi khi có sự cố mạng.

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**  
   Dữ liệu thô JSON từ Crossref API được tải về qua `src/ingestion/crossref.py` và lưu trữ nguyên trạng vào `data/raw/`. Hàm `parse_crossref_payload` bóc tách các trường, loại bỏ thẻ JATS XML thành các `PaperRecord`. Tiếp theo, `src/ingestion/cleaning.py` lọc bỏ bản ghi lỗi, khử trùng lặp theo `paper_id`, tính `age_days` và ghép chuỗi 5 phần `text_for_embedding`, lưu ra `data/clean/papers_clean.csv/json`. Dữ liệu sạch này được nạp vào `src/retrieval/index.py`, sử dụng mô hình `all-MiniLM-L6-v2` để sinh vector embeddings (384 chiều) và lưu trữ bền vững vào ChromaDB collection `papers-baseline`.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**  
   File `data/eval/test_set.json` gồm 10 câu hỏi chuẩn hóa qua 4 nhóm nghiệp vụ (`summary`, `authors`, `date`, `categories`). Mỗi câu hỏi đều gắn kèm `ground_truth_doc_ids` (ID bài báo chứa câu trả lời chuẩn) và `ground_truth_answer`. Khi đánh giá:
   - **Retrieval Hit Rate:** Kiểm tra xem `ground_truth_doc_ids` có nằm trong danh sách Top-K tài liệu mà ChromaDB trả về hay không.
   - **Mean Token F1:** So sánh sự trùng khớp từ vựng giữa câu trả lời mà RAG Agent trích xuất được với `ground_truth_answer`.
   - **LLM Judge:** Dùng mô hình ngôn ngữ lớn đánh giá độ chính xác về mặt ngữ nghĩa (thang điểm 1–5 và Correct boolean).

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**  
   - **Quality checks (Great Expectations 1.x):** Kiểm tra tính toàn vẹn và cấu trúc tĩnh của tập dữ liệu (Schema & Data Integrity) như số dòng tối thiểu (`ExpectTableRowCountToBeBetween`), không chứa giá trị Null ở các cột quan trọng (`ExpectColumnValuesToNotBeNull`), tính duy nhất của ID (`ExpectColumnValuesToBeUnique`), và độ dài tối thiểu của tóm tắt (`ExpectColumnValueLengthsToBeBetween >= 30`).
   - **Freshness monitoring (SLA Monitor):** Kiểm tra tính kịp thời và độ tươi mới động của dữ liệu theo trục thời gian (Timeliness & Data Drift). Đo lường tỷ lệ các bài báo có `age_days > 180` ngày so với thời điểm chạy và kích hoạt cảnh báo vi phạm SLA nếu tỷ lệ này vượt quá 25%.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**  
   Đây là nguyên tắc vàng trong thực nghiệm khoa học (Controlled Experiment). Việc giữ nguyên vẹn 10 câu hỏi benchmark và ground truth đóng vai trò là biến số độc lập cố định. Khi đó, sự thay đổi về điểm số (`retrieval_hit_rate`, `token_f1`, `judge_score`) phản ánh chính xác và khách quan 100% tác động của chất lượng dữ liệu (Data Quality) ở 3 trạng thái, loại trừ hoàn toàn sự thiên lệch do độ khó hay sự khác biệt giữa các câu hỏi đánh giá.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**  
   Quá trình Repair được công nhận thành công khi thỏa mãn đồng thời 2 nhóm tiêu chí:
   - **Nhóm Observability & Data Artifacts:** Tập dữ liệu sạch `data/clean/papers_clean_repaired.csv/json` được tạo mới từ raw data; báo cáo chất lượng `repaired_quality_report.json` đạt `gx_success = True`; báo cáo độ tươi `repaired_freshness_report.json` đạt `is_fresh = True` (stale ratio trở về 4.17% < 25%).
   - **Nhóm Agent Performance Metrics:** Trong `data/results/repaired_metrics.json`, chỉ số `retrieval_hit_rate` được khôi phục từ 0.6000 lên 1.0000 (100%), `mean_token_f1` khôi phục từ 0.6741 lên 1.0000, và `judge_accuracy` khôi phục từ 0.7000 lên 1.0000, hoàn toàn tương đương với trạng thái Baseline ban đầu.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |   1.0000 |    0.6000 |   1.0000 | Tụt giảm nghiêm trọng 40% trên dữ liệu lỗi do bị drop 20% bài mới; sau repair từ raw snapshot đã khôi phục hoàn hảo 100%. |
| `mean_token_f1`      |   1.0000 |    0.6741 |   1.0000 | Suy giảm mạnh do abstract bị xóa rỗng hoặc chèn ký tự nhiễu rác; sau repair đã lấy lại độ chính xác từ vựng tối đa. |
| `judge_accuracy`     |   1.0000 |    0.7000 |   1.0000 | LLM Judge đánh giá 30% câu trả lời bị sai lệch hoặc rỗng trên dữ liệu bẩn; sau repair tỷ lệ trả lời đúng đạt 100%. |
| `mean_judge_score`   |     5.00 |      3.80 |     5.00 | Điểm chất lượng trung bình giảm sâu xuống 3.8/5.0 và được phục hồi về điểm tuyệt đối 5.0/5.0. |
| Quality checks (GX)    |   PASSED | FAILED 🚨 | PASSED ✅ | Great Expectations 1.x phát hiện chính xác vi phạm độ dài summary và trùng lặp ID trên tập corrupted; đạt chuẩn trên tập repaired. |
| Freshness status       |    FRESH |  STALE 🚨 |  FRESH ✅ | Tỷ lệ bài quá hạn 180 ngày vọt lên 59.09% trên tập lỗi (vượt ngưỡng 25%); sau repair trở về 4.17%, đạt chuẩn SLA. |

### Kết luận từ số liệu

**Hai chuỗi nguyên nhân – bằng chứng thực tế:**
1. **Chuỗi sụt giảm (Data Corruption Impact):**  
   Dữ liệu bị tiêm 6 kịch bản lỗi (Drop latest records, Blank summary, Inject noise, Truncate title, Stale date, Duplicate rows) → Quality Gate báo `gx_success = False` (vi phạm Expectation độ dài tóm tắt và trùng lặp ID), Freshness SLA báo `is_fresh = False` (tỷ lệ bài cũ vọt lên 59.09%) → RAG Agent bị suy giảm hiệu năng nghiêm trọng: `retrieval_hit_rate` sụp đổ từ 1.0000 xuống 0.6000, `mean_token_f1` giảm từ 1.0000 xuống 0.6741 và `judge_accuracy` giảm xuống 0.7000.
2. **Chuỗi tự phục hồi (Idempotent Recovery Impact):**  
   Kích hoạt luồng phục hồi dữ liệu từ bản snapshot thô bất biến `data/raw/crossref_records.json`, chạy lại pipeline `build_clean_dataframe` và tái tạo vector index → Quality Gate đạt `gx_success = True`, Freshness SLA trở lại trạng thái `FRESH` (tỷ lệ bài cũ giảm còn 4.17%) → Toàn bộ chỉ số Agent (`retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy`, `mean_judge_score`) phục hồi 100% về mức tuyệt đối ban đầu.

**Dạng corruption ảnh hưởng rõ nhất và lý do:**  
- Hai dạng lỗi gây tác động tàn phá lớn nhất là **Drop latest records** và **Blank summary / Inject noise**:
  - *Drop latest records (mất 20% bản ghi mới nhất):* Làm biến mất trực tiếp tài liệu mục tiêu trong cơ sở dữ liệu. Ngay cả khi thuật toán vector search hoạt động hoàn hảo, hệ thống vẫn không thể tìm ra tài liệu không tồn tại, khiến `retrieval_hit_rate` lập tức tụt mất 40%.
  - *Blank summary & Inject noise:* Phá hủy vector biểu diễn ngữ nghĩa. Khi đoạn tóm tắt bị rỗng hoặc lẫn chuỗi ký tự rác vô nghĩa, khoảng cách cosine giữa câu hỏi và tài liệu bị đẩy ra xa, dẫn tới việc vector retrieval trả về các tài liệu sai lệch, kéo theo `token_f1` giảm sút nặng nề.

**Hiện tượng khác biệt với kỳ vọng ban đầu:**  
- Ban đầu tôi giả định rằng khi dữ liệu bị xóa rỗng summary hoặc trùng lặp ID, mã nguồn RAG Agent hoặc vector database sẽ gặp ngoại lệ runtime (Crash/Exception). Tuy nhiên, trên thực tế toàn bộ hệ thống vẫn chạy bình thường với mã thoát `exit code 0`, nhưng âm thầm trả về câu trả lời sai lệch hoặc câu "I don't know".
- Đây chính là minh chứng kinh điển cho hiện tượng **Silent Failure** trong các hệ thống AI/RAG: Lỗi dữ liệu không làm sập phần mềm mà âm thầm làm giảm sút chất lượng và độ tin cậy của mô hình mà người vận hành không hề hay biết nếu không có hệ thống Data Observability chốt chặn.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về Data Pipeline & Data Lineage:**  
   Bản lưu trữ thô (Raw Data Snapshot) là tài sản tối quan trọng của mọi kỹ sư dữ liệu. Việc giữ nguyên vẹn dữ liệu gốc ban đầu và xây dựng pipeline biến đổi theo nguyên tắc bất biến (Immutability) là điều kiện tiên quyết để thực hiện cơ chế tự phục hồi an toàn (Idempotent Repair) khi môi trường sản xuất gặp sự cố.
2. **Về Data Quality & Observability:**  
   Không thể chỉ dựa vào unit test mã nguồn để đảm bảo chất lượng hệ thống RAG. Phải thiết lập Data Quality Gate (như Great Expectations 1.x) kết hợp với giám sát độ tươi mới (Freshness SLA) như một chốt kiểm dịch tự động trước khi dữ liệu được nạp vào vector store.
3. **Về ảnh hưởng của Data đến RAG Agent:**  
   "Garbage In, Silent Garbage Out" — chất lượng của mô hình RAG phụ thuộc trực tiếp vào chất lượng dữ liệu nền tảng. Khi dữ liệu bị nhiễm bẩn, mô hình sẽ gặp hiện tượng Silent Failure. Do đó, việc quan sát dữ liệu (Data Observability) có vai trò sống còn tương đương với việc đánh giá mô hình (Model Evaluation).

### Nếu có thêm thời gian

Nếu có thêm thời gian phát triển, tôi sẽ xây dựng **Cơ chế Tự động Ngắt mạch & Tự phục hồi thời gian thực (Automated Circuit Breaker & Auto-Healing):**
- **Mô tả:** Tích hợp Quality Gate vào pipeline streaming hoặc cron job. Ngay khi Great Expectations hoặc Freshness SLA phát hiện vi phạm (ví dụ `is_fresh = False` hoặc `gx_success = False`), hệ thống sẽ lập tức kích hoạt Circuit Breaker, tạm ngưng phục vụ collection bị lỗi, cô lập dữ liệu vào vùng cách ly (Quarantine Zone), và tự động kích hoạt tiến trình phục hồi dữ liệu từ bản snapshot raw gần nhất mà không cần con người can thiệp thủ công.
- **Cách đo lường cải thiện:** Đo lường chỉ số **MTTR (Mean Time To Recovery)** — rút ngắn thời gian phát hiện và khôi phục từ vài chục phút can thiệp thủ công xuống dưới 5 giây tự động hoàn toàn.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đỗ Trương Thành Ân  
**Ngày xác nhận:** 2026-09-26  
