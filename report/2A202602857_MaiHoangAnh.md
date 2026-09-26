# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                  |
| ------------------ | -------------------------- |
| Họ và tên       | Mai Hoàng Anh            |
| MSSV               | 2A202602857                    |
| Khóa/Lớp         | K4            |
| Tên nhóm         | J97     |
| Vai trò chính    | RAG & Vector Index (ChromaDB, Retrieval) |
| Repository         | https://github.com/minhdh329/K4-L3B-DAY10-J97-DataPipelineDataObservability.git |
| Ngày hoàn thành | 2026-09-26               |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao  | Trạng thái                                 |
| ------------------ | --------------------- | ---------------- | ----------------- | -------------------------------------------- |
| Vector Index Storage | `src/retrieval/index.py` (`LocalEmbeddingIndex`, `build`, `search`, `lookup`) | Cleaned DataFrame | Thư mục `data/embeddings/` chứa ChromaDB collection | Hoàn thành |
| Embeddings Model | `src/retrieval/embeddings.py` (`MiniLMEmbeddings`, `@lru_cache` loader) | Raw Text | Float Vectors List | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động                         | Thành viên/module được hỗ trợ | Kết quả                    |
| ------------------------------------ | ------------------------------------ | ---------------------------- |
| Tích hợp Agent Tools | Module `src/retrieval/agent.py` | Tạo hai tool `semantic_search_papers` và `lookup_paper` sử dụng instance của `LocalEmbeddingIndex`, giúp LLM tìm kiếm dễ dàng |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao       | Cách xác minh         |
| --------------------------- | ----------------------------- | ------------------------- | ----------------------- |
| Xây dựng logic indexing | `src/retrieval/index.py` | Thư mục database ChromaDB (`data/embeddings/`) | Chạy thử `ls data/embeddings` |
| Tích hợp và cache model embeddings | `src/retrieval/embeddings.py` | Tốc độ load embeddings model giảm đáng kể | Chạy script `script/run_phase1.py` |

Nêu một output cụ thể mà phần việc của bạn tạo ra hoặc giúp xác minh:

Phần việc tạo ra trực tiếp artifacts chứa local ChromaDB index tại `data/embeddings/`, hỗ trợ vector search và exact text lookup để RAG agent làm ngữ cảnh trả lời câu hỏi.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Chuyển đổi dữ liệu văn bản đã được làm sạch (`text_for_embedding`) thành vector không gian (embeddings) và lưu trữ chúng vào hệ thống Vector Database (ChromaDB) để thực hiện tìm kiếm ngữ nghĩa nhanh chóng cho Agent, cung cấp context khi trả lời.

### Cách triển khai

- **Embeddings:** Sử dụng `SentenceTransformer` gói trong class `MiniLMEmbeddings` (kế thừa từ `Embeddings` của LangChain). Áp dụng caching `@lru_cache` để tối ưu tải model.
- **Vector Store:** Cấu hình `chromadb.PersistentClient` tại `data/embeddings`. 
- **Bảo mật dữ liệu (Safe Indexing):** Để quá trình cập nhật (re-index) không gây hỏng collection cũ khi có lỗi giữa chừng, tôi triển khai cơ chế Staging Collection: tạo một bảng lưu trữ tạm (tên random uuid `staging-***`), nạp dữ liệu xong mới tiến hành swap tên với collection chính thông qua hàm `.modify(name=...)`, đồng thời backup dữ liệu cũ. Điều này giúp pipeline mạnh mẽ hơn với data corruption.

### Input, output và contract

| Thành phần                   | Mô tả                                     |
| ------------------------------ | ------------------------------------------- |
| Input                          | Pandas DataFrame chứa dữ liệu sạch (cột `text_for_embedding`, `paper_id`, `title`) |
| Output                         | Thư mục Persistent ChromaDB tại `data/embeddings/` và JSON manifest |
| Module phụ thuộc             | pipeline clean data (để lấy dataframe), `SentenceTransformer` model |
| Module sử dụng output        | `src/retrieval/agent.py` sử dụng hàm `search` và `lookup` |
| Điều kiện lỗi cần xử lý | Lỗi count mismatch khi index (xóa bảng staging ngay nếu lỗi), Document không tồn tại khi lookup exact |

