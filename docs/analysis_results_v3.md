# Báo cáo Phân tích Kết quả Đo (Analysis Results) - Version 3

Báo cáo này phân tích chi tiết hiệu năng của hệ thống xử lý dữ liệu và thuật toán lọc **Version 3** dựa trên dữ liệu telemetry thu được từ hai phiên chạy thực tế ngày 02/06/2026: Phiên đo dài (Session `144857`, kéo dài **915.92 giây**) và Phiên đo mới nhất (Session `151115`, kéo dài **112.30 giây**). 

Phân tích tập trung vào khả năng tự động bám vết lồng ngực thông qua thuật toán bám cụm Point Cloud gần nhất (Nearest-Cluster Priority - NCP), hiệu năng của bộ lọc Kalman thích ứng (Adaptive Kalman Filter) điều chỉnh động hiệp phương sai $R$, cơ chế loại bỏ nhiễu khoảng cách và đánh giá các hạn chế kỹ thuật hiện tại làm tiền đề cho Version 4.

---

## 1. Thống kê Phiên chạy & Cấu trúc Gói tin (Session & Packet Statistics)

Bảng tổng hợp truyền thông và số lượng gói tin giải mã trên Host cho cả hai phiên đo:

| Tham số hệ thống | Phiên chạy dài (Session `144857`) | Phiên chạy mới nhất (Session `151115`) |
| :--- | :---: | :---: |
| **Thời gian ghi nhận thực tế** | 915.92 giây (~15.2 phút) | 112.30 giây (~1.9 phút) |
| **Tổng số mẫu sinh hiệu Vital nhận được** | 636 mẫu | 79 mẫu |
| **Tần suất cập nhật sinh hiệu thô** | ~0.70 Hz | ~0.70 Hz |
| **Tổng số gói tin TLV hệ thống** | 10,174 gói | 1,273 gói |
| **Tỷ lệ nhận gói 0x3fd (Target Index)** | 10,174 gói (100.00%) | 1,273 gói (100.00%) |
| **Tỷ lệ nhận gói 0x3fc (Target List)** | 8,238 gói (80.97%) | 1,073 gói (84.29%) |
| **Tỷ lệ nhận gói 0x3f2 (Mapped Point Cloud)**| 8,301 gói (81.59%) | 1,144 gói (89.87%) |
| **Tỷ lệ nhận gói 0x3f3 (Point Cloud Side)** | 6,440 gói (63.30%) | 966 gói (75.88%) |

> [!NOTE]
> Tần suất cập nhật sinh hiệu thô đạt ~0.70 Hz do thiết lập decimation từ firmware radar (truyền gói Vital sau mỗi 16 khung hình tracking 20 Hz, tức $20 / 16 \approx 1.25\text{ Hz}$ trong điều kiện lý tưởng, kết hợp trễ xử lý và truyền nhận serial trên Host). Tỷ lệ nhận gói đám mây điểm (Point Cloud) đạt trên 80% đảm bảo dữ liệu đầu vào ổn định cho thuật toán bám vết tọa độ.

---

## 2. Kiểm chứng Khả năng Khắc phục Sai số Khoảng cách (Nearest-Cluster Priority - NCP)

Sự cải tiến cốt lõi của Version 3 là việc triển khai thuật toán NCP để Host tự bám vết lồng ngực, khắc phục sai số thô bám nhầm sang phản xạ tĩnh ở 1.4m (Bin 35) của Version 2.

### Phân bố các Range Bin trong hai phiên chạy:

#### A. Session 151115 (Người ngồi ổn định cách radar 40-50cm):
*   **Vùng bám thực tế**: 100.00% mẫu nằm trong dải từ Bin 9 (0.36m) đến Bin 19 (0.76m).
*   **Chi tiết phân bố**:
    *   **Bin 15 (0.60m)**: 42 mẫu (53.16%) -> Trọng tâm bám chính.
    *   **Bin 9 (0.36m)**: 11 mẫu (13.92%)
    *   **Bin 11 (0.44m)**: 10 mẫu (12.66%)
    *   **Bin 12 (0.48m)**: 5 mẫu (6.33%)
    *   **Bin 13 (0.52m)**: 3 mẫu (3.80%)
    *   Các bin khác (Bin 16, 18, 19): Tổng cộng 7 mẫu (8.86%)
*   **Đánh giá**: Thuật toán NCP đã khắc phục hoàn toàn lỗi bám tĩnh của DSP trên chip radar. Toàn bộ 100% mẫu được khóa vào dải khoảng cách vật lý của lồng ngực người dùng ($0.36\text{m} - 0.76\text{m}$), loại bỏ triệt để đỉnh năng lượng ảo từ ghế/tường ở 1.40m.

