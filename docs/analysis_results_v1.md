# Báo cáo Phân tích Kết quả Đo (Analysis Results) - Version 1

Báo cáo này phân tích chi tiết dữ liệu telemetry thu được từ radar IWR6843AOP trong phiên chạy thực tế ngày 02/06/2026 (Session `142351`), kéo dài **177.036 giây** (tương đương khoảng 3 phút). Phân tích được thực hiện độc lập, khách quan dựa trên dữ liệu thô ghi nhận từ cổng UART của thiết bị.

---

## 1. Thống kê Phiên chạy & Cấu trúc Gói tin (Session & Packet Statistics)

Dữ liệu được ghi nhận đồng thời qua hai tệp log: `vital_20260602_142351.csv` (chứa kết quả sinh hiệu đã qua xử lý và lọc) và `tlv_summary_20260602_142351.csv` (tóm tắt cấu trúc gói tin TLV nhận được).

*   **Thời gian bắt đầu**: 1.225 giây (kể từ lúc khởi chạy parser)
*   **Thời gian kết thúc**: 178.261 giây
*   **Tổng thời gian đo**: 177.036 giây
*   **Tổng số khung hình Vital nhận được**: 124 mẫu.
*   **Tần suất gửi gói Vital (`0x410`)**: Gửi chính xác sau mỗi 16 khung hình radar ($16 \times 50\text{ ms} = 0.8\text{ s}$ per packet).
*   **Tỷ lệ mất gói Vital (Packet Drop Rate)**: **0.00%** (124/124 mẫu được nhận đầy đủ, không phát hiện frame nhảy cóc hoặc mất gói trên UART).
*   **Tổng số gói tin TLV hệ thống nhận được**: 1,982 gói.
    *   `0x3fd` (Tracker Target Index): 1,982 lần xuất hiện (xuất hiện ở mọi frame $20\text{ Hz}$ để bám vết).
    *   `0x3fc` (Tracker Target List): 1,752 lần xuất hiện (tần suất ~88.4%, có một số frame không bám được mục tiêu).
    *   `0x410` (Vital Signs): 124 lần xuất hiện (tần suất decimation đúng bằng 16).
    *   `0x3f2` (Point Cloud): 1,655 lần xuất hiện.
    *   `0x3f3` (Point Cloud Side Info): 1,527 lần xuất hiện.

---

## 2. Phân tích Hiện tượng Nhảy Range Bin & Sự mất ổn định mục tiêu

Đây là **vấn đề kỹ thuật nghiêm trọng nhất** được phát hiện trong phiên chạy này. Thuật toán tự động bám mục tiêu và chọn Range Bin của DSP trên radar hoạt động vô cùng thiếu ổn định:

### Phân bố các Range Bin được chọn:
| Chỉ số Range Bin | Khoảng cách vật lý ước tính (m) | Số lượng mẫu (Samples) | Tỷ lệ phần trăm (%) | Đánh giá |
| :--- | :--- | :--- | :--- | :--- |
| **Bin 16** | $16 \times 0.04\text{ m} \approx 0.64\text{ m}$ | 21 | 16.94% | Vị trí mục tiêu thực tế (khoảng gần) |
| **Bin 15** | $15 \times 0.04\text{ m} \approx 0.60\text{ m}$ | 18 | 14.52% | Vị trí mục tiêu thực tế (khoảng gần) |
| **Bin 42** | $42 \times 0.04\text{ m} \approx 1.68\text{ m}$ | 18 | 14.52% | **Sai lệch** (Nhiễu phản xạ từ môi trường hoặc ghế ngồi) |
| **Bin 33** | $33 \times 0.04\text{ m} \approx 1.32\text{ m}$ | 10 | 8.06% | **Sai lệch** (Rìa vùng đo) |
| **Bin 19** | $19 \times 0.04\text{ m} \approx 0.76\text{ m}$ | 7 | 5.65% | Khoảng cách bám lồng ngực dịch chuyển |
| **Bin 32** | $32 \times 0.04\text{ m} \approx 1.28\text{ m}$ | 7 | 5.65% | **Sai lệch** |
| **Bin 11** | $11 \times 0.04\text{ m} \approx 0.44\text{ m}$ | 6 | 4.84% | Quá gần đối tượng |
| **Bin 25** | $25 \times 0.04\text{ m} \approx 1.00\text{ m}$ | 5 | 4.03% | Khoảng cách bám lồng ngực di động |
| **Bin 28** | $28 \times 0.04\text{ m} \approx 1.12\text{ m}$ | 5 | 4.03% | Vùng đo trung gian |
| **Bin 18** | $18 \times 0.04\text{ m} \approx 0.72\text{ m}$ | 5 | 4.03% | Vùng đo trung gian |
| **Bin 47** | $47 \times 0.04\text{ m} \approx 1.88\text{ m}$ | 4 | 3.23% | **Sai lệch** |
| **Bin 40** | $40 \times 0.04\text{ m} \approx 1.60\text{ m}$ | 3 | 2.42% | **Sai lệch** |
| **Bin 216** | $216 \times 0.04\text{ m} \approx 8.64\text{ m}$ | 3 | 2.42% | **Lỗi nghiêm trọng** (Nhảy sang nhiễu nền ở khoảng cách xa) |
| **Khác** | Dao động từ 0.40m đến 4.68m | 17 | 13.70% | Các bin còn lại do thuật toán tìm kiếm |

