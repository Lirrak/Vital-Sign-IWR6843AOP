# Implementation Plan - Version 2: Point Cloud Visualization, Range Jitter Mitigation, and Kalman Filtering

This document presents the technical design and specifications for **Version 2** of the mmWave Vital Signs application.

---

## 1. User Review Required

We propose major upgrades to the filtering logic and the user interface. Please review the following critical design decisions:

> [!IMPORTANT]
> **1. Bố cục UI Grid 2x2 mới**: Để tích hợp màn hình hiển thị Point Cloud mà không làm rối mắt, chúng tôi sẽ tái cấu trúc lưới Matplotlib thành dạng 2x2 cân đối:
> *   `Góc trên bên trái`: **2D Point Cloud Scatter Plot** (trục X từ -1.5m đến +1.5m, trục Y từ 0m đến 2.5m).
> *   `Góc trên bên phải`: **Respiration Waveform** (đồ thị nhịp thở).
> *   `Góc dưới bên trái`: **Cardiac Waveform** (đồ thị nhịp tim).
> *   `Góc dưới bên phải`: **Vitals Trend History** (lịch sử nhịp tim & nhịp thở).

> [!WARNING]
> **2. Chuyển đổi sang Kalman Filtering**: Bộ lọc thô so sánh ngưỡng đơn giản `RobustVitalFilter` sẽ được nâng cấp thành hệ thống lọc thông minh tích hợp **1D Kalman Filter** cho cả quá trình bám vết khoảng cách (Range Tracking) và ước lượng sinh hiệu (BPM Estimation). Điều này sẽ làm mượt dữ liệu nhưng có thể tạo ra độ trễ pha rất nhỏ (~1-2 mẫu) do quán tính của bộ lọc.

---

## 2. Point Cloud Data Extraction & Layout Design

### A. Point Cloud TLV Parser (`0x3f2`)
Dựa trên phân tích nhị phân của tệp log thô, gói tin TLV Type `0x3f2` (`MMWDEMO_UART_MSG_DETECTED_POINTS`) truyền về có kích thước cố định là **112 bytes** cho mỗi frame chứa 7 điểm phản xạ.
*   **Cấu trúc một điểm**: Gồm 4 giá trị số thực Single-precision Float (16 bytes):
    *   `x`: Tọa độ ngang (meters)
    *   `y`: Tọa độ khoảng cách/chiều sâu (meters)
    *   `z`: Tọa độ chiều cao (meters)
    *   `velocity`: Vận tốc Doppler (m/s)
*   **Giải pháp**: Cập nhật `mmwave_parser.py` để giải mã TLV `0x3f2` và truyền danh sách các điểm $(x, y, z)$ này qua hàng đợi `data_queue` sang GUI để vẽ trực tiếp ở tần số **20 Hz**.

### B. Point Cloud UI Panel
*   Sử dụng đồ thị Scatter Plot của Matplotlib trên Tkinter.
*   Hiển thị vị trí cơ thể/lồng ngực của người dùng dưới dạng các chấm sáng màu xanh lá (neon green) trên nền tối, giúp người dùng quan sát trực quan vị trí bám mục tiêu của radar.

---

## 3. Khắc phục Lỗi Nhảy Range Bin & Bù Pha (Phase Correction)

Dựa trên dữ liệu thực tế V1 (nhảy Range Bin 25 lần trong 3 phút, nhảy loạn từ 0.40m tới 8.64m), chúng tôi đề xuất các giải pháp sau:

### A. Range-gate Limiter (Bộ giới hạn khoảng cách trên Host)
*   Trong `app_config.py`, thêm các tham số `MIN_RANGE_M = 0.3` và `MAX_RANGE_M = 1.5`.
*   Nếu khoảng cách tính từ `range_bin` vượt quá phạm vi này, dữ liệu pha của frame đó sẽ bị bỏ qua hoặc giữ nguyên ở vị trí bám vết hợp lệ trước đó để tránh bắt nhầm phản xạ tường hay ghế phía sau.

### B. Phase Coherence Adjustment (Bù pha động khi nhảy Range Bin)
*   **Hiện tượng**: Khi chuyển từ Range Bin $N_{old}$ sang $N_{new}$, pha $\phi$ nhảy một bước lớn đột ngột gây ra gai BPM.
*   **Thuật toán**:
    1.  Lưu lại pha cuối cùng của bin cũ $\phi_{old}$ và pha đầu tiên của bin mới $\phi_{new}$.
    2.  Tính chênh lệch pha tức thời tại thời điểm chuyển tiếp: $\Delta \phi_{jump} = \phi_{new} - \phi_{old}$.
    3.  Cập nhật bộ tích lũy bù pha: $\text{phase\_offset} = \text{phase\_offset} + \Delta \phi_{jump}$.
    4.  Với mọi mẫu pha tiếp theo $\phi(t)$ từ bin mới, pha hiệu chỉnh liên tục sẽ là: $\phi_{corrected}(t) = \phi(t) - \text{phase\_offset}$.
    5.  Điều này đảm bảo đồ thị pha lồng ngực luôn liên tục và không bị đứt gãy, triệt tiêu hoàn toàn gai nhiễu nhịp tim/nhịp thở.