#### B. Session 144857 (Kịch bản động dài hạn / Người dùng đứng dậy di chuyển):
*   **Chi tiết phân bố**:
    *   **Nhóm cự ly gần (0.36m - 0.76m)**: Chiếm **38.83%** (Bin 9: 1.57%, Bin 10: 1.89%, Bin 11: 13.52%, Bin 14: 7.55%, Bin 15: 7.86%, Bin 16: 4.56%, Bin 18: 5.19%). Đây là khoảng thời gian đối tượng ngồi đo thực tế.
    *   **Nhóm cự ly trung bình (1.28m - 1.40m)**: Chiếm **22.33%** (Bin 32: 20.13%, Bin 35: 1.89%). Radar bám vào tựa ghế gỗ/vách ngăn sau khi người dùng rời vị trí.
    *   **Nhóm cự ly xa (>1.5m)**: Chiếm **23.59%** (Bin 51 ở 2.04m: 19.50%, Bin 141 ở 5.64m: 2.04%, Bin 128 ở 5.12m: 1.10%). Radar bám vào tường hoặc người đi lại ở xa.
*   **Đánh giá**: Trong kịch bản dài hạn khi người dùng di chuyển ra ngoài hoặc thay đổi tư thế mạnh, thuật toán NCP tự động lựa chọn cụm point cloud tiếp theo có cự ly gần nhất. Điều này dẫn đến sự dịch chuyển bám vết sang các vật thể tĩnh ở xa khi không có đối tượng ở cự ly gần.

---

## 3. Phân tích Hiệu quả Bộ lọc Gating trên Host (Host-side Defense)

Cơ chế phòng thủ trên Host của Version 3 bao gồm hai lớp lọc: Bộ giới hạn dải đo (Range-gate Limiter) và Gating chuyển bin (Bin-jump Transient Gating).

### Tỷ lệ và Nguyên nhân Loại bỏ Mẫu (Rejection Statistics):

```
Session 144857 (Rejection Rate: 49.37% - 314/636 samples rejected)
┌────────────────────────────────────────────────────────┐
│  - range_out_of_bounds_2.04m : 124 samples (19.50%)    │
│  - transient_bin_jump_gating  : 106 samples (16.67%)    │
│  - range_out_of_bounds_other  : 48 samples  (7.55%)     │
│  - Sinh học thô vượt ngưỡng/gai: 36 samples  (5.65%)     │
└────────────────────────────────────────────────────────┘

Session 151115 (Rejection Rate: 43.04% - 34/79 samples rejected)
┌────────────────────────────────────────────────────────┐
│  - transient_bin_jump_gating  : 27 samples  (34.18%)    │
│  - Sinh học thô vượt ngưỡng/gai: 7 samples   (8.86%)     │
└────────────────────────────────────────────────────────┘
```

### Nhận xét Kỹ thuật Khách quan:

1.  **Hiệu quả tuyệt đối của Range-gate Limiter**:
    Trong Session 144857, khi người dùng rời vị trí và thuật toán NCP bám nhầm sang các cụm ở cự ly xa (Bin 51 ở 2.04m, Bin 141 ở 5.64m), bộ giới hạn khoảng cách trên Host đã phát hiện và loại bỏ ngay lập tức 100% các mẫu này (`range_out_of_bounds_2.04m`: 124 mẫu). Điều này ngăn chặn hoàn toàn việc đưa pha của các mục tiêu ảo/nhiễu nền vào bộ lọc sinh hiệu.
2.  **Hạn chế nghiêm trọng của Bin-jump Gating (Centroid Jittering)**:
    *   Trong phiên đo ổn định `151115`, tỷ lệ mẫu bị từ chối do `transient_bin_jump_gating` lên tới **34.18%** (27/79 mẫu).
    *   *Nguyên nhân*: Các điểm Point Cloud phản xạ từ lồng ngực dao động liên tục về số lượng và vị trí qua từng frame. Khi tính toán trọng tâm cụm $Y_{centroid}$, sai số răng cưa nhỏ xuất hiện. Công thức xác định bin ép bộ xử lý pha:
        $$\text{range\_bin\_override} = \text{round}\left(\frac{Y_{centroid}}{0.04}\right)$$
        Khi $Y_{centroid}$ dao động nhỏ xung quanh ranh giới giữa hai bin (ví dụ: nhảy liên tục giữa 0.439m và 0.441m), chỉ số bin override sẽ dao động liên tục giữa Bin 11 và Bin 12. Điều này liên tục kích hoạt cơ chế gating (khóa cập nhật trong 3 khung hình tiếp theo), khiến hơn 1/3 lượng dữ liệu sinh hiệu hữu ích bị loại bỏ một cách không cần thiết, làm giảm độ mượt của kết quả lọc Kalman.

---

## 4. Hiệu suất lọc Adaptive Kalman Filter & Thống kê Sinh hiệu

Hệ thống lọc thích ứng tự động điều chỉnh ma trận hiệp phương sai đo $R$ dựa trên độ tin cậy tín hiệu $C$:
$$C = 0.2 \cdot N_{points} + 5.0 \cdot \text{breathing\_deviation}$$
$$R_{adaptive} = R_{static} \cdot \text{scale}$$

### Bảng đối chiếu Thống kê Sinh hiệu trước và sau lọc:

