# Implementation Plan - Version 3: Point Cloud Target Tracking, Interactive Range Lock, and Adaptive Kalman Filtering

This document details the software specifications and design choices for **Version 3** of the mmWave Vital Signs application.

---

## 1. Phân tích Nguyên nhân Sai số Khoảng cách (40-50cm vs. 1.4m)

Trong phiên chạy Version 2, mặc dù đối tượng ngồi cách radar thực tế khoảng 40-50cm, thuật toán DSP trên chip radar vẫn báo khoảng cách là **1.40m** (Bin 35) trong 80% thời gian đo.

### Nguyên nhân cốt lõi:
1.  **Nhiễu phản xạ tĩnh lớn (Static Clutter Dominance)**: Vật thể phía sau người dùng (tựa lưng ghế gỗ/ghế lưới, thành bàn, hoặc bức tường ở khoảng cách 1.4m) có diện tích phản xạ hiệu dụng (RCS) lớn hơn nhiều so với lồng ngực của người dùng ở cự ly gần.
2.  **Thuật toán chọn đỉnh năng lượng DSP (Peak Selection Bias)**: Bộ xử lý DSP trên radar tìm kiếm đỉnh năng lượng phổ lớn nhất trong toàn dải đo. Đỉnh phản xạ từ tường/ghế ở 1.4m đè bẹp đỉnh phản xạ lồng ngực ở 0.45m, khiến radar khóa cứng (lock) mục tiêu tại 1.4m và lấy pha của bin này để tính sinh hiệu (dẫn đến sai số thô).

---

## 2. Giải pháp kỹ thuật khắc phục trên Host (Version 3 Specification)

Để khắc phục sai số trên mà không cần can thiệp vào firmware C của radar, chúng ta sẽ thực hiện bám vết mục tiêu chủ động trên Host (Host-side Target Selection) thông qua 2 giải pháp phối hợp:

### A. Thuật toán bám cụm Point Cloud gần nhất (Nearest-Cluster Priority - NCP)
Thay vì tin tưởng vào `vital.range_bin` của DSP, Host sẽ tự động phân tích đám mây điểm Point Cloud (`0x3f2`):
1.  **Lọc nhiễu dải đo**: Chỉ giữ lại các điểm Point Cloud $(x, y, z)$ có khoảng cách chiều sâu $y$ nằm trong dải đo hợp lệ $[MIN\_RANGE\_M, MAX\_RANGE\_M]$.
2.  **Phân cụm khoảng cách (Distance Clustering)**: Gom nhóm các điểm Point Cloud có khoảng cách $y$ gần nhau (sai số $\le 0.15\text{ m}$) thành các cụm mục tiêu độc lập.
3.  **Ưu tiên mục tiêu gần nhất**: Trong các cụm phát hiện được, chọn cụm có khoảng cách trung bình $Y_{centroid}$ nhỏ nhất (gần radar nhất). Đây chắc chắn là lồng ngực người dùng vì cơ thể người luôn che chắn và nằm gần radar hơn tựa ghế hoặc bức tường phía sau.
4.  **Override Range Bin**: Tính toán khoảng cách lọc và ép bộ lọc pha sử dụng Range Bin tương ứng với cụm này:
    $$\text{range\_bin\_override} = \text{round}\left(\frac{Y_{centroid}}{0.04}\right)$$
    Điều này ép bộ xử lý pha trên Host lấy đúng pha phản xạ ở cự ly 40-50cm của người dùng thay vì lấy pha của tường ở 1.4m.

### B. Tính năng Khóa vùng đo trên GUI (Interactive Range Focus Lock)
Bổ sung bảng điều khiển trên GUI cho phép người dùng kiểm soát khoảng cách đo:
*   **Chế độ Tự động (Auto)**: Hệ thống tự chạy thuật toán NCP bám cụm gần nhất.
*   **Chế độ Khóa khoảng cách (Manual Lock / Focus Mode)**:
    *   Người dùng nhập khoảng cách ước tính (ví dụ: `0.5m`) và dải quét (ví dụ: `±0.2m`).
    *   Hệ thống khóa cứng và chỉ phân tích dữ liệu trong dải $[0.3\text{m}, 0.7\text{m}]$, loại bỏ hoàn toàn mọi phản xạ và nhiễu từ khoảng cách 1.4m trở đi.

