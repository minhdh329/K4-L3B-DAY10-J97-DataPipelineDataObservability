# Báo Cáo Đối Chiếu 3 Trạng Thái: Baseline vs Corrupted vs Repaired

> **Mục tiêu:** Đo lường tác động của Data Corruption đến RAG Agent (hiện tượng Silent Failure), chứng minh năng lực cảnh báo sớm của Data Quality Gate (Great Expectations 1.x & Freshness SLA), và kiểm chứng năng lực tự phục hồi an toàn (Idempotent Repair) từ nguồn dữ liệu thô.

---

## 1. Bảng So Sánh Hiệu Năng & Tín Hiệu Observability (3 Trạng Thái)

| Tiêu chí / Chỉ số | Baseline (Dữ liệu Sạch) | Corrupted (Dữ liệu Lỗi) | Repaired (Sau Phục Hồi) | Phục Hồi So Với Baseline |
| :--- | :---: | :---: | :---: | :---: |
| **Retrieval Hit Rate** | **1.0000** (100.0%) | **0.6000** (60.0%) | **1.0000** (100.0%) | **100% Khôi phục** |
| **Mean Token F1** | **1.0000** | **0.6741** | **1.0000** | **100% Khôi phục** |
| **LLM Judge Accuracy** | **1.0000** (100.0%) | **0.7000** (70.0%) | **1.0000** (100.0%) | **100% Khôi phục** |
| **Mean Judge Score** | **5.00 / 5.0** | **3.80 / 5.0** | **5.00 / 5.0** | **100% Khôi phục** |
| **Data Quality Gate (GX 1.x)** | **PASSED** | **FAILED** 🚨 | **PASSED** ✅ | **Chặn đứng lỗi** |
| **Freshness SLA Status** | **FRESH** | **STALE** 🚨 | **FRESH** ✅ | **Đạt chuẩn SLA** |
| **Stale Ratio (> 180 ngày)** | **4.17%** | **59.09%** | **4.17%** | **< 25.0% SLA Threshold** |

---

## 2. Phân Tích Hiện Tượng Silent Failure Trên Dữ Liệu Bẩn

Khi dữ liệu bị tiêm 6 kịch bản lỗi mà không có Data Quality Gate chặn lại:
1. **Drop latest records (mất 20% dữ liệu mới):** Khiến Agent hoàn toàn không tìm thấy các bài báo công bố gần đây (`retrieval_hit_rate` tụt sâu từ 100% xuống 60.0%).
2. **Blank summary & Inject noise:** Khiến vector embedding bị phân tán, câu trả lời trích xuất bị rỗng hoặc lẫn ký tự rác, dẫn đến `token_f1` giảm từ 1.0 xuống 0.6741.
3. **Truncate title:** Làm mất khả năng đối khớp chính xác theo tiêu đề, hệ thống phải fallback sang vector search với độ tin cậy thấp hơn.
4. **Stale date:** Dữ liệu bị đẩy lùi 365 ngày khiến Agent đưa ra thông tin lỗi thời cho người dùng.

Hệ thống RAG thông thường không ném ngoại lệ (no runtime crash) mà âm thầm trả về kết quả sai lệch hoặc rỗng (**Silent Failure**).

---

## 3. Vai Trò Của Data Observability Gate (GX 1.x & Freshness SLA)

- **Great Expectations 1.x:** Phát hiện ngay lập tức 2 lỗi nghiêm trọng:
  - `ExpectColumnValueLengthsToBeBetween`: Phát hiện tóm tắt rỗng/ngắn `< 30 chars`.
  - `ExpectColumnValuesToBeUnique`: Báo động khi phát hiện bản ghi trùng lặp `paper_id`.
- **Freshness SLA Monitor:** Báo động **`is_fresh = False`** ngay khi tỷ lệ bài quá hạn 180 ngày nhảy lên 59.1% (vượt ngưỡng trần 25%).
- **Kết luận:** Nhờ có Quality Gate, pipeline có thể chủ động ngừng cung cấp dữ liệu bẩn vào serving layer và kích hoạt quy trình tự phục hồi.

---

## 4. Cơ Chế Tự Phục Hồi An Toàn (Idempotent Repair)

- **Nguyên lý:** Phục hồi dữ liệu từ bản lưu trữ thô bất biến ban đầu (`data/raw/crossref_records.json` / `crossref_response.json`) thay vì sửa chữa chắp vá trên dữ liệu hỏng.
- **Tính Idempotent (Bất biến theo số lần chạy):** Cho dù chạy lại repair 1 lần hay 100 lần, kết quả dữ liệu sạch, vector store và chỉ số đánh giá đều đạt giá trị tối ưu như baseline ban đầu.
- **Kết quả nghiệm thu:** Toàn bộ các chỉ số `retrieval_hit_rate`, `mean_token_f1`, `judge_accuracy` và `judge_score` sau khi Repaired đều lấy lại 100% phong độ so với Baseline.
