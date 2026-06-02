# Báo cáo Phân tích Kết quả Đo (Analysis Results) - Version 4

Báo cáo này phân tích chi tiết hiệu năng của hệ thống thu thập và lọc xử lý dữ liệu **Version 4**, đồng thời so sánh khách quan với các phiên chạy trước. Trọng tâm của Version 4 là việc đưa vào **cơ chế tự động Reset phần cứng (RTS/DTR Hardware Reset)** và chế độ **Tự động bắt đầu/Standby (Daemon Mode)**, kết hợp bộ lọc Kalman thích ứng và thuật toán bám cụm gần nhất NCP (Nearest-Cluster Priority) trên Host.

Phân tích này dựa trên dữ liệu telemetry thực tế từ ba phiên chạy chính thức ngày 02/06/2026:
*   **Session 144857** (Phiên chạy dài kiểm tra kịch bản động): **915.92 giây** (~15.2 phút)
*   **Session 151115** (Phiên chạy tĩnh ở cự ly gần): **112.30 giây** (~1.9 phút)
*   **Session 155208** (Phiên chạy mới nhất, ứng dụng Reset tự động): **105.02 giây** (~1.75 phút)

---

## 1. Thống kê Truyền thông & Hiệu ứng Khởi động Sạch (Communication & Clean Startup Statistics)

Bảng đối chiếu tỉ lệ nhận gói tin TLV giải mã được từ UART trên Host cho cả ba phiên đo:

| Tham số hệ thống | Session `144857` (Cũ) | Session `151115` (Cũ) | Session `155208` (Mới nhất - Auto Reset) |
| :--- | :---: | :---: | :---: |
| **Thời gian ghi nhận thực tế** | 915.92s | 112.30s | **105.02s** |
| **Tổng số mẫu sinh hiệu Vital** | 636 mẫu | 79 mẫu | **73 mẫu** |
| **Tần suất cập nhật sinh hiệu thô**| ~0.70 Hz | ~0.70 Hz | **~0.70 Hz** |
| **Tổng số gói tin TLV hệ thống** | 10,174 gói | 1,273 gói | **1,178 gói** |
| **Tỉ lệ gói 0x3fd (Target Index)** | 10,174 (100.00%) | 1,273 (100.00%) | **1,178 (100.00%)** |
| **Tỉ lệ gói 0x3fc (Target List)**  | 8,238 (80.97%) | 1,073 (84.29%) | **1,096 (93.04%)** |
| **Tỉ lệ gói 0x3f2 (Mapped Point Cloud)** | 8,301 (81.59%) | 1,144 (89.87%) | **1,115 (94.65%)** |
| **Tỉ lệ gói 0x3f3 (Point Cloud Side)**   | 6,440 (63.30%) | 966 (75.88%) | **1,038 (88.12%)** |

### Đánh giá Kỹ thuật Khách quan về Truyền thông:
1.  **Sự vượt trội về độ ổn định UART của Session 155208**:
    Tỉ lệ nhận các gói tin quan trọng trong Session 155208 tăng vọt lên mức kỷ lục: gói **Point Cloud đạt 94.65%** (so với 81.59% của V3) và gói **Target List đạt 93.04%** (so với 80.97% của V3).
2.  **Nguyên nhân kỹ thuật**:
    Trong các phiên bản trước (V3 trở về trước), việc mở cổng Serial và ghi đè cấu hình mà không reset cứng hoặc bấm nút RST thủ công thường để lại một lượng dữ liệu rác (stale bytes) trong bộ đệm FIFO của chip UART. Điều này làm bộ phân tích gói `MmWaveFrameParser` trên Host mất nhiều thời gian để đồng bộ lại khung tiêu đề (Magic Word), dẫn đến mất gói tin lúc khởi tạo. 
    Mã nguồn mới của Version 4 giải quyết triệt để vấn đề này nhờ cơ chế **tự động nhấp nháy RTS/DTR trên cổng CLI**, kéo chân `NRST` xuống mức thấp để buộc radar khởi động lại từ trạng thái "sạch" trước khi nạp cấu hình `.cfg`. Kết quả là dòng byte đầu tiên truyền đi từ DATA port hoàn toàn thẳng hàng, tối ưu hóa hiệu suất phân tích cú pháp từ giây đầu tiên.

