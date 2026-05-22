# KẾ HOẠCH TRIỂN KHAI & PHÂN TÍCH CHI TIẾT MÃ NGUỒN - PHIÊN BẢN v1.0.0 (BẢN GỐC)

Tài liệu này chứa toàn bộ kết quả phân tích mã nguồn hiện tại của dự án **IWR6843AOP Vital Sign Monitor** ở phiên bản đầu tiên (`v1.0.0`).

---

## 📌 QUY TẮC PHÁT TRIỂN & CẬP NHẬT (HÃY TUÂN THỦ NGHIÊM NGẶT)
1. **BẢO TOÀN MÃ NGUỒN**: Không tự ý xóa bất kỳ file nào trong thư mục dự án khi chưa có lệnh rõ ràng từ người dùng.
2. **QUẢN LÝ PHIÊN BẢN (VERSION CONTROL)**: Sau mỗi lần cập nhật mã nguồn hoặc phác thảo ý tưởng nâng cấp, tạo một file Implementation Plan riêng biệt cho phiên bản đó (ví dụ: `implementation_plan_v1.md`, `implementation_plan_v1.1.md`) để theo dõi sát sao tiến trình phát triển.
3. **CHẠY THỬ NGHIỆM PREVIEW**: Sau khi hoàn thành các cập nhật mã nguồn, thực hiện chạy thử nghiệm (Preview/Dry Run) 1 lần để đảm bảo tính đúng đắn trước khi bàn giao và chờ lệnh của người dùng chạy file chính thức.

---

## 🔍 PHÂN TÍCH KIẾN TRÚC MÃ NGUỒN GỐC (v1.0.0)

Ứng dụng được thiết kế trên mô hình **Multithreaded GUI (Giao diện đa luồng)** sử dụng Python, kết nối song song 2 cổng Serial của thiết bị **TI IWR6843AOP EVM**:
1. **CFG/CLI Port (115200 baud)**: Dùng để truyền các lệnh cấu hình radar từ file cấu hình `.cfg`.
2. **DATA Port (921600 baud)**: Dùng để nhận luồng nhị phân chứa các gói tin dữ liệu sinh tồn thời gian thực.

### 1. Bản đồ Cấu trúc Dự án
```text
Vital Sign/
├── run_gui.py                # Điểm khởi chạy ứng dụng chính (gọi vital_signs.app.main())
├── requirements.txt          # Khai báo thư viện: pyserial (giao tiếp serial), matplotlib (vẽ đồ thị), numpy (tính toán toán học)
├── config/                   # Thư mục lưu trữ cấu hình radar của TI (.cfg)
│   ├── PUT_CFG_HERE.txt      # Tệp hướng dẫn lấy chirp profile từ TI Radar/Industrial Toolbox
│   └── vital_signs_AOP_6m.cfg # File cấu hình chirp mẫu cho cự ly 6 mét
├── doc/                      # Thư mục chứa tài liệu hướng dẫn và kế hoạch (Thư mục mới tạo)
│   └── implementation_plan_v1.md # File tài liệu Kế hoạch triển khai & Phân tích này
└── vital_signs/              # Package chứa toàn bộ mã nguồn xử lý logic
    ├── __init__.py           # Khai báo python package
    ├── app.py                # Lớp VitalSignMonitorApp (Tkinter GUI + Matplotlib Canvas)
    ├── config_sender.py      # Xử lý gửi tệp .cfg qua cổng serial với khoảng trễ lệnh 50ms
    ├── csv_logger.py         # Module ghi logs dữ liệu sinh tồn ra tệp CSV dạng bảng
    ├── mmwave_parser.py      # Bộ phân tích gói nhị phân mmWave TLV (trích xuất TLV 0x410)
    └── serial_worker.py      # Luồng nền SerialWorker (Thread) đọc dữ liệu nhị phân không gây đơ GUI
```

---

### 2. Phân tích Chi tiết Hoạt động của các Module chính

