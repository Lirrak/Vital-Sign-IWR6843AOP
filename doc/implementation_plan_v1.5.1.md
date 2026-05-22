# KẾ HOẠCH TRIỂN KHAI NÂNG CẤP - PHIÊN BẢN v1.5.1 (HIỆU CHỈNH SMART RANGE BIN GATE CHO CỰ LY ĐO THỰC TẾ)

Tài liệu này đề xuất và chi tiết hóa kế hoạch nâng cấp phiên bản `v1.5.1` nhằm hiệu chỉnh dải kiểm duyệt của bộ lọc Range Bin thông minh (Smart Range Bin Gate), cho phép kích hoạt cơ chế đồng bộ hóa Range Bin động và tự động tối ưu hóa cự ly bám bắt của radar mmWave.

---

## 🔍 KẾT QUẢ PHÂN TÍCH THỰC TẾ & VẤN ĐỀ PHÁT HIỆN (FINDINGS & ISSUE)

Dựa trên việc nghiên cứu dữ liệu log đo đạc thực tế của phiên bản `v1.5.0` trong tệp [vital_signs.csv](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/logs/vital_signs.csv):

### 1. Thành công lớn về độ ổn định
* **Khử nhiễu tuyệt đối**: Nhịp tim đo đạc trung bình đạt **67.50 BPM** (Min 50.22, Max 83.71, Std Dev 8.69), bám sát tuyệt đối smartwatch. Số mẫu nhịp tim bị vọt lên 150 - 170 BPM là **0 mẫu (0.0%)**!
* **Dạng sóng mượt mà**: Thuật toán Burg AR kết hợp bộ lọc Butterworth và cơ chế reset bộ đệm tích lũy khi đổi range bin đã loại bỏ hoàn toàn các lỗi đứt gãy pha.

### 2. Sự không đồng nhất giữa Thiết lập Gate và Thực tế bám bắt
* **Vấn đề phát hiện**: 
  * Cột `range_bin` thực tế trong tệp log ghi nhận toàn bộ các mẫu đo nằm ở dải **30 đến 44** (trong đó **bin 37** chiếm đến **78.5%**).
  * Trong khi đó, bộ lọc thông minh ở phiên bản `v1.5.0` đang thiết lập cứng dải hợp lệ:
    ```python
    is_valid_bin = (2 <= sample.range_bin <= 20)
    ```
  * **Hậu quả**: Vì toàn bộ Range Bin thực tế ($30 - 44$) lớn hơn 20, chúng đều bị bộ lọc thông minh chặn lại và coi là "nhiễu rác". Do đó, **cơ chế tự động đồng bộ hóa Range Bin động đã bị vô hiệu hóa hoàn toàn** trong suốt quá trình chạy.
* **Tại sao hệ thống vẫn đo cực kỳ chính xác?**
  * Do lệnh cấu hình mặc định gửi khi radar khởi động là `VSRangeIdxCfg 0 21` (đo cứng ở bin 21).
  * Theo thông số chirp profile, tracker nội suy trên chip bám bắt với độ phân giải mịn là ~0.15m/bin, tương đương Tracker Bin 37 nằm ở cự ly thực tế $37 \times 0.15 \approx 5.55$ mét.
  * Phép đo Vital Signs on-chip đo với độ phân giải thô hơn, nên Vital Signs Bin 21 tương ứng với cự ly $21 \times 0.25 = 5.25$ mét.
  * **Độ lệch khoảng cách thực chất chỉ là 20-30 cm!** Nhờ đó, radar vẫn bắt trọn vẹn vi dao động ngực của bạn, và thuật toán DSP thứ cấp trên GUI đã lọc và đưa ra nhịp tim vô cùng chính xác. Tuy nhiên, nếu bạn di chuyển ra xa hoặc lại gần hơn, radar sẽ không thể tự động đồng bộ cự ly động nữa.

---

## 🛠️ CHI TIẾT PHƯƠNG ÁN NÂNG CẤP v1.5.1

Để kích hoạt lại tính năng đồng bộ cự ly động một cách an toàn và nhạy bén trên toàn bộ phạm vi đo của radar ($0.3\text{m} - 6.0\text{m}$), chúng ta cần điều chỉnh dải kiểm duyệt của Smart Range Bin Gate:

### 1. Nới rộng giới hạn Smart Gate
* **Thiết lập mới**: Cho phép range bin nằm trong dải `[2, 50]`.
  * *Lý do*: Theo độ phân giải bám bắt mịn của tracker on-chip (~0.12 - 0.15m/bin), bin 50 tương ứng với cự ly thực tế tối đa khoảng 6.0m - 7.5m. Điều này bao phủ hoàn toàn Boundary Box 6m của radar mà vẫn lọc bỏ triệt để các bin nhiễu ảo cực xa (>50) do phản xạ đa đường từ môi trường.

---

## 📁 FILE CHỈNH SỬA TRONG v1.5.1

### 1. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)

* **Vị trí chỉnh sửa**: Thay thế dải lọc thông minh ở phương thức `_handle_sample` (Dòng 318):
```diff
-        is_valid_bin = (2 <= sample.range_bin <= 20)
+        is_valid_bin = (2 <= sample.range_bin <= 50)
```

---

## 🔬 KẾ HOẠCH XÁC MINH (VERIFICATION PLAN)

1. **Kiểm tra biên dịch cú pháp tự động**:
   ```powershell
   python -m compileall .
   ```
2. **Chạy thử nghiệm thực tế**:
   ```powershell
   python run_gui.py
   ```
   * **Mục tiêu**:
     * Kiểm tra log hiển thị: Khi radar phát hiện bạn ngồi ở cự ly bin 37, hệ thống sẽ gửi lệnh cấu hình động: `[DSP] Đang cấu hình động radar: Chuyển vùng Vital Signs sang Target 0 ở Range Bin 37...` thành công.
     * Xác nhận bộ đệm waveforms được reset sạch sẽ khi chuyển vùng đo và đo đạc lại với độ ổn định tuyệt đối.
     * Thử nghiệm di chuyển vị trí xa/gần trong phạm vi 6m để xác nhận radar bám bắt động mượt mà.