### Cách xác minh

```bash
uv run python script/run_phase1.py
```

- **Kết quả mong đợi:** Pipeline chạy thành công, báo cáo tạo thành công `LocalEmbeddingIndex` và lưu file json manifest.
- **Kết quả thực tế:** Pipeline chạy hoàn tất, sinh ra `data/embeddings/baseline_metrics.json` (hoặc `embeddings.json` tuỳ môi trường) và thư mục lưu persist db.
- **Artifact/log:** `data/embeddings/`

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cần xử lý kịch bản dữ liệu mới đổ về và phải tạo lại hoặc đè index cũ (nhất là trong pipeline chạy định kỳ).
- **Các phương án đã cân nhắc:** (1) Xoá collection cũ và index lại từ đầu. (2) Index vào một collection phụ (staging collection), sau khi kiểm tra số lượng khớp (`collection.count() == len(documents)`), mới thực hiện đổi tên (swap) thành collection chính.
- **Phương án đã chọn:** Phương án 2 (Staging collection & Swap).
- **Lý do:** Trade-off về việc mất thêm một chút thao tác và complexity trong code đổi lại tính Data Quality và Reproducibility rất cao: nếu một pipeline bị đứt đoạn hoặc văng Exception, Collection chính đang được agent truy vấn không hề bị downtime hay lỗi.
- **Bằng chứng quyết định phù hợp:** Code thực tế trong `LocalEmbeddingIndex.build()` bắt try-except, rollback `delete_collection` an toàn nếu `count` mismatch.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi LLM dùng tool `lookup_paper(paper_id_or_title)`, thỉnh thoảng nó tự in hoa hoặc thường sai lệch so với title thực tế, dẫn tới kết quả "No exact paper match found".
- **Lệnh hoặc bước tái hiện:** Test agent thủ công hỏi về "Một Tựa Đề Nào Đó" trong khi dataset là "một tựa đề nào đó".
- **Nguyên nhân gốc:** Dictionary mapping `self.documents_by_title` bị case-sensitive (phân biệt hoa thường).
- **Cách xử lý:** Chuẩn hoá in thường khi build index: mapping lưu keys dưới dạng `.lower()`, và đầu vào `lookup(value)` cũng xử lý `value.strip().lower()`.
- **Cách xác minh sau khi sửa:** Tool lookup bắt được bài báo dù LLM có format chữ hoa chữ thường.
- **Điều học được:** Khi build các exact-match components cho Agent/LLM Tools, cần hỗ trợ fuzzy matching hoặc normalize (chuyển chữ thường, xoá khoảng trắng) để tránh sự kém ổn định của LLM input.

## 7. Hiểu biết về luồng end-to-end