---

## 4. Nghiên cứu & Thiết kế Bộ lọc Kalman (Kalman Filter Design)

Chúng tôi sẽ triển khai bộ lọc Kalman ở hai thành phần:

### A. Bộ lọc Kalman 1D cho Khoảng cách (Target Range Tracking)
Nhằm làm mịn sự dao động Range Bin của DSP:
*   **Trạng thái hệ thống**: $x_k = [d_k, v_k]^T$ (khoảng cách và vận tốc).
*   **Mô hình dự báo**: 
    $$x_k = A x_{k-1} + w_k, \quad A = \begin{bmatrix} 1 & \Delta t \\ 0 & 1 \end{bmatrix}$$
*   **Phép đo**: $z_k = \text{range\_bin} \times 0.04\text{ m}$.
*   **Ma trận hiệp phương sai đo $R$**: Nếu phát hiện bước nhảy khoảng cách thô lớn ($> 0.3\text{ m}$), $R$ sẽ tự động tăng lên cực lớn để Kalman Filter bỏ qua phép đo lỗi và tiếp tục bám vết mượt mà dựa trên dự báo trạng thái tĩnh trước đó.

### B. Bộ lọc Kalman cho Ước lượng BPM (HR & BR Smoothing)
Thay thế thuật toán so sánh ngưỡng của `RobustVitalFilter`:
*   **Trạng thái**: $x_k = [BPM_k, \Delta BPM_k]^T$.
*   **Ý nghĩa**: Nhịp tim và nhịp thở của người không thể thay đổi đột ngột hàng chục BPM trong 0.8 giây. Bộ lọc Kalman sẽ kết hợp mô hình quán tính sinh học này với kết quả FFT thô từ radar.
*   **Kết quả**: Tự động lọc sạch các gai nhọn BPM do nhiễu động vật lý gây ra mà không bị lỗi khóa cứng bộ lọc (lockout) như ở V1.

---

## 5. Proposed Changes (Danh sách File sửa đổi)

### [Component: Configuration & Parser]

#### [MODIFY] [app_config.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/app_config.py)
*   Thêm các tham số cấu hình: `MIN_RANGE_M = 0.3`, `MAX_RANGE_M = 1.5`, và các tham số cho bộ lọc Kalman.

#### [MODIFY] [mmwave_parser.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/mmwave_parser.py)
*   Bổ sung logic giải mã gói TLV Type `0x3f2` (Point Cloud). 
*   Cập nhật class `ParsedPacket` và `VitalSignData` để mang thêm thông tin tọa độ các điểm Point Cloud.

### [Component: Signal Processing & Filters]

#### [MODIFY] [vital_filter.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/vital_filter.py)
*   Cài đặt lớp `KalmanFilter1D` phục vụ cho Range Tracking và BPM Tracking.
*   Tích hợp thuật toán bù pha động khi phát hiện nhảy Range Bin.

### [Component: User Interface]

#### [MODIFY] [gui.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/gui.py)
*   Tái cấu trúc Matplotlib Grid thành bố cục 2x2.
*   Thêm đồ thị Scatter Plot hiển thị Point Cloud động ở tần số 20 Hz.
*   Cập nhật luồng xử lý hàng đợi để vẽ Point Cloud đồng bộ thời gian thực.

---

## 6. Verification Plan

### Automated / Offline Tests:
1.  **Replay Test**: Chạy chương trình với chế độ phát lại log cũ `python replay_bin.py` để xác nhận GUI vẽ chính xác Point Cloud 2D và các bộ lọc Kalman hoạt động ổn định trên dữ liệu nhị phân đã ghi trước đó.

### Manual Verification:
1.  **Online Test**: Yêu cầu người dùng cắm radar, khởi chạy dashboard, ngồi yên trước radar và thực hiện cử động nhẹ để xác nhận Point Cloud bám đúng hình dáng lồng ngực và nhịp tim/nhịp thở không bị vọt gai khi đổi Range Bin.

---

## 7. Execution Rules
*   **Không tự ý chạy code**: Chúng tôi sẽ không thực thi hoặc thay đổi bất kỳ file mã nguồn nào cho đến khi nhận được sự đồng ý phê duyệt kế hoạch này từ phía bạn.
