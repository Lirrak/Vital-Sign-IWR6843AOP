# KẾ HOẠCH TRIỂN KHAI NÂNG CẤP - PHIÊN BẢN v1.2.0 (BỘ LỌC CHỐNG NHIỄU HÀI THÍCH ỨNG & PHỔ ĐỘ PHÂN GIẢI CAO)

Tài liệu này đề xuất giải pháp thiết kế thuật toán nâng cao cấp độ 2 nhằm khắc phục hoàn toàn sự sai lệch nhịp tim **10 BPM** và triệt tiêu ảnh hưởng của hài nhịp thở.

---

## 🛠️ CHI TIẾT PHÁC THẢO GIẢI PHÁP NÂNG CẤP v1.2.0

### 1. Nâng cấp cấu hình Radar (Chirps Tuning)
* **Tệp tin**: [vital_signs_AOP_6m.cfg](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/config/vital_signs_AOP_6m.cfg)
* **Thay đổi**: Điều chỉnh dòng lệnh `vitalsign 15 300` thành `vitalsign 15 512` (hoặc dài hơn).
* **Mục đích**: Tăng số lượng điểm tích lũy của cửa sổ dữ liệu để tăng độ phân giải tự nhiên của FFT trên chip xuống dưới 2 BPM.

### 2. Xây dựng Bộ xử lý nâng cao thứ cấp trên GUI (GUI-Side High-Res DSP)
* **Tệp tin mới**: `vital_signs/dsp_advanced.py`
* **Nội dung thiết kế**:
  1. **ButterworthBandpassFilter**: Bộ lọc thông dải IIR Butterworth bậc 4, lọc cực sạch tần số dạng sóng tim (`heart_waveform`) trong phạm vi hẹp $0.8 - 2.0$ Hz.
  2. **AdaptiveLMSFilter**: Sử dụng dạng sóng nhịp thở làm kênh nhiễu tham chiếu và triệt tiêu phần xuyên nhiễu hài nhịp thở ra khỏi dạng sóng tim cơ học.
  3. **AR_BurgEstimator**: Thuật toán tự hồi quy (Autoregressive - AR) Burg giúp xác định tần số nhịp tim với độ phân giải siêu cao (độ mịn $0.1$ BPM), vượt qua ranh giới độ phân giải thô 4 BPM của FFT.

---

## 📁 CÁC FILE SẼ TẠO MỚI / CHỈNH SỬA TRONG v1.2.0

### 1. [NEW] [dsp_advanced.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/dsp_advanced.py)
* Viết lớp `IIRButterworthFilter` xử lý lọc thông dải dạng sóng bằng Scipy/Numpy.
* Viết lớp `LMSAdaptiveFilter` xử lý khử xuyên nhiễu hài nhịp thở.
* Viết lớp `BurgSpectralEstimator` tính toán phổ nhịp tim siêu mịn.

### 2. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)
* Khai báo bộ ước lượng nâng cao `self.advanced_dsp = AdvancedVitalSignsDSP()`.
* Đẩy chuỗi tín hiệu dạng sóng nhận được (`heart_waveform`, `breath_waveform`) qua `advanced_dsp` để tính toán nhịp tim thứ cấp chính xác cao.
* Hiển thị chỉ số siêu mịn lên GUI và vẽ biểu đồ so sánh.

---

## 📈 BẢNG QUẢN LÝ LỊCH SỬ CÁC PHIÊN BẢN (VERSION CONTROL LOG)

| Phiên bản | Ngày cập nhật | Tác giả | Nội dung thay đổi chi tiết | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-05-22 | Antigravity AI | - Xem chi tiết tại [implementation_plan_v1.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan_v1.md) | **Lịch sử** |
| **v1.1.0** | 2026-05-22 | Antigravity AI | - Đề xuất thiết kế bộ lọc số kép Kalman + Median thời gian thực để ổn định chỉ số nhịp tim/nhịp thở. | **Hiện hành** |
| **v1.2.0** | 2026-05-22 | Antigravity AI | - Thiết kế bộ lọc khử hài nhịp thở thích ứng (Adaptive LMS) và phổ tự hồi quy Burg độ phân giải cao.<br>- Thay đổi chirp profile để tối ưu hóa tần số FFT tích lũy trên chip. | **Chờ phê duyệt** |