Giải thích ngắn gọn bằng lời của bạn:

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu raw qua API Crossref dạng JSON -> làm sạch, chuẩn hoá thành schema tabular (Dataframe) với cột gộp `text_for_embedding` -> được đẩy qua model `MiniLMEmbeddings` sinh ra vectors -> lưu trữ và đánh index bằng `chromadb` xuống đĩa cứng, kèm metadata.
2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Eval set gồm các câu hỏi và `ground_truth` (paper_id kỳ vọng). RAG Agent sẽ search và trả lời, ta trích xuất `paper_id` từ câu trả lời đó so sánh với `ground_truth`. Nếu trùng thì tính là Hit (Hit Rate), tương tự cho text answer tính F1 token và LLM-as-a-judge accuracy.
3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   Quality checks tập trung vào tính toàn vẹn và độ sạch của records (không null, đủ độ dài, ID unique). Freshness monitoring quan tâm thời điểm dữ liệu được lấy/xuất bản (so sánh ngày publish mới nhất với ngày hiện tại để đánh giá độ trễ).
4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Vì chỉ khi cố định bộ câu hỏi (test set), chúng ta mới thực hiện được phép thử A/B, kiểm chứng chính xác được sự khác biệt của metric là do data thay đổi (bị lỗi/được sửa) chứ không phải do câu hỏi khó/dễ hơn.
5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   Thông qua việc `quality_report.json` và `freshness_report.json` chuyển status thành `success`/`is_fresh` (bằng chứng), kéo theo metrics (F1, Accuracy, Hit rate) phục hồi hoàn toàn hoặc xấp xỉ mức của `baseline_metrics.json`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal          | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| ---------------------- | -------: | --------: | -------: | ------------------------- |
| `retrieval_hit_rate` |      1.0 |       0.9 |      1.0 | Giảm khi bị corrupt vì vector index bị nhiễu do mất dữ liệu |
| `mean_token_f1`      |      0.8 |    0.7192 |      0.8 | Giảm tương ứng vì trả lời sai ngữ cảnh |
| `judge_accuracy`     |      0.8 |       0.7 |      0.8 | Giảm mạnh (mất 10%), hồi phục 100% khi repair |
| `mean_judge_score`   |      4.2 |       3.8 |      4.2 | Model judge đánh giá chất lượng câu trả lời bị tụt dưới 4 |
| Quality checks         |  Success |      Fail |  Success | Corrupted data sinh ra null summary và dup ID |
| Freshness status       |    Fresh |     Stale |    Fresh | Bị ghi đè bởi dữ liệu cũ, làm hỏng freshness |

### Kết luận từ số liệu

Hoàn thành hai chuỗi nguyên nhân–bằng chứng sau:

1. **[Data corruption]** → **[Quality checks failed (4 null summary, 4 unique id vi phạm), freshness failed (28.5% stale rows)]** → **[Agent metric giảm: hit rate 1.0 -> 0.9, accuracy 0.8 -> 0.7]**.
2. **[Repair action phục hồi từ nguồn sạch]** → **[Quality/freshness signal phục hồi về success/true]** → **[Agent metric phục hồi về chính xác mức baseline 1.0 hit rate, 0.8 accuracy]**.

Corruption nào ảnh hưởng rõ nhất và vì sao?
Corruption làm thay thế dữ liệu bằng record cũ và duplicate ID. Việc duplicate ID và mất summary làm ChromaDB vector index bị loãng và nhiễu (hai vector giống hệt nhau hoặc metadata rỗng), dẫn tới khi search bị lấy nhầm tài liệu cũ không phù hợp (làm giảm hit_rate và f1).

Kết quả nào khác với kỳ vọng ban đầu?
LLM judge score không giảm sâu về dưới trung bình (chỉ giảm từ 4.2 xuống 3.8). Điều này cho thấy kể cả lấy sai tài liệu (hit rate 0.9), LLM vẫn đôi khi "chữa cháy" trả lời dựa theo common knowledge hoặc format câu trả lời trơn tru, nên điểm không rớt bằng 0.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Quản lý state cho Database của pipeline:** Cập nhật index phải luôn có staging space, xoá/sửa trực tiếp có nguy cơ để lại hệ luỵ.
2. **Khái niệm "Garbage In, Garbage Out":** Metric của LLM RAG agent bị ràng buộc chặt chẽ với chất lượng bảng dữ liệu (quality) và độ tươi (freshness) trước khi được đưa vào Embeddings.
3. **Normalize input cho Agent Tools:** Các tool lookup chính xác bắt buộc phải có bước chuyển đổi normalize chữ (lower, trim) trước khi đưa vào Python matching dictionary.

### Nếu có thêm thời gian

Tôi sẽ thử cài đặt cơ chế **Hybrid Search (kết hợp TF-IDF/BM25 với Semantic Vector)** trong class `LocalEmbeddingIndex`. Lý do là Semantic Search thỉnh thoảng sẽ gặp khó với các exact keywords dạng mã (ví dụ tìm chính xác tên gen/mã thuốc). Có thể dùng metric Hit Rate để đo xem hybrid search có vượt được baseline vector hay không.

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Mai Hoàng Anh
**Ngày xác nhận:** 2026-09-26