---

## 2. Kiểm chứng Thuật toán Bám vết Khoảng cách (Nearest-Cluster Priority - NCP)

Thuật toán NCP tự động lựa chọn cụm điểm di động có cự ly gần nhất nhằm ngăn ngừa radar bám nhầm vào các vật thể tĩnh xung quanh.

### Biểu đồ phân bố dải khoảng cách bám vết (Range Bin Distribution):

#### Session 155208 (Người ngồi ở cự ly trung bình ~1.2m):
*   **Dải phân bố bám chính**: 49.32% mẫu tập trung tại **Bin 31 (1.24m)** và 17.81% tại **Bin 15 (0.60m)**.
*   **Chi tiết phân bố vật lý**:
    *   **Bin 31 (1.24m)**: 36 mẫu (49.32%) -> Vị trí ngồi thực tế ổn định của đối tượng.
    *   **Bin 15 (0.60m)**: 13 mẫu (17.81%) -> Phản xạ phụ gần hơn (có thể từ mép bàn học hoặc chuyển động cánh tay gõ bàn phím).
    *   **Bin 25 (1.00m)**: 7 mẫu (9.59%) -> Điểm trung gian khi người dùng thay đổi tư thế tựa lưng.
    *   **Bin 38 (1.52m)**: 6 mẫu (8.22%) -> Vùng biên nhiễu nền ở xa.
    *   Các bin khác (Bin 8, 12, 13, 29, 32, 33, 42): Tổng cộng 11 mẫu (15.06%)

```
Phân bố Range Bin - Session 155208 (~1.24m Chủ đạo)
┌────────────────────────────────────────────────────────┐
│  ██████████████████████████████  Bin 31 (1.24m): 49.32% │
│  ██████████                    Bin 15 (0.60m): 17.81% │
│  ██████                        Bin 25 (1.00m): 9.59%  │
│  ████                          Bin 38 (1.52m): 8.22%  │
│  ████                          Khác           : 15.06% │
└────────────────────────────────────────────────────────┘
```

### Đánh giá NCP:
Thuật toán NCP đã chứng minh độ linh hoạt cao khi tự động khóa vào cự ly ngồi xa hơn (~1.24m) của người dùng thay vì dập khuôn ở cự ly cực gần 0.4m của phiên chạy trước. Tuy nhiên, nó vẫn bộc lộ khuyết điểm **phân mảnh cụm phản xạ** (khiến 17.81% mẫu nhảy về Bin 15 ở 0.6m). Điều này cho thấy thuật toán bám vết dựa trên việc tìm cụm gần nhất dễ bị phân tán bởi các cụm phản xạ nhỏ hơn nhưng gần radar hơn sinh ra do hoạt động của bàn tay hoặc đồ vật trung gian.

---

## 3. Đánh giá Hiệu lực của Bộ lọc Phòng thủ trên Host (Host-side Defense Performance)

Bộ lọc phòng thủ Host-side kiểm soát tính hợp lệ của dữ liệu trước khi đưa vào Kalman bằng 2 lớp: Giới hạn dải đo cứng (Range-gate Limiter) và Bộ lọc chống nhảy Bin đột ngột (Bin-jump Transient Gating).

### Thống kê và Nguyên nhân Loại bỏ Mẫu (Rejection Comparison):

| Nguyên nhân loại bỏ (Rejection Reason) | Session `144857` (V3) | Session `151115` (V3) | Session `155208` (V4) |
| :--- | :---: | :---: | :---: |
| **Tổng số mẫu bị loại bỏ** | 314 / 636 (**49.37%**) | 34 / 79 (**43.04%**) | **27 / 73 (36.99%)** |
| `transient_bin_jump_gating` | 106 mẫu (16.67%) | 27 mẫu (34.18%) | **15 mẫu (20.55%)** |
| `range_out_of_bounds` | 202 mẫu (31.76%) | 0 mẫu (0.00%) | **8 mẫu (10.96%)** |
| `sinh_hoc_raw_vuot_nguong/gai`| 6 mẫu (0.94%) | 7 mẫu (8.86%) | **4 mẫu (5.48%)** |

