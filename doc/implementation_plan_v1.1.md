# KẾ HOẠCH TRIỂN KHAI NÂNG CẤP - PHIÊN BẢN v1.1.0 (BỘ LỌC SỐ KÉP STABILIZER)

Tài liệu này chứa chi tiết giải pháp thiết kế bộ lọc số và kế hoạch triển khai nâng cấp mã nguồn của phiên bản `v1.1.0` nhằm giải quyết dứt điểm lỗi nhịp tim/nhịp thở bị nhảy loạn và tăng độ chính xác của chỉ số.

---

## 📌 QUY TẮC PHÁT TRIỂN & CẬP NHẬT (HÃY TUÂN THỦ NGHIÊM NGẶT)
1. **BẢO TOÀN MÃ NGUỒN**: Không tự ý xóa bất kỳ file nào trong thư mục dự án khi chưa có lệnh rõ ràng từ người dùng.
2. **QUẢN LÝ PHIÊN BẢN (VERSION CONTROL)**: Mỗi khi đề xuất giải pháp hoặc nâng cấp mã nguồn, tạo một file Implementation Plan riêng biệt đại diện cho phiên bản đó (ví dụ: `implementation_plan_v1.1.md`) để dễ dàng đối chiếu và quản lý.
3. **CHẠY THỬ NGHIỆM PREVIEW**: Sau khi hoàn thành các cập nhật mã nguồn, thực hiện chạy thử nghiệm (Preview/Dry Run) 1 lần để đảm bảo tính đúng đắn trước khi bàn giao và chờ lệnh của người dùng chạy file chính thức.

---

## 🛠️ CHI TIẾT PHÁC THẢO GIẢI PHÁP NÂNG CẤP v1.1.0

### 1. Phân tích Nguyên nhân Nhảy số Loạn
* **Hiện tượng**: Chỉ số nhịp tim và nhịp thở thô từ radar mmWave có tần suất biến động cao, thỉnh thoảng xuất hiện các đỉnh nhiễu đột ngột (spikes) do cử động cơ thể của đối tượng hoặc nhiễu phase từ radar. GUI hiện tại hiển thị giá trị thô trực tiếp từ mỗi frame.
* **Giải pháp bộ lọc kép**:
  1. **Moving Median Filter (Lọc trung vị động)**: Một bộ lọc có cửa sổ trượt (kích thước $N=7$ cho nhịp tim, $N=9$ cho nhịp thở) giúp triệt tiêu hoàn toàn nhiễu xung thô đột biến.
  2. **1D Kalman Filter (Lọc Kalman 1 chiều)**: Chạy nối tiếp sau lọc trung vị để làm mịn các răng cưa nhỏ mà không gây độ trễ pha (lag) lớn như lọc trung bình động thông thường.
  3. **Cơ chế Giữ trạng thái (Hold State)**: Nếu radar trả về dữ liệu không hợp lệ (`heart_rate_valid` hoặc `breathing_rate_valid` là False), bộ lọc sẽ đóng băng ở trạng thái ổn định gần nhất.
* **Cải tiến giao diện hiển thị**:
  * Hiển thị chỉ số mượt mà sau bộ lọc lên các biến số hiển thị lớn.
  * Vẽ song song trên đồ thị Matplotlib: đường thô (`raw` - nét đứt mờ) và đường mượt mà (`smoothed` - nét liền đậm) để dễ đối chiếu trực quan.

---

## 📁 CÁC FILE SẼ TẠO MỚI / CHỈNH SỬA TRONG v1.1.0

### 1. [NEW] [dsp_filters.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/dsp_filters.py)
* Tạo lớp `KalmanFilter1D` xử lý tính toán lọc Kalman 1 chiều.
* Tạo lớp `MovingMedianFilter` xử lý lọc trung vị cửa sổ trượt động.
* Tạo lớp `VitalSignStabilizer` điều phối cả hai bộ lọc cho nhịp tim và nhịp thở, tích hợp logic kiểm duyệt dữ liệu hợp lệ và đóng băng trạng thái cũ khi mất sóng.

### 2. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)
* Khởi tạo `VitalSignStabilizer` trong hàm dựng `__init__`.
* Khai báo thêm lịch sử dữ liệu thô: `history_hr_raw` và `history_br_raw`.
* Trong `_handle_sample`: Đẩy dữ liệu qua bộ lọc Stabilizer để lấy nhịp tim và nhịp thở làm mịn, lưu đồng thời giá trị thô và giá trị làm mịn.
* Trong `_redraw_plot`: Thay đổi đồ thị Matplotlib để vẽ song song đường nét đứt mờ (dữ liệu thô) và đường nét liền đậm (dữ liệu làm mịn).

---

## 📈 BẢNG QUẢN LÝ LỊCH SỬ CÁC PHIÊN BẢN (VERSION CONTROL LOG)

| Phiên bản | Ngày cập nhật | Tác giả | Nội dung thay đổi chi tiết | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-05-22 | Antigravity AI | - Xem chi tiết tại [implementation_plan_v1.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.md) | **Lịch sử** |
| **v1.1.0** | 2026-05-22 | Antigravity AI | - Đề xuất thiết kế bộ lọc số kép Kalman + Median thời gian thực để ổn định chỉ số nhịp tim/nhịp thở.<br>- Tích hợp hiển thị song song đường dữ liệu thô và đường dữ liệu làm mịn trên GUI. | **Hiện hành** |

---

## 🔬 KẾ HOẠCH XÁC MINH & CHẠY THỬ NGHIỆM (VERIFICATION PLAN)

### 1. Kiểm tra Cú pháp Tự động (Syntax Compiling)
Thực hiện biên dịch thử tất cả các file Python trong dự án bằng lệnh:
```powershell
python -m compileall .
```

### 2. Chạy Preview (Chạy Thử nghiệm GUI)
Khởi chạy thử giao diện đồ họa để đảm bảo ứng dụng tải thành công đồ thị Matplotlib:
```powershell
python run_gui.py
```
* Xác nhận cửa sổ hiển thị bình thường, không có crash khi khởi tạo.
