# KẾ HOẠCH TRIỂN KHAI NÂNG CẤP - PHIÊN BẢN v1.4.0 (TÍCH LŨY TOÀN BỘ SÓNG LỊCH SỬ KHÔI PHỤC TẦN SỐ LẤY MẪU GỐC)

Tài liệu này phân tích nguyên nhân gốc rễ của hiện tượng chênh lệch chỉ số nhịp tim lớn còn lại trong phiên bản `v1.3.0` dựa trên dữ liệu log thực tế thu thập được trong `vital_signs.csv` và đề xuất giải pháp xử lý triệt để cho phiên bản `v1.4.0`.

---

## 🔍 PHÂN TÍCH DỮ LIỆU THU THẬP & NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)

Dựa trên việc nghiên cứu tệp dữ liệu log thực tế [vital_signs.csv](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/logs/vital_signs.csv), chúng tôi phát hiện ra vấn đề cốt lõi gây ra sai lệch nhịp tim lớn như sau:

### 1. Chu kỳ gửi gói tin và mảng sóng lịch sử của Radar
* **Khám phá cấu trúc gói tin**:
  * Các dòng trong tệp `vital_signs.csv` có chỉ số `frame_number` tăng tiến cách nhau chính xác **16 frame** (16, 32, 48, 64, 80, 96, 112, ...).
  * Chênh lệch mốc thời gian thực tế `timestamp_s` giữa các gói tin nhận được là khoảng **1.44 giây** (tương đương $16 \times 90$ ms frame period).
  * Điều này khẳng định firmware trên chip chỉ gửi gói tin Vital Signs TLV (0x410) **mỗi 16 frame một lần** để tối ưu hóa băng thông UART, thay vì gửi liên tục ở từng frame.
  * Mỗi gói tin TLV gửi về chứa hai mảng dữ liệu lịch sử gồm **15 mẫu dạng sóng liên tiếp** (`heart_waveform_0` đến `heart_waveform_14` và `breath_waveform_0` đến `breath_waveform_14`).

### 2. Sai lầm nghiêm trọng trong cách tích lũy dữ liệu ở v1.2.0 / v1.3.0
* **Hiện tượng**: Trong file `app.py` của phiên bản `v1.3.0`, chúng ta chỉ thực hiện lấy mẫu cuối cùng của mảng lịch sử để tích lũy:
  ```python
  if sample.heart_waveform:
      self.accumulated_heart_waveform.append(sample.heart_waveform[-1])
  if sample.breath_waveform:
      self.accumulated_breath_waveform.append(sample.breath_waveform[-1])
  self.accumulated_timestamps.append(sample.timestamp_s)
  ```
* **Hậu quả (Aliasing cực nặng)**:
  * Vì ta chỉ lấy phần tử cuối cùng `[-1]` của mỗi gói tin, tức là trong khoảng thời gian **1.44 giây**, ta chỉ tích lũy đúng **1 mẫu dữ liệu** dạng sóng vào buffer!
  * Điều này làm giảm tần số lấy mẫu thực tế của chuỗi dữ liệu tích lũy xuống cực thấp: $f_{s\_actual} \approx 1 / 1.44 \approx 0.7$ Hz.
  * Theo định lý lấy mẫu Nyquist, tần số lấy mẫu 0.7 Hz chỉ có thể khôi phục các dao động có tần số tối đa là $0.35$ Hz (tương đương 21 BPM). Nhịp tim người bình thường dao động từ 55 - 140 BPM ($0.9$ - $2.3$ Hz), do đó hiện tượng **aliasing (chồng phổ)** cực kỳ nghiêm trọng đã xảy ra, làm méo dạng hoàn toàn tín hiệu nhịp tim và khiến NDTFT bị bão hòa ở biên cực đại 175 BPM!

---

## 🛠️ CHI TIẾT PHÁC THẢO GIẢI PHÁP NÂNG CẤP v1.4.0

### 1. Tích lũy toàn bộ mảng 15 mẫu dạng sóng lịch sử mỗi gói tin
* **Giải pháp**: Thay vì chỉ lấy mẫu cuối cùng `[-1]`, chúng ta sẽ duyệt qua toàn bộ mảng 15 mẫu dạng sóng (`sample.heart_waveform` và `sample.breath_waveform`) có trong mỗi gói tin TLV nhận về và đẩy toàn bộ vào các mảng tích lũy tương ứng.
* Điều này khôi phục đầy đủ và chính xác tín hiệu dạng sóng liên tục gốc với tần số lấy mẫu thực tế chuẩn của radar ($\approx 11.11$ Hz).

### 2. Nội suy trục thời gian thực tế chính xác cho từng mẫu lịch sử
* **Giải pháp**: 
  * Mốc thời gian nhận gói tin `sample.timestamp_s` tương ứng với mẫu cuối cùng trong mảng (chỉ số 14).
  * 15 mẫu dạng sóng được lấy mẫu đều cách nhau đúng $0.090$ giây (chu kỳ frame 90ms).
  * Ta sẽ nội suy mốc thời gian thực tế cho từng mẫu thứ $i$ ($i = 0 \dots 14$) trong gói tin theo công thức:
    $$t_i = \text{sample.timestamp\_s} - (14 - i) \times 0.090 \text{ giây}$$
  * Các timestamps nội suy chính xác này sẽ được tích lũy vào `accumulated_timestamps`.
  * Nhờ trục thời gian nội suy siêu chính xác này, thuật toán **NDTFT (Non-uniform DTFT)** sẽ hoạt động ở hiệu suất tối đa, loại bỏ hoàn toàn hiện tượng méo tần số do aliasing và jitter truyền thông, đảm bảo độ chính xác nhịp tim tuyệt đối so với Smartwatch.

---

## 📁 FILE SẼ CHỈNH SỬA TRONG v1.4.0

### 1. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)

* **Cập nhật phương thức `_handle_sample`**:
  * Đọc độ dài mảng dữ liệu lịch sử nhận được (thường là 15 mẫu).
  * Thực hiện vòng lặp duyệt qua tất cả mẫu lịch sử, tính toán timestamp nội suy tương ứng với khoảng cách frame 90ms.
  * Tích lũy các mẫu và timestamp nội suy này vào `self.accumulated_heart_waveform`, `self.accumulated_breath_waveform` và `self.accumulated_timestamps`.
  * Giới hạn kích thước buffer dùng vòng lặp `while len(...) > self.waveform_buffer_size: pop(0)` để đảm bảo giải phóng bộ nhớ cũ khi số mẫu tăng thêm 15 mẫu mỗi gói.
  * Tính toán lại tần số lấy mẫu thực tế động `fs_actual` dựa trên sự chênh lệch timestamps để cung cấp chỉ số chính xác nhất cho DSP.

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
   * Xác nhận buffer tích lũy hoạt động mượt mà, không bị lag giao diện.
   * Quan sát đồ thị nhịp tim hiển thị: tín hiệu dạng sóng thô và mịn được vẽ đầy đủ, chi tiết, không còn bị đứt quãng.
   * Đo đạc và xác nhận chỉ số nhịp tim hội tụ chính xác, ổn định ở dải 60 - 90 BPM (khi nghỉ ngơi), sai lệch so với Smartwatch nằm trong khoảng cực nhỏ **±1 đến ±3 BPM**.