---

## 3. Nghiên cứu Kalman Filter Thích ứng (Adaptive Kalman Filter)

Để tối ưu hóa thời gian bám vết và độ mượt, bộ lọc Kalman ước lượng BPM sẽ được nâng cấp thành bộ lọc thích ứng (Adaptive Kalman Filter) bằng cách thay đổi động ma trận hiệp phương sai nhiễu đo $R$:

### Thuật toán điều chỉnh $R$ động:
1.  **Tính toán độ tin cậy tín hiệu (Signal Confidence Metric)**:
    Độ tin cậy được tính dựa trên mật độ điểm Point Cloud tập trung tại cụm mục tiêu ($N_{points}$) và biên độ thở (`breathing_deviation`):
    $$C = \alpha \cdot N_{points} + \beta \cdot \text{breathing\_deviation}$$
2.  **Cập nhật $R$ thích ứng**:
    *   Nếu $C$ cao (nhiều điểm phản xạ từ ngực, chuyển động ngực rõ ràng): Giảm mạnh $R$ ($R_{adaptive} = 0.2 \times R_{static}$) để Kalman Filter bám sát và phản ứng cực nhanh với thay đổi nhịp tim thực tế, giảm thiểu độ trễ pha.
    *   Nếu $C$ thấp (tín hiệu yếu, ít điểm Point Cloud hoặc có chuyển động nhiễu động macro-motion): Tăng mạnh $R$ ($R_{adaptive} = 10.0 \times R_{static}$) để Kalman Filter bỏ qua các đo lường nhiễu, tin cậy hoàn toàn vào mô hình dự đoán quán tính để giữ nhịp tim/nhịp thở ổn định.

---

## 4. Proposed Changes (Danh sách File sửa đổi)

### [Component: UI & Controls]

#### [MODIFY] [gui.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/gui.py)
*   Thêm khung điều khiển **"Target Range Lock"** ở Sidebar bên trái:
    *   Combobox chọn chế độ: `Auto (Nearest Cluster)` hoặc `Manual Focus`.
    *   Hai ô nhập liệu: `Center Distance (m)` và `Span (m)`.
*   Truyền cấu hình khóa dải đo này sang `SerialWorker` qua một hàng đợi cấu hình hoặc biến chia sẻ.

#### [MODIFY] [app_config.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/app_config.py)
*   Thêm các tham số mặc định: `TRACKING_MODE = "auto"`, `FOCUS_CENTER_M = 0.5`, `FOCUS_SPAN_M = 0.2`.

### [Component: Signal Processing & Parsing]

#### [MODIFY] [vital_filter.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_uart/vital_filter.py)
*   Triển khai thuật toán **Nearest-Cluster Priority (NCP)** để tự bám vết Y centroid của cụm Point Cloud gần nhất.
*   Cập nhật `RobustVitalFilter` để ghi đè `range_bin` sử dụng vị trí cụm point cloud bám vết được.
*   Nâng cấp bộ lọc Kalman sang cơ chế **Adaptive Kalman Filter** tự điều chỉnh $R$ dựa trên số điểm point cloud và deviation.

---

## 5. Verification Plan

### Automated / Offline Tests:
1.  **Replay Verification**: Sử dụng tệp log cũ `replay_bin.py` và cấu hình `Manual Focus` ở 0.5m để xác minh hệ thống lọc sạch nhiễu ở 1.4m và bám đúng cụm Point Cloud lân cận 0.5m.

### Manual Verification:
1.  **Online Test**: 
    *   Bước 1: Người dùng ngồi cách radar 40-50cm ở chế độ `Auto (Nearest Cluster)`. Xác nhận phần mềm hiển thị khoảng cách khoảng 0.45m thay vì 1.4m.
    *   Bước 2: Chuyển sang chế độ `Manual Focus`, nhập `Center = 0.5` và `Span = 0.2`. Xác nhận đồ thị Point Cloud chỉ vẽ các chấm trong vùng 0.3m đến 0.7m, khóa cứng mục tiêu lồng ngực.

---

## 6. Execution Rules
*   **Tuyệt đối không chạy code**: Chúng tôi sẽ không thực thi lệnh hay thay đổi mã nguồn cho đến khi nhận được chỉ thị phê duyệt kế hoạch từ bạn.