### Đánh giá kỹ thuật khách quan:
1.  **Tần suất nhảy cực kỳ cao**: Trong 177 giây, có tới **25 lần chuyển đổi Range Bin** (trung bình cứ **7.08 giây** thuật toán bám mục tiêu của DSP lại thay đổi khoảng cách đo).
2.  **Sai số khoảng cách quá lớn**: Khoảng cách đo thực tế nhảy loạn xạ từ **0.40 m** đến tận **8.64 m**. Với một đối tượng ngồi tĩnh cách radar trong phạm vi 0.3m – 1.5m, việc bám vào các bin 42 (~1.68m) hay bin 216 (~8.64m) chứng tỏ radar đang bị đánh lừa hoàn toàn bởi các vật thể phản xạ tĩnh phía sau (như bức tường, tủ, hoặc tựa lưng ghế) hoặc nhiễu đa đường (multipath reflections).
3.  **Hậu quả lên Pha (Phase Discontinuity)**: Việc thay đổi Range Bin liên tục tạo ra các bước nhảy pha (phase steps) đột ngột ở phía DSP. Do thuật toán tính toán nhịp tim/nhịp thở dựa trên vi phân pha của tín hiệu phản xạ lồng ngực $\Delta \phi$, mỗi lần nhảy Range Bin sẽ sinh ra các gai nhiễu biên độ lớn. Các gai này sẽ làm sai lệch hoàn toàn kết quả tính nhịp tim/nhịp thở raw trên chip.

---

## 3. Đánh giá Hiệu suất Bộ lọc phía Host (RobustVitalFilter)

Bộ lọc `RobustVitalFilter` được thiết kế để phát hiện và loại bỏ các bước nhảy nhịp thở/nhịp tim đột ngột (outliers) do lỗi nhảy Range Bin nêu trên gây ra.

*   **Tỷ lệ chấp nhận dữ liệu (Valid)**: **86.29%** (107 samples).
*   **Tỷ lệ loại bỏ dữ liệu (Rejected)**: **13.71%** (17 samples).
*   **Phân tích nguyên nhân loại bỏ (Rejection Reasons)**:
    *   `ok` (Hợp lệ): 105 mẫu.
    *   `br_jump_16.74_to_6.70`: 5 mẫu (4.03%) - Phát hiện nhịp thở sụt giảm đột ngột hơn 10 BPM.
    *   `br_jump_6.70_to_20.09`: 4 mẫu (3.23%) - Phát hiện nhịp thở tăng đột biến.
    *   `br_jump_10.04_to_20.09`: 3 mẫu (2.42%) - Nhịp thở tăng vọt gấp đôi trong 0.8s.
    *   `br_jump_6.70_to_16.74`: 3 mẫu (2.42%) - Tăng vọt nhịp thở.
    *   `br_jump_6.70_to_21.76`: 2 mẫu (1.61%) - Nhịp thở nhảy lên ngưỡng bất thường.
    *   `warming_up`: 2 mẫu ban đầu (1.62%) - Thời gian khởi động làm đầy cửa sổ bộ lọc.

### Đánh giá bộ lọc:
*   **Ưu điểm**: Bộ lọc đã hoạt động rất chính xác theo đúng thiết kế toán học. Nó đã phát hiện ra các thay đổi nhịp thở không sinh lý (ví dụ: nhảy từ 6.70 BPM lên 20.09 BPM trong 0.8 giây) và gắn nhãn loại bỏ (`filter_valid=0`).
*   **Hạn chế**: Bộ lọc chỉ giải quyết "phần ngọn". Khi DSP nhảy Range Bin liên tục và giữ nguyên vị trí sai lệch trong thời gian dài (như giữ ở Bin 42 trong 18 mẫu ~ 14.4 giây), bộ lọc buộc phải chấp nhận giá trị mới sau khi kích hoạt cơ chế reset (consecutive rejection limit = 10). Dữ liệu trong thời gian bám sai mục tiêu này hoàn toàn không có giá trị sinh học thực tế.

