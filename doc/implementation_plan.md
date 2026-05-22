# THƯ MỤC CÁC BẢN KẾ HOẠCH TRIỂN KHAI (IMPLEMENTATION PLANS)

Chào mừng bạn! Theo chỉ thị của bạn về việc lưu trữ **mỗi kế hoạch triển khai của từng phiên bản trong một tệp tin riêng biệt**, thư mục `doc/` hiện đang chứa các tệp kế hoạch tương ứng với các phiên bản sau đây:

---

## 📁 DANH SÁCH CÁC PHIÊN BẢN KẾ HOẠCH (FILES)

### 1. 📄 [Phiên bản v1.0.0 (Bản gốc)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.md)
* **Tên file**: `implementation_plan_v1.md`
* **Nội dung**: Phân tích kiến trúc mã nguồn nguyên bản của dự án, bao gồm cấu trúc thư mục, luồng serial bất đồng bộ, thuật toán giải nén nhị phân mmWave gói tin `0x410` và giao diện đồ họa GUI Tkinter + Matplotlib gốc.
* **Trạng thái**: **Hiện hành / Bản gốc**.

### 2. 📄 [Phiên bản v1.1.0 (Bộ lọc kép Stabilizer)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.1.md)
* **Tên file**: `implementation_plan_v1.1.md`
* **Nội dung**: Bản phác thảo thiết kế chi tiết cho giải pháp thuật toán lọc số kép (Moving Median Filter + 1D Kalman Filter) và tích hợp cơ chế đóng băng giữ trạng thái cùng biểu đồ trực quan hóa dữ liệu kép thô & mượt trên GUI.
* **Trạng thái**: **Hiện hành**.

### 3. 📄 [Phiên bản v1.2.0 (Khử Hài Nhịp Thở & Phổ Burg AR)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.2.md)
* **Tên file**: `implementation_plan_v1.2.md`
* **Nội dung**: Đề xuất thiết kế thuật toán cấp độ 2 nhằm triệt tiêu xuyên nhiễu hài nhịp thở (Adaptive LMS filter) và ứng dụng phổ tự hồi quy Burg độ phân giải cao để cải thiện độ chính xác nhịp tim về mức sai số nhỏ hơn 2 BPM.
* **Trạng thái**: **Đã triển khai**.

### 4. 📄 [Phiên bản v1.3.0 (Đồng bộ Range Bin động & DTFT không đều)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.3.md)
* **Tên file**: `implementation_plan_v1.3.md`
* **Nội dung**: Giải quyết triệt để lỗi lệch Range bin giữa radar và target thực tế bằng cách tự động đồng bộ hóa thời gian thực qua CLI CFG port bất đồng bộ, kết hợp thuật toán NDTFT (Non-uniform DTFT) thích ứng tần số lấy mẫu động để khử hoàn toàn jitter UART.
* **Trạng thái**: **Đã triển khai**.

### 5. 📄 [Phiên bản v1.4.0 (Tích lũy toàn bộ sóng lịch sử khôi phục fs gốc)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.4.md)
* **Tên file**: `implementation_plan_v1.4.md`
* **Nội dung**: Tích lũy toàn bộ mảng 15 mẫu dạng sóng lịch sử nhận được trong mỗi gói tin TLV thay vì chỉ lấy mẫu cuối cùng `[-1]`, đồng thời nội suy chính xác mốc thời gian 90ms cho từng mẫu để khôi phục tần số lấy mẫu gốc (~11.11 Hz) giúp thuật toán NDTFT hoạt động chính xác tuyệt đối.
* **Trạng thái**: **Đã triển khai**.

### 6. 📄 [Phiên bản v1.5.0 (Bộ lọc Range Bin thông minh & Khử đứt gãy pha)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.5.md)
* **Tên file**: `implementation_plan_v1.5.md`
* **Nội dung**: Tích hợp Bộ lọc Range Bin thông minh (Smart Range Bin Gate) cự ly `[2, 20]` (0.5m - 5.0m) để loại bỏ nhiễu range bin cực xa (49, 53, 66) và tự động reset (xóa sạch) bộ đệm dạng sóng khi đổi range bin đo để triệt tiêu hoàn toàn hiện tượng đứt gãy pha.
* **Trạng thái**: **Đã triển khai**.

### 7. 📄 [Phiên bản v1.5.1 (Hiệu chỉnh Smart Range Bin Gate)](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.5.1.md)
* **Tên file**: `implementation_plan_v1.5.1.md`
* **Nội dung**: Hiệu chỉnh dải kiểm duyệt Range bin thông minh từ `[2, 20]` thành `[2, 50]` (tương ứng tối đa 6.0m theo độ phân giải mịn của Tracker) để kích hoạt cơ chế đồng bộ cự ly động thực tế của radar mmWave.
* **Trạng thái**: **Lên kế hoạch (Đang chờ duyệt)**.

---

## 📈 BẢNG QUẢN LÝ LỊCH SỬ CÁC PHIÊN BẢN (VERSION CONTROL LOG)

| Phiên bản | Ngày cập nhật | Tác giả | File tài liệu tương ứng | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.md) | **Lịch sử** |
| **v1.1.0** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.1.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.1.md) | **Đã triển khai** |
| **v1.2.0** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.2.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.2.md) | **Đã triển khai** |
| **v1.3.0** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.3.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.3.md) | **Đã triển khai** |
| **v1.4.0** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.4.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.4.md) | **Đã triển khai** |
| **v1.5.0** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.5.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.5.md) | **Đã triển khai** |
| **v1.5.1** | 2026-05-22 | Antigravity AI | [implementation_plan_v1.5.1.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.5.1.md) | **Lên kế hoạch** |

---

## 📌 QUY TẮC PHÁT TRIỂN & CẬP NHẬT
* Không được phép tự ý xóa bất kỳ file nào trong dự án.
* Mỗi khi có giải pháp hoặc yêu cầu nâng cấp mã nguồn mới, **tạo riêng một file `implementation_plan_vX.Y.md` mới** tương tự để quản lý và theo dõi.

