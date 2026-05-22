# KẾ HOẠCH TRIỂN KHAI NÂNG CẤP - PHIÊN BẢN v1.5.0 (BỘ LỌC RANGE BIN THÔNG MINH & KHỬ ĐỨT GÃY PHA BỘ ĐỆM)

Tài liệu này phân tích dữ liệu log vận hành thực tế mới thu thập được trong `vital_signs.csv` và đề xuất giải pháp xử lý triệt để hiện tượng nhịp tim thỉnh thoảng bị nhảy vọt lên 150 - 170 BPM cho phiên bản `v1.5.0`.

---

## 🔍 PHÂN TÍCH DỮ LIỆU LOG THỰC TẾ & NGUYÊN NHÂN CỐT LÕI (ROOT CAUSE ANALYSIS)

Dựa trên việc nghiên cứu sâu tệp log thực tế [vital_signs.csv](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/logs/vital_signs.csv) mới được ghi nhận (dung lượng tăng vọt lên 134KB), chúng tôi đã phát hiện ra nguyên nhân cốt lõi gây ra hiện tượng không ổn định này:

### 1. Sự nhảy vọt bất thường của Range Bin do nhiễu môi trường
* **Bằng chứng từ Log**:
  * Tại các dòng log đầu tiên, tracker hoạt động ổn định ở `range_bin = 12` đến `14` (khoảng cách cự ly thực tế hợp lý $3.0\text{m} - 3.5\text{m}$).
  * Tuy nhiên, ở các dòng tiếp theo, xuất hiện liên tiếp các cú nhảy range bin cực kỳ bất thường: `range_bin = 49`, `53`, `66`, `60`... (tương ứng với cự ly từ $12.25$m đến $16.5$m!).
  * Theo tệp cấu hình radar [vital_signs_AOP_6m.cfg](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/config/vital_signs_AOP_6m.cfg), cự ly bám bắt tối đa (`boundaryBox`) được thiết lập cứng là **6 mét** (tương đương tối đa bin 24).
  * Do đó, các giá trị range bin lớn hơn 24 (như 49, 53, 66) chắc chắn là **nhiễu rác (clutter), quạt máy hoặc phản xạ đa đường (ghost targets)**, nơi không hề có người đứng đo.

### 2. Hiện tượng Đứt gãy pha (Phase Discontinuities) trong bộ đệm tích lũy dạng sóng
* **Cơ chế gây lỗi**:
  * Khi phát hiện range bin thay đổi (kể cả do nhiễu nhảy lên các bin ảo như 49, 53), ứng dụng GUI lập tức truyền lệnh cập nhật bin đo mới qua cổng CFG.
  * Tuy nhiên, bộ đệm tích lũy dạng sóng (`accumulated_heart_waveform`) có dung lượng tối đa 256 mẫu (tương đương 25 giây gần nhất) **vẫn giữ nguyên dữ liệu cũ của bin trước đó**.
  * Việc trộn lẫn các mảnh dạng sóng đo ở các khoảng cách hoàn toàn khác nhau (ví dụ: đang ở bin 13 nhảy lên bin 49 rồi giật về bin 13) tạo ra một chuỗi dữ liệu thô cực kỳ hỗn loạn, đứt gãy pha và nhiễu biên độ cực lớn.
  * Khi thuật toán NDTFT phân tích phổ tần số rời rạc không đều trên chuỗi dữ liệu đứt gãy pha nghiêm trọng này, nó sẽ sinh ra các đỉnh phổ giả ở vùng tần số cao, dẫn đến kết quả nhịp tim ước lượng bị nhảy loạn xạ lên **150 đến 170 BPM** trong suốt 25 giây sau đó (cho đến khi dữ liệu bin cũ bị đẩy hoàn toàn ra ngoài bộ đệm).

---

## 🛠️ CHI TIẾT PHÁC THẢO GIẢI PHÁP NÂNG CẤP v1.5.0

Để giải quyết triệt để vấn đề này, phiên bản `v1.5.0` sẽ được trang bị hai nâng cấp quan trọng:

### 1. Thiết lập Bộ lọc Range Bin thông minh (Smart Range Bin Gate)
* **Giải pháp**: Chỉ chấp nhận range bin nếu nó nằm trong phạm vi cự ly thực tế hợp lý có con người ngồi đo trước cảm biến (thiết lập dải bin hợp lệ từ **2 đến 20**, tương đương cự ly $0.5$m đến $5.0$m).
* Bất kỳ range bin nào lớn hơn 20 (như 49, 53, 66) hoặc nhỏ hơn 2 sẽ bị coi là nhiễu nhất thời và bị loại bỏ ngay lập tức (không gửi lệnh cập nhật, giữ nguyên vùng đo cũ đang hoạt động ổn định).

### 2. Reset (Xóa sạch) bộ đệm tích lũy khi đổi Range Bin đo thành công
* **Giải pháp**: Ngay khi kích hoạt luồng phụ cập nhật range bin mới cho radar, ứng dụng GUI sẽ lập tức xóa sạch bộ đệm tích lũy dạng sóng:
  ```python
  self.accumulated_heart_waveform.clear()
  self.accumulated_breath_waveform.clear()
  self.accumulated_timestamps.clear()
  ```
* **Ý nghĩa**: Loại bỏ 100% sự đứt gãy pha giữa các cự ly đo khác nhau. Khi bắt đầu đo ở bin mới, hệ thống sẽ sử dụng chỉ số nhịp tim dự phòng thô từ chip phát về trong thời gian bộ đệm tích lũy mẫu sạch mới (warm-up dưới 64 mẫu). Khi bộ đệm đạt trên 64 mẫu sạch của bin mới, bộ DSP nâng cao sẽ tiếp quản và đưa ra chỉ số nhịp tim siêu chính xác, ổn định tuyệt đối.

---

## 📁 FILE SẼ CHỈNH SỬA TRONG v1.5.0

### 1. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)

* **Cập nhật phương thức `_handle_sample`**:
  * Tích hợp thêm điều kiện kiểm duyệt Range bin hợp lệ: `is_valid_bin = (2 <= sample.range_bin <= 20)`.
  * Chỉ tiến hành cập nhật range bin động khi bin mới là hợp lệ.
  * Khi tiến hành đổi range bin, thực hiện xóa sạch bộ đệm tích lũy dạng sóng và timestamps:
    ```python
    self.accumulated_heart_waveform.clear()
    self.accumulated_breath_waveform.clear()
    self.accumulated_timestamps.clear()
    ```
  * In log thông báo chi tiết: `[DSP] Đã xóa bộ đệm tích lũy dạng sóng để chuẩn bị nhận dữ liệu từ Range Bin mới X...` để người dùng dễ theo dõi trên GUI.

---

## 🔬 KẾ HOẠCH XÁC MINH & CHẠY THỬ NGHIỆM

1. **Kiểm tra biên dịch cú pháp tự động**:
   ```powershell
   python -m compileall .
   ```
2. **Khởi chạy ứng dụng**:
   ```powershell
   python run_gui.py
   ```
   * Xác nhận range bin nhảy loạn lên cự ly xa (như 49, 53) được lọc bỏ hoàn toàn, radar giữ vững vùng đo thực tế của bạn.
   * Khi bạn di chuyển vị trí (ví dụ từ cự ly 1.5m sang 3.0m), kiểm tra log hiển thị dòng thông báo reset bộ đệm và chuyển bin thành công.
   * Quan sát chỉ số nhịp tim: Không còn bất kỳ cú nhảy vọt đột ngột lên 150 - 170 BPM nào nữa, nhịp tim duy trì sự ổn định tối đa.
