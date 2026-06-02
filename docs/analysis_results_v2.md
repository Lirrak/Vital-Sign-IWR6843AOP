# Báo cáo Phân tích Kết quả Đo (Analysis Results) - Version 2

Báo cáo này phân tích hiệu năng của hệ thống xử lý dữ liệu và thuật toán lọc **Version 2** dựa trên telemetry thu được trong phiên chạy thực tế ngày 02/06/2026 (Session `144613`), kéo dài **99.220 giây**. Phân tích tập trung vào hiệu quả bám vết khoảng cách, khả năng giảm nhiễu nhảy Range Bin, hiệu năng bộ lọc Kalman và khả năng vẽ Point Cloud ở tần số cao.

---

## 1. Thống kê Phiên chạy & Cấu trúc Gói tin (Session & Packet Statistics)

Dữ liệu ghi nhận từ phiên chạy V2 cho thấy truyền thông UART đạt hiệu suất tối đa:
*   **Tổng số khung hình Vital nhận được**: 70 mẫu.
*   **Tỷ lệ mất gói Vital (Packet Drop Rate)**: **0.00%** (70/70 mẫu được nhận đầy đủ, không rớt gói).
*   **Tổng số gói tin TLV hệ thống nhận được**: 1,120 gói.
    *   `0x3fd` (Tracker Target Index): 1,120 lần xuất hiện ($20\text{ Hz}$).
    *   `0x3f2` (Mapped Point Cloud): **1,008 lần xuất hiện** (tần suất ~90.0%). Chứng tỏ luồng giải mã dữ liệu đám mây điểm (Point Cloud) hoạt động liên tục và ổn định trên host.
    *   `0x3fc` (Tracker Target List): 969 lần xuất hiện.
    *   `0x3f3` (Point Cloud Side Info): 876 lần xuất hiện.
    *   `0x410` (Vital Signs): 70 lần xuất hiện (decimation = 16).

---

## 2. Kiểm chứng Khả năng Giảm Nhiễu Nhảy Range Bin

Sự cải tiến từ Version 1 lên Version 2 thể hiện rõ rệt ở việc ổn định khoảng cách bám vết và cách ly nhiễu:

### Phân bố các Range Bin trong phiên đo V2:
| Chỉ số Range Bin | Khoảng cách vật lý ước tính (m) | Số lượng mẫu (Samples) | Tỷ lệ phần trăm (%) | Đánh giá |
| :--- | :--- | :--- | :--- | :--- |
| **Bin 35** | $35 \times 0.04\text{ m} \approx 1.40\text{ m}$ | 56 | 80.00% | Vị trí mục tiêu thực tế (ổn định cao) |
| **Bin 30** | $30 \times 0.04\text{ m} \approx 1.20\text{ m}$ | 6 | 8.57% | Vùng bám dao động nhẹ |
| **Bin 15** | $15 \times 0.04\text{ m} \approx 0.60\text{ m}$ | 5 | 7.14% | Vùng bám dao động nhẹ |
| **Bin 44** | $44 \times 0.04\text{ m} \approx 1.76\text{ m}$ | 3 | 4.29% | **Nhiễu xa** (Vượt quá giới hạn đo 1.5m) |

### So sánh & Đánh giá kỹ thuật:
1.  **Số lần nhảy Range Bin giảm mạnh**: Phiên đo V2 chỉ ghi nhận **3 lần thay đổi Range Bin** (so với 25 lần của V1). Sự tập trung 80% mẫu tại Bin 35 chứng tỏ thuật toán bám vết đã ổn định hơn đáng kể.
2.  **Hiệu quả của Range-gate Limiter**: Khi radar bám nhầm sang Bin 44 (~1.76m, chiếm 4.29%), bộ giới hạn khoảng cách trên Host đã phát hiện tức thời và từ chối cập nhật (`range_out_of_bounds_1.76m: 3 samples`). Điều này ngăn chặn hoàn toàn sai số từ phản xạ tường phía sau.
3.  **Bù pha động & Gating**: Có **6 mẫu** bị từ chối với lý do `transient_bin_jump_gating`. Thuật toán đã phát hiện chính xác thời điểm thay đổi Range Bin và khóa cập nhật BPM trong 3 frame tiếp theo để đợi bộ lọc DSP ổn định, chặn đứng các gai pha chuyển tiếp.

---