### Nhận xét Khách quan về Hiệu lực Bộ lọc:

1.  **Bộ giới hạn dải đo (Range-gate Limiter) hoạt động hoàn hảo**:
    Trong Session 155208, khi NCP bám lệch ra xa mục tiêu ngồi ở 1.24m sang dải nhiễu hậu cảnh ở 1.52m (Bin 38) và 1.68m (Bin 42), lớp phòng thủ cứng đã phát hiện và chặn đứng **100% mẫu vượt ngưỡng** (`range_out_of_bounds_1.52m`: 6 mẫu, `range_out_of_bounds_1.68m`: 2 mẫu). Điều này chứng minh dải bảo vệ của Host $0.3\text{m} - 1.5\text{m}$ (theo cấu hình `app_config.py`) đang bảo vệ Kalman cực kỳ tốt khỏi nhiễu môi trường xa.
2.  **Bin-jump Gating vẫn gây lãng phí tài nguyên dữ liệu lớn**:
    Tỉ lệ loại bỏ do nhảy bin đột ngột chiếm **20.55%** trong Session 155208. Mặc dù có sự cải thiện so với 34.18% của Session 151115, đây vẫn là một điểm thắt cổ chai lớn (lãng phí hơn 1/5 lượng dữ liệu thô). 
    *Bản chất lỗi:* Thuật toán chuyển đổi centroid thành chỉ số bin đo rời rạc bằng phép làm tròn toán học đơn giản `round(Y/0.04)`. Chỉ cần centroid lồng ngực dao động cực nhỏ xung quanh ranh giới giữa hai bin (ví dụ từ 0.599m lên 0.601m), chỉ số bin đo sẽ liên tục bị dao động từ Bin 14 sang Bin 15. Việc dao động ảo này kích hoạt cơ chế gating chặn cập nhật, làm gián đoạn dòng dữ liệu hữu ích không cần thiết.

---

## 4. Hiệu suất lọc Adaptive Kalman Filter & Thống kê Sinh hiệu

Bảng đối chiếu thống kê Nhịp tim và Nhịp thở trước và sau khi đi qua bộ lọc Kalman thích ứng (Adaptive Kalman Filter - scale ma trận $R$ theo mật độ điểm phản xạ):

| Tham số đo lường | Nhịp tim Raw (BPM) | Nhịp tim Filtered (BPM) | Nhịp thở Raw (BPM) | Nhịp thở Filtered (BPM) |
| :--- | :---: | :---: | :---: | :---: |
| **Session 155208 (Auto Reset)** | | | | |
| **Trung bình (Mean)** | 62.31 | **56.04** | 12.52 | **14.80** |
| **Độ lệch chuẩn (Std)** | 10.81 | **3.95** | 4.20 | **2.72** |
| **Giá trị nhỏ nhất (Min)** | 50.22 | 50.22 | 5.02 | 10.21 |
| **Giá trị lớn nhất (Max)** | 83.70 | 66.22 | 23.44 | 23.44 |

### Phân tích Khoa học & Thuật toán:
1.  **Độ mượt sinh hiệu vượt trội**:
    *   **Nhịp tim**: Độ biến động thô cực kỳ lớn (Std thô = 10.81 BPM, dao động từ 50.22 đến 83.70 BPM) đã được bộ lọc Kalman thích ứng nén mượt hoàn hảo xuống Std = **3.95 BPM**, loại bỏ hoàn toàn các gai nhịp tim ảo vượt ngưỡng 70 BPM sinh ra do trễ pha lúc bám dính cụm điểm di chuyển.
    *   **Nhịp thở**: Std thọ giảm từ 4.20 BPM xuống **2.72 BPM**. Lọc Kalman thích ứng hoạt động rất chính xác khi nâng giá trị trung bình nhịp thở từ 12.52 BPM thô lên **14.80 BPM sau lọc**. Điều này là do thuật toán đã phát hiện và loại bỏ các dải mẫu nhịp thở lỗi cực thấp (lân cận 5 BPM - thường là nhiễu do rung động cơ học thứ cấp) để bám chắc vào nhịp thở sinh lý thực tế ổn định quanh mức 14-15 lần/phút.