#### 2.1. Module Parser (`vital_signs/mmwave_parser.py`)
Bộ phân tích cú pháp stream nhị phân hoạt động theo cơ chế **Streaming State Machine**:
* **Magic Word**: Tìm kiếm signature byte đặc trưng của TI mmWave: `0x02 0x01 0x04 0x03 0x06 0x05 0x08 0x07`.
* **Frame Header Parsing**: Giải mã phần tiêu đề dài 40 bytes để lấy `frame_number`, `total_packet_len`, và `num_tlvs`.
* **TLV Traversal**: Duyệt qua từng khối dữ liệu TLV (Type-Length-Value). Khi phát hiện `tlv_type == 0x410` (Vital Signs TLV), chương trình sẽ giải nén payload nhị phân 136 bytes bằng `struct.unpack_from` định dạng kiểu dữ liệu Little-Endian `<HHfff15f15f`:
  - `target_id` (uint16)
  - `range_bin` (uint16)
  - `breathing_deviation` (float)
  - `heart_rate_bpm` (float)
  - `breathing_rate_bpm` (float)
  - `heart_waveform` (15 floats - dạng sóng tim)
  - `breath_waveform` (15 floats - dạng sóng thở)

Ràng buộc tính hợp lệ của chỉ số đo:
* Nhịp tim hợp lệ: Từ 25.0 đến 240.0 BPM.
* Nhịp thở hợp lệ: Từ 2.0 đến 80.0 BPM.

#### 2.2. Luồng Nền Bất Đồng Bộ (`vital_signs/serial_worker.py`)
* Chạy dưới dạng một `threading.Thread` độc lập để không làm nghẽn Main Thread của Tkinter GUI.
* Khởi động gửi cấu hình `.cfg` đến cảm biến bằng `send_config()`.
* Mở cổng DATA Serial ở tốc độ rất cao `921600` baud.
* Vòng lặp `while` liên tục đọc tối đa `4096` bytes mỗi chu kỳ, đẩy trực tiếp vào bộ đệm của parser.
* Sử dụng hàng đợi Thread-safe `queue.Queue` để đẩy các mẫu dữ liệu `VitalSignsSample` giải mã được và các dòng nhật ký trạng thái (logs) về cho GUI tiêu thụ.

#### 2.3. Giao diện Người dùng (`vital_signs/app.py`)
* Kế thừa từ `tk.Tk` để xây dựng giao diện ứng dụng.
* Vẽ 3 đồ thị trực quan bằng Matplotlib:
  1. Đồ thị xu hướng biến thiên nhịp tim & nhịp thở theo thời gian (tối đa 600 điểm lịch sử).
  2. Đồ thị dạng sóng nhịp tim thời gian thực (Circular Buffer).
  3. Đồ thị dạng sóng nhịp thở thời gian thực (Circular Buffer).
* Vòng lặp giao diện: Sử dụng phương thức `.after(100, self._update_ui_loop)` chạy định kỳ mỗi 100 miligiây để kiểm tra và lấy dữ liệu mới từ các hàng đợi (`samples` và `logs`) của `SerialWorker`, sau đó tự động cập nhật lên giao diện và vẽ lại đồ thị.

---

## 📈 BẢNG QUẢN LÝ LỊCH SỬ CÁC PHIÊN BẢN (VERSION CONTROL LOG)

Tất cả các bản nâng cấp, sửa đổi mã nguồn hoặc các tài liệu phác thảo kiến trúc mã nguồn sẽ được theo dõi chặt chẽ tại đây:

| Phiên bản | Ngày cập nhật | Tác giả | Nội dung thay đổi chi tiết | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| **v1.0.0** | 2026-05-22 | Antigravity AI | - Hoàn thành rà soát toàn bộ cấu trúc mã nguồn dự án.<br>- Thiết lập thư mục tài liệu `doc/` và tạo file Kế hoạch triển khai `implementation_plan_v1.md`. | **Hiện hành** |

---

## 🔬 KẾ HOẠCH XÁC MINH & CHẠY THỬ NGHIỆM (VERIFICATION PLAN)

Để đảm bảo các thay đổi tiếp theo hoạt động hoàn hảo và không gây lỗi cú pháp:

### 1. Kiểm tra Cú pháp Tự động (Syntax Compiling)
Trước khi chạy chương trình, thực hiện biên dịch thử tất cả các file Python để kiểm tra lỗi cú pháp bằng lệnh:
```powershell
python -m compileall .
```

### 2. Chạy Preview (Khởi chạy giao diện thử nghiệm)
Sau khi mã nguồn được cập nhật và biên dịch thành công, chúng ta sẽ khởi chạy ứng dụng ở chế độ xem trước (Preview) bằng lệnh:
```powershell
python run_gui.py
```
* **Mục tiêu của Preview**: Xác nhận cửa sổ GUI Tkinter hiển thị đầy đủ, Matplotlib tích hợp vẽ các lưới trục đồ thị chính xác mà không gặp lỗi khởi tạo, và các thành phần nút bấm/cổng kết nối hoạt động ổn định.