## 3. Phân tích Hiệu suất Lọc Kalman & Thống kê Sinh hiệu

Hệ thống lọc Kalman đã thay thế thành công cơ chế so sánh ngưỡng cứng của Version 1:

| Tham số đo | Nhịp tim Raw (BPM) | Nhịp tim Filtered (BPM) | Nhịp thở Raw (BPM) | Nhịp thở Filtered (BPM) |
| :--- | :---: | :---: | :---: | :---: |
| **Trung bình (Mean)** | 60.89 | 61.02 | 11.07 | 12.02 |
| **Độ lệch chuẩn (Std)** | **9.46** | **4.24** | 3.39 | 2.30 |
| **Nhỏ nhất (Min)** | 50.22 | 50.22 | 0.00 | 6.70 |
| **Lớn nhất (Max)** | **82.03** | **70.57** | 18.41 | 15.94 |

### Đánh giá khách quan về hiệu quả lọc:
1.  **Ổn định Nhịp tim**: Nhịp tim thô (Raw) dao động rất mạnh với độ lệch chuẩn **9.46 BPM** và có gai nhiễu đỉnh lên tới **82.03 BPM**. Bộ lọc **BPM Kalman Tracker** đã giảm độ lệch chuẩn xuống **hơn 2 lần** (chỉ còn **4.24 BPM**) và cắt bỏ hoàn toàn các gai nhọn (giới hạn cực đại sau lọc chỉ còn **70.57 BPM**).
2.  **Kiểm soát Nhịp thở**: Bộ lọc Kalman đã loại bỏ hoàn toàn giá trị lỗi thở bằng 0 từ firmware (`Min=0.00` được kéo về `6.70 BPM`), thu hẹp độ lệch chuẩn xuống **2.30 BPM**.
3.  **Tỷ lệ Loại bỏ dữ liệu (Rejection Rate)**:
    *   Tỷ lệ Invalid/Rejected tăng từ 13.71% (ở V1) lên **24.29%** (ở V2).
    *   *Nguyên nhân*: Phần lớn do cơ chế Gating chuyển bin (`transient_bin_jump_gating`: 8.57%) và giới hạn khoảng cách đo (`range_out_of_bounds`: 4.29%). 
    *   *Đánh giá*: Sự gia tăng tỷ lệ từ chối này là **hoàn toàn tích cực và cần thiết**. Đây là sự đánh đổi kỹ thuật để bảo vệ tính toàn vẹn của dữ liệu sinh hiệu (data integrity), ngăn chặn các mẫu sai số thô do radar bám lệch mục tiêu truyền vào bộ lọc.

---

## 4. Đánh giá Khuyết điểm Hiện tại & Hướng đi cho Version 3

Mặc dù Version 2 đã giải quyết xuất sắc các lỗi của V1, hệ thống vẫn tồn tại các hạn chế sau:

1.  **Độ trễ pha của Kalman Filter**: Khi nhịp tim/nhịp thở thực tế thay đổi thực sự, bộ lọc Kalman cần từ 2-3 mẫu (~2.4 giây) để bám kịp giá trị mới do quán tính của ma trận hiệp phương sai.
2.  **Sự phụ thuộc vào cấu hình tĩnh**: Tham số hiệp phương sai nhiễu đo $R$ và nhiễu hệ thống $Q$ đang được đặt cố định (`KF_VITAL_Q = 0.05`, `KF_VITAL_R = 1.00`). Điều này chưa tối ưu khi đối tượng chuyển động nhẹ hoặc có nhiễu nền thay đổi theo thời gian.

### Đề xuất phát triển Version 3:
*   **Adaptive Kalman Filtering**: Tự động điều chỉnh ma trận hiệp phương sai đo $R$ dựa trên chỉ số biến động lồng ngực `breathing_deviation` và mật độ điểm của đám mây phản xạ (Point Cloud). Nếu mật độ điểm thấp hoặc deviation quá nhỏ, tăng $R$ để Kalman Filter tin cậy hoàn toàn vào mô hình quán tính dự đoán.
*   **Point Cloud Centroid Tracking**: Thay vì tin vào `range_bin` của DSP, ta sẽ tính toán trực tiếp tọa độ trọng tâm (Centroid) của 7 điểm Point Cloud theo trục Y để tự xác định khoảng cách thực tế của lồng ngực trên Host.
