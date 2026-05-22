# KẾ HOẠCH TRIỂN KHAI NÂNG CẤP - PHIÊN BẢN v1.3.0 (ĐỒNG BỘ RANGE BIN ĐỘNG & DTFT KHÔNG ĐỀU KHỬ JITTER)

Tài liệu này phân tích nguyên nhân gốc rễ của hiện tượng chênh lệch chỉ số nhịp tim cực lớn (nhảy lên cận trên 175 BPM) dựa trên dữ liệu vận hành thực tế và đề xuất giải pháp xử lý triệt để cho phiên bản `v1.3.0`.

---

## 🔍 PHÂN TÍCH NGUYÊN NHÂN GỐC RỄ (ROOT CAUSE ANALYSIS)

Dựa trên hình ảnh giao diện đang hoạt động thực tế do người dùng cung cấp, chúng tôi đã phát hiện ra hai vấn đề cốt lõi nghiêm trọng gây ra sự sai lệch nhịp tim lớn này:

### 1. Lệch Range Bin giữa cấu hình Radar và vị trí Target thực tế
* **Hiện tượng**: Thanh trạng thái hiển thị người đo đang được tracker bám bắt ở `Range bin: 13` (khoảng cách khoảng $3.25$ m). Tuy nhiên, tệp cấu hình radar gửi đi `vital_signs_AOP_6m.cfg` lại thiết lập cứng lệnh `VSRangeIdxCfg 0 21` (đo nhịp tim ở range bin 21, tương ứng $5.25$ m, nơi hoàn toàn không có người).
* **Hệ quả**: 
  * Radar cố gắng trích xuất tín hiệu nhịp tim từ một vùng không gian trống rỗng, dẫn đến dữ liệu dạng sóng thu được hoàn toàn là nhiễu trắng tĩnh.
  * Vì dữ liệu quá nhiễu, thuật toán kiểm duyệt trên chip liên tục đánh dấu dữ liệu không hợp lệ. Điều này khiến số lượng gói tin Vital Signs nhận được qua UART (`vital_tlvs`) cực kỳ ít (chỉ có `113` gói trong tổng số `1822` frame, tức là trung bình khoảng **1.4 giây mới nhận được 1 gói** thay vì 11 gói mỗi giây).
  * Chuỗi dữ liệu dạng sóng tích lũy trên GUI bị đứt đoạn và thưa thớt trầm trọng.

### 2. Mất đồng bộ tần số lấy mẫu ($fs$) và Jitter truyền thông UART
* **Hiện tượng**: Trong phiên bản `v1.2.0`, thuật toán DSP thứ cấp nâng cao giả định tần số lấy mẫu cố định là `fs = 20.0 Hz` (khoảng cách mẫu 50ms).
* **Hệ quả**:
  * Khi tốc độ nhận gói tin thực tế bị kéo giãn ra tới **1.4 giây/gói** do lệch range bin, thuật toán DSP vẫn giả định các mẫu cách nhau 50ms. Điều này làm cho trục thời gian bị co lại gần **28 lần**, khiến tần số của nhiễu bị phóng đại lên 28 lần và luôn vượt quá giới hạn đo, dẫn đến nhịp tim hiển thị bị bão hòa ở biên trên cực đại là **175.0 BPM** hoặc **180.0 BPM**.
  * Ngay cả khi range bin khớp, việc truyền thông qua USB-UART trên hệ điều hành Windows luôn có độ trễ không đều (jitter). Việc giả định khoảng cách mẫu đều tăm tắp gây ra sai số tích lũy pha trong biến đổi Fourier.

---

## 🛠️ CHI TIẾT PHÁC THẢO GIẢI PHÁP NÂNG CẤP v1.3.0

### 1. Tự động đồng bộ hóa Range Bin của Radar thời gian thực (Dynamic Range Bin Sync)
* **Giải pháp**: Thiết lập cơ chế tự động theo dõi Range bin của Target đang hoạt động (`sample.range_bin`). 
* Nếu phát hiện range bin đo của radar khác với range bin thực tế của target, ứng dụng GUI sẽ tự động gửi lệnh cập nhật `VSRangeIdxCfg 0 {sample.range_bin}\n` qua cổng CFG port bằng một luồng chạy phụ bất đồng bộ (`threading.Thread`) để tránh làm đơ giao diện.
* **Cơ chế chống rung (Cooldown)**: Giới hạn tần suất gửi lệnh tối đa **1 lần mỗi 5 giây** để bảo vệ cổng serial và tránh xung đột khi range bin của target bị dao động nhẹ giữa hai bin liền kề.

### 2. Thuật toán NDTFT (Non-uniform DTFT) khử Jitter và thích ứng tần số lấy mẫu động
* **Giải pháp**: 
  * Tích lũy thêm mảng mốc thời gian thực nhận gói tin `accumulated_timestamps` song song với các mảng dạng sóng.
  * Tự động tính toán tần số lấy mẫu thực tế động `fs_actual` dựa trên khoảng thời gian trung bình thực tế giữa các mẫu.
  * Thay thế trục thời gian giả định đều bằng trục thời gian thực tế `t_history = accumulated_timestamps - accumulated_timestamps[0]`.
  * Áp dụng thuật toán **NDTFT (Biến đổi Fourier rời rạc không đều)** sử dụng chính trục thời gian thực tế để tính toán phổ tần nhịp tim/nhịp thở. Phép tính này triệt tiêu hoàn toàn sai số do jitter UART và sự không đồng đều của tốc độ nhận gói tin.

---

## 📁 CÁC FILE SẼ CHỈNH SỬA TRONG v1.3.0

### 1. [MODIFY] [dsp_advanced.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/dsp_advanced.py)
* Cập nhật chữ ký hàm `filter_and_estimate_hr` và `estimate_br` để nhận thêm tham số `fs` động và mảng trục thời gian thực tế `t_history`.
* Áp dụng `t_history` trực tiếp vào công thức lũy thừa phức của DTFT để tính phổ tần không đều chính xác tuyệt đối.

### 2. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)
* Import thêm thư viện `threading` và `serial`.
* Khởi tạo biến theo dõi `self.current_radar_range_bin = None`, `self.last_range_bin_update_time = 0.0` và hàng đợi mốc thời gian `self.accumulated_timestamps = []`.
* Viết phương thức truyền lệnh bất đồng bộ `_update_radar_range_bin`.
* Trong `_handle_sample`: Tích lũy timestamp, tính toán `fs_actual` động, kiểm tra và tự động gửi lệnh đồng bộ Range bin khi lệch kèm cooldown 5 giây. Truyền trục thời gian thực tế vào bộ xử lý DSP.

---

## 🔬 KẾ HOẠCH XÁC MINH & CHẠY THỬ NGHIỆM

1. **Kiểm tra biên dịch cú pháp tự động**:
   ```powershell
   python -m compileall .
   ```
2. **Khởi chạy ứng dụng và kiểm tra hoạt động**:
   ```powershell
   python run_gui.py
   ```
   * Xác nhận luồng gửi lệnh cấu hình động hoạt động trơn tru qua cổng CFG khi phát hiện target.
   * Xác nhận số lượng `vital_tlvs` nhận được tăng vọt và liên tục.
   * Xác nhận chỉ số nhịp tim hội tụ chính xác về giá trị thực tế của cơ thể và khớp với smartwatch.