---

## 4. Thống kê Sinh hiệu (Heart Rate & Breathing Rate Statistics)

Dưới đây là bảng so sánh trực quan các thông số thống kê giữa dữ liệu thô (Raw) từ radar và dữ liệu sau lọc (Filtered):

| Tham số đo | Nhịp tim Raw (BPM) | Nhịp tim Filtered (BPM) | Nhịp thở Raw (BPM) | Nhịp thở Filtered (BPM) |
| :--- | :---: | :---: | :---: | :---: |
| **Trung bình (Mean)** | 61.89 | 60.23 | 11.73 | 11.20 |
| **Độ lệch chuẩn (Std)** | 8.42 | 6.42 | 4.23 | 2.91 |
| **Nhỏ nhất (Min)** | 50.22 | 50.22 | 6.70 | 6.70 |
| **Lớn nhất (Max)** | 80.36 | 71.99 | 21.76 | 16.74 |

### Đánh giá sinh học và thuật toán:
1.  **Nhịp tim**: Bộ lọc làm giảm độ lệch chuẩn từ **8.42 BPM xuống 6.42 BPM**, đồng thời gạt bỏ các gai nhọn nhịp tim cực đại (giảm từ 80.36 BPM xuống 71.99 BPM). Trị số trung bình 60.23 BPM là rất thực tế đối với một người trưởng thành ở trạng thái nghỉ ngơi tĩnh.
2.  **Nhịp thở**: Nhịp thở Raw ghi nhận nhiều dao động bất thường lên tới 21.76 BPM (thở nhanh/nhiễu động). Bộ lọc đã kiểm soát chặt chẽ và kéo giá trị cực đại sau lọc về mức thực tế hơn là **16.74 BPM**, ổn định nhịp thở trung bình ở mức **11.20 BPM**.
3.  **Chỉ số Breathing Deviation**: Đạt giá trị trung bình là **0.053745** với độ lệch chuẩn **0.040833**. Mức tối thiểu ghi nhận được cực thấp (**0.000051**). Điều này cho thấy có những thời điểm biên độ chuyển động ngực bám được gần như bằng không, tương ứng với các pha radar bị mất dấu lồng ngực hoàn toàn hoặc chuyển sang range bin trống không có chuyển động.

---

## 5. Kết luận & Đề xuất kỹ thuật cho Version 2

Kết quả đo sinh hiệu của Version 1 đã chỉ ra một sự thật rằng: **Mặc dù bộ lọc phần mềm trên Host (Python) hoạt động tốt về mặt thuật toán toán học, chất lượng dữ liệu đầu ra vẫn bị ảnh hưởng nặng nề bởi sự bất ổn bám mục tiêu của phần cứng/DSP.**

### Điểm yếu cốt lõi cần khắc phục:
1.  **Thuật toán chọn Range Bin của radar quá nhạy với nhiễu tĩnh (Static Clutter)**: Radar liên tục bị phân tâm bởi các phản xạ ở khoảng cách xa (>1.5m).
2.  **Không có cơ chế bù đắp pha khi đổi Range Bin**: Gây ra các đứt gãy pha đột ngột, trực tiếp tạo ra sai số BPM.

### Đề xuất hành động cho Version 2:
*   **Bù pha động (Phase Coherence Adjustment)**: Thêm thuật toán lưu lại pha cuối của Range Bin cũ, tính chênh lệch pha tức thời khi nhảy sang Range Bin mới, và cộng bù trừ vào chuỗi pha liên tục để triệt tiêu hoàn toàn gai BPM khi nhảy bin.
*   **Bộ lọc Clutter Subtraction trên Host**: Thực hiện thuật toán tự động trừ nhiễu nền tĩnh (clutter) trên chuỗi tín hiệu thô nhận được từ UART, hạn chế việc radar nhảy sang các bin phản xạ tĩnh ở xa.
*   **Giới hạn khoảng cách bám (Range-gate Limiter)**: Cấu hình cứng hoặc lọc trên Host để loại bỏ hoàn toàn các Range Bin ngoài phạm vi $0.3 - 1.5\text{ m}$ (tương ứng loại bỏ các bin $< 7$ và $> 38$), tránh hiện tượng nhảy sang bin 42 hay 216 như trong log.