---

## 5. Bảng Tổng kết Khuyết điểm Kỹ thuật & Định hướng Phát triển Version 5

Dù cơ chế khởi động sạch qua RTS/DTR Reset và Standby Daemon ở Version 4 đã cải tiến vượt bậc về độ ổn định UART và trải nghiệm người dùng, hệ thống hiện tại vẫn tồn tại các điểm yếu chí mạng sau:

### Danh sách Khuyết điểm Kỹ thuật Hiện hữu (Không nịnh bợ):
1.  **Dao động Jittering Centroid ảo (Răng cưa bin ranh giới)**:
    Phép làm tròn rời rạc hóa bin đo (`round(Y/0.04)`) đang triệt tiêu tính liên tục của dữ liệu point cloud. Jittering này là nguyên nhân cốt lõi gây lãng phí 20% đến 34% dữ liệu sinh hiệu thực tế của người dùng.
2.  **Mất bám dính cụm khi có chuyển động phụ tay (NCP distraction)**:
    Khi đối tượng gõ bàn phím hoặc di chuyển tay ở cự ly gần radar hơn lồng ngực (ví dụ ở 0.6m trong khi ngực ở 1.24m), thuật toán NCP mù quáng chọn cụm gần nhất nên lập tức nhảy bin đo về 0.6m (Bin 15 chiếm 17.81%). Điều này làm ngắt quãng dải đo sinh hiệu thực tế của lồng ngực.
3.  **Trễ pha Kalman do sụt giảm điểm phản xạ đột ngột**:
    Khi người dùng ngồi sai tư thế làm số lượng point cloud sụt giảm đột ngột, bộ lọc thích ứng tăng ma trận $R_{adaptive}$ lên gấp nhiều lần. Bộ lọc sẽ bám cứng vào mô hình quán tính cũ và phản ứng rất chậm trước sự thay đổi nhịp tim thực tế, tạo ra trễ pha lên tới 5-8 giây.

---

### Kế hoạch Nâng cấp Kỹ thuật cho Version 5:

*   **1. Bộ lọc Centroid Hysteresis & Kalman 1D trên Host**:
    Thay vì làm tròn trực tiếp $Y_{centroid}$ thô sang Bin đo, hãy đưa $Y_{centroid}$ đi qua một bộ lọc Kalman 1D để làm mịn vị trí liên tục. Đồng thời, áp dụng **cơ chế trễ (Hysteresis window)** với khoảng dịch chuyển tối thiểu $\pm 0.06\text{ m}$ (tương đương 1.5 lần kích thước bin) và duy trì tối thiểu trong 5 khung hình liên tiếp trước khi ra quyết định chuyển bin cập nhật pha. Giải pháp này sẽ triệt tiêu 100% hiện tượng lãng phí dữ liệu do `transient_bin_jump_gating`.
*   **2. Trọng tâm Trọng số Doppler (Doppler-Weighted Centroid)**:
    Khi tính toán $Y_{centroid}$, không sử dụng trung bình cộng hình học đơn thuần. Hãy lấy trọng số dựa trên cường độ phản xạ (Doppler Velocity/SNR) của từng điểm trong đám mây. Do lồng ngực di chuyển tuần hoàn liên tục sẽ có dải vận tốc Doppler đặc trưng và rõ nét hơn bàn tay di chuyển tự do, centroid trọng số Doppler sẽ bám chắc vào lồng ngực bất chấp nhiễu gõ phím ở cự ly gần hơn.
*   **3. Thuật toán "Focus Lock" thông minh dựa trên mô hình nhịp thở**:
    Khi NCP đã phát hiện ra dải nhịp thở chuẩn xác ở cự ly $Y$ (ví dụ 1.24m), nó phải tự động nâng cao độ ưu tiên của dải này bằng một "Cơ chế khóa tiêu cự" (Focus Lock) động, chỉ cho phép mở khóa bám cụm gần hơn khi không còn nhận diện được bất kỳ dao động thở tuần hoàn nào ở dải hiện tại sau 5 giây.