| Tham số đo | Nhịp tim Raw (BPM) | Nhịp tim Filtered (BPM) | Nhịp thở Raw (BPM) | Nhịp thở Filtered (BPM) |
| :--- | :---: | :---: | :---: | :---: |
| **Session 144857** | | | | |
| *Trung bình (Mean)* | 63.20 | 65.10 | 11.90 | 10.85 |
| *Độ lệch chuẩn (Std)* | **8.51** | **6.05** | 3.85 | **2.97** |
| *Nhỏ nhất (Min)* | 50.22 | 53.62 | 0.00 | 6.70 |
| *Lớn nhất (Max)* | 87.05 | 73.66 | 21.76 | 21.76 |
| **Session 151115** | | | | |
| *Trung bình (Mean)* | 62.87 | 61.57 | 11.63 | 10.77 |
| *Độ lệch chuẩn (Std)* | **9.14** | **5.08** | 5.08 | **1.89** |
| *Nhỏ nhất (Min)* | 50.22 | 50.22 | 0.00 | 7.28 |
| *Lớn nhất (Max)* | 83.70 | 69.18 | 35.16 | 15.07 |

### Đánh giá Kỹ thuật:

1.  **Ổn định sinh hiệu**:
    Bộ lọc thích ứng đã giảm đáng kể độ biến động của nhịp tim (Std giảm từ 9.14 BPM xuống còn 5.08 BPM trong Session 151115) và cắt bỏ hoàn toàn các gai nhiễu thô (Max nhịp tim sau lọc là 69.18 BPM so với 83.70 BPM thô). Nhịp thở được làm mượt tối đa với Std chỉ còn 1.89 BPM.
2.  **Khắc phục triệt để lỗi Zero-Value & Lockout**:
    *   Các giá trị nhịp thở lỗi bằng 0 từ firmware (`Min=0.00`) đã được loại bỏ hoàn toàn trong cả hai phiên đo nhờ hàm validator.
    *   Bộ lọc không xảy ra hiện tượng kẹt trạng thái (lockout) nhờ cơ chế reset tự động khi số mẫu rejected liên tiếp đạt ngưỡng 10 (`filter_lockout_recovery_reset` kích hoạt thành công).

---

## 5. Khuyết điểm Kỹ thuật Hiện tại & Đề xuất Nâng cấp cho Version 4

Dù giải quyết được lỗi sai số khoảng cách của V2, hệ thống V3 vẫn tồn tại các khuyết điểm kỹ thuật sau:

1.  **Hiện tượng Jittering Chỉ số Bin (Bin Index Jittering)**:
    Như phân tích ở mục 3, việc tính toán trọng tâm Point Cloud đơn giản và làm tròn trực tiếp tạo ra sự dao động bin ảo. Đây là khuyết điểm lớn nhất của V3 gây lãng phí 34% dữ liệu.
2.  **Sự phụ thuộc vào mật độ Point Cloud không ổn định**:
    Mật độ đám mây điểm từ ngực thay đổi liên tục tùy thuộc vào tư thế ngồi và nhịp thở của người dùng. Khi số lượng điểm giảm đột ngột, độ tin cậy tín hiệu $C$ sụt giảm mạnh, khiến $R_{adaptive}$ tăng lên tới 10 lần. Điều này làm cho bộ lọc Kalman tạm thời phớt lờ các thay đổi sinh hiệu thực tế để tin hoàn toàn vào mô hình quán tính, tạo ra độ trễ pha lớn khi nhịp tim thực tế biến động nhanh.

### Đề xuất Nâng cấp Kỹ thuật cho Version 4:

*   **Bộ lọc Centroid Hysteresis (Trễ biên độ Bin)**:
    Không làm tròn trực tiếp centroid Y để chuyển bin. Áp dụng một bộ lọc Kalman 1D làm mịn tọa độ $Y_{centroid}$, kết hợp cơ chế trễ (hysteresis window) với độ rộng $\pm 0.06\text{ m}$ (tương đương 1.5 lần kích thước bin). Chỉ cho phép chuyển bin đo khi lồng ngực dịch chuyển thực sự vượt quá ngưỡng trễ hoặc duy trì trạng thái mới liên tục trong ít nhất 5 khung hình sinh hiệu.
*   **Trọng tâm Trọng số Năng lượng (Weighted Centroid)**:
    Thay vì tính trung bình cộng tọa độ $y$ của các điểm trong cụm, tính trọng tâm có trọng số dựa trên giá trị Doppler hoặc cường độ phản xạ (SNR) của từng điểm. Điều này giúp tọa độ centroid bám sát vào vùng chuyển động mạnh nhất của lồng ngực, giảm thiểu ảnh hưởng của các điểm point cloud nhiễu biên.
*   **Dynamic Gating Threshold**:
    Tự động rút ngắn thời gian lockout gating từ 3 frame xuống 1 frame khi độ lệch chuẩn của nhịp thở (`breathing_deviation`) nhỏ hơn 0.03, biểu thị tín hiệu lồng ngực đang cực kỳ tĩnh lặng và ổn định.
