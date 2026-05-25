# KẾ HOẠCH TRIỂN KHAI v2.0 - KIẾN TRÚC DSP ĐA TẦNG SIÊU PHÂN GIẢI KHỬ HÀI HÔ HẤP THÍCH ỨNG
## (ADVANCED BIO-SIGNAL FUSION DSP PIPELINE & MULTI-HARMONIC RLS & NDTFT HARMONIC MASKING)

Tài liệu này chi tiết hóa kế hoạch nghiên cứu lý thuyết, tổng hợp và đề xuất kiến trúc xử lý tín hiệu sinh tồn thế hệ mới (**v2.0**) dựa trên việc nghiên cứu sâu tệp tài liệu kỹ thuật [Tong_hop_nghien_cuu_Radar_va_Vital_Sign.docx](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/Tong_hop_nghien_cuu_Radar_va_Vital_Sign.docx) và các công trình khoa học đỉnh cao (Scientific Reports 2024/2025).

---

## 🔍 TỔNG HỢP NGHIÊN CỨU & KHẢO SÁT LÝ THUYẾT (LITERATURE RESEARCH SYNTHESIS)

Từ bản tổng hợp tài liệu kỹ thuật, chúng tôi rút ra 3 luận điểm cốt lõi làm kim chỉ nam cho sự phát triển của hệ thống Vital Signs đo bằng Radar mmWave IWR6843AOP:

### 1. Bản chất Vật Lý & Thách thức cực đại của Nhịp Tim (Heart Rate)
* **Dao động cơ học cực yếu**: Biên độ dao động lồng ngực do thở dao động từ vài mm đến hơn $1\text{ cm}$. Ngược lại, dao động vi mô do tim đập (heartbeat) chỉ ở mức **sub-mm (dưới 1mm, thường từ 0.01mm - 0.2mm)**. Do đó, tín hiệu tim đập dễ dàng bị "chìm" hoàn toàn trong nhiễu và chuyển động thở.
* **Xuyên nhiễu hài hô hấp (Respiratory Harmonics)**: Đây là nguyên nhân hàng đầu gây sai lệch nhịp tim. Nhịp thở bình thường nằm ở dải tần $0.1 - 0.5\text{ Hz}$ ($6 - 30\text{ BPM}$). Các hài bậc cao của nhịp thở (hài bậc 2, bậc 3, bậc 4) sẽ rơi trực tiếp vào dải tần số của nhịp tim ($0.8 - 2.0\text{ Hz}$ tương đương $48 - 120\text{ BPM}$).
  > [!WARNING]
  > *Ví dụ*: Một người thở với nhịp $0.33\text{ Hz}$ ($19.8\text{ BPM}$). Hài bậc 3 của nhịp thở này nằm ở $0.33 \times 3 = 0.99\text{ Hz}$ ($59.4\text{ BPM}$) hoặc hài bậc 4 nằm ở $1.32\text{ Hz}$ ($79.2\text{ BPM}$). Phổ FFT thông thường sẽ nhầm lẫn các đỉnh hài hô hấp này là nhịp tim thật, dẫn tới hiện tượng nhịp tim hiển thị bị "khóa" vào bội số nhịp thở.

### 2. Các giải pháp đột phá từ các nghiên cứu gần đây (2024 - 2025)
* **Chen và các cộng sự (Scientific Reports, 2024)**: Đề xuất loại bỏ DC baseline bằng bộ lọc trung vị (Median Filter), tăng cường độ hội tụ thông qua thuật toán lọc thích ứng **RLS (Recursive Least Squares)** và nâng cao phổ nhịp tim yếu bằng thuật toán siêu phân giải **DR-MUSIC (Dimension Reduction MUSIC)**.
* **Hao và các cộng sự (Scientific Reports, 2025)**: Sử dụng toán tử vi phân pha (**Phase Differencing**), chuẩn hóa căn bậc hai (**Square-root Normalization**) để cân bằng biên độ ở các cự ly/tư thế khác nhau, kết hợp biến đổi Wavelet (DWT) và bộ lọc **Adaptive Kalman Filter** để tự động thích ứng với chuyển động cơ thể.

---

## 💡 GIẢI PHÁP ĐỀ XUẤT THẾ HỆ MỚI v2.0 (THE OUT-OF-THE-BOX HYBRID ARCHITECTURE)

Để giải quyết triệt để các vấn đề trên mà không bị bó buộc vào lối mòn kỹ thuật, phiên bản **v2.0** đề xuất kiến trúc xử lý tín hiệu **"Advanced Bio-Signal Fusion DSP Pipeline"** kết hợp 5 đột phá thuật toán cốt lõi:

### Sơ đồ luồng xử lý (DSP Pipeline Workflow)
```
[Raw Accumulated Waveforms] 
           │
           ▼
[Square-root Normalization & Detrending] (Khử baseline & cân bằng cự ly)
           │
           ▼
[Phase Differencing & High-Pass Enhancement] (Boost dao động tim vi mô)
           │
           ▼
[Multi-Harmonic RLS Adaptive Filter] (Triệt tiêu hài thở bậc 2, 3 bằng RLS)
           │
           ▼
[Fine-grid Non-uniform DTFT] (Phân tích tần số mịn 0.1 BPM)
           │
           ▼
[Respiration Harmonic Suppression RHS Masking] (Mặt nạ che nhiễu hài thở)
           │
           ▼
[Frequency Peak Identification & Peak PAR] (Trích xuất đỉnh và Confidence)
           │
           ▼
[Quality-Aware Adaptive Kalman Filter] (Làm mượt động theo Confidence)
           │
           ▼
[Stable Dynamic Heart & Breath BPM]
```

### 1. Chuẩn hóa Căn Bậc Hai & Khử Baseline tự động (Square-root Normalization & Detrending)
* **Ý tưởng sáng tạo**: Thay vì chỉ dùng bộ lọc High-pass dễ gây méo pha ở biên tần số thấp, chúng tôi kết hợp phép trừ tín hiệu chạy trung bình (moving average) để detrend. Đồng thời, áp dụng chuẩn hóa biên độ thích ứng dựa trên căn bậc hai của phương sai cục bộ:
  $$\tilde{x}(t) = \frac{x(t) - \mu_x}{\sqrt{\sigma_x^2 + \epsilon}}$$
  Giúp giữ biên độ sóng ổn định kể cả khi đối tượng dịch chuyển nhẹ hoặc thay đổi cự ly so với radar.

### 2. Toán tử Vi Phân Pha (Phase Differencing)
* **Ý tưởng sáng tạo**: Thực hiện đạo hàm bậc một (phép sai phân $y[n] = x[n] - x[n-1]$) trực tiếp lên chuỗi pha nhịp tim.
* **Hiệu quả vật lý**: Sai phân tương đương một bộ lọc High-pass tự nhiên có đáp ứng tỉ lệ thuận với tần số ($H(f) \propto f$). Nó giúp làm suy hao cực mạnh các thành phần tần số rất thấp (nhịp thở gốc) và đồng thời nhân khuếch đại (boost) các dao động tần số cao (nhịp tim vi mô).

### 3. Bộ lọc thích ứng RLS Đa Hài (Multi-Harmonic Recursive Least Squares Filter)
* **Sự vượt trội so với LMS**: Bộ lọc LMS hiện tại trong `v1.5.0` hội tụ rất chậm và nhạy cảm với việc tuning hệ số học $\mu$. Chúng tôi thay thế hoàn toàn bằng **RLS (Recursive Least Squares)** với tốc độ hội tụ cực nhanh (chỉ cần vài chu kỳ dao động) và khả năng thích ứng pha xuất sắc.
* **Chiến thuật Đa Hài (Multi-Harmonic Reference)**: Thay vì chỉ lấy sóng thở làm nhiễu tham chiếu đơn lẻ, chúng tôi xây dựng vector nhiễu tham chiếu đa chiều bao gồm:
  $$\mathbf{X}_{ref}(t) = \left[ x_{br}(t), \quad x_{br}^2(t), \quad x_{br}(t-1), \quad x_{br}^2(t-1) \right]^T$$
  Phép dựng bình phương sóng thở ($x_{br}^2(t)$) đại diện trực tiếp cho **Hài bậc 2 của nhịp thở** trong miền thời gian! Bộ lọc RLS sẽ tự động tìm trọng số tối ưu để triệt tiêu cả nhịp thở gốc lẫn hài bậc 2 ra khỏi dạng sóng tim.

### 4. Mặt nạ Triệt tiêu Hài Hô Hấp trên phổ NDTFT (Respiration Harmonic Suppression Masking)
* Kể cả sau khi lọc RLS, tàn dư hài hô hấp vẫn có thể sót lại nếu nhịp thở quá mạnh. Chúng tôi thiết lập cơ chế **Harmonic Suppression Masking** trên phổ NDTFT tần số mịn:
  1. Xác định tần số thở chính xác nhất $f_{br}$ từ phổ thở.
  2. Định vị các vùng nhiễu hài hô hấp lý thuyết trên phổ tim: $2 \times f_{br}$ và $3 \times f_{br}$.
  3. Tạo một mặt nạ lọc dạng hình chuông ngược (Inverse-Gaussian Notch Mask) quanh các tần số hài này với độ rộng sinh lý ($\pm 0.12\text{ Hz}$):
     $$M(f) = 1.0 - \sum_{k=2}^{3} \exp\left( -\frac{(f - k \cdot f_{br})^2}{2 \cdot \sigma_h^2} \right)$$
  4. Nhân trực tiếp mặt nạ này vào phổ năng lượng NDTFT nhịp tim trước khi tìm đỉnh cực đại (peak frequency). Điều này ngăn chặn tuyệt đối tình trạng chọn nhầm đỉnh hài thở làm nhịp tim.

### 5. Bộ lọc Kalman Thích ứng theo Chất lượng Tín hiệu (Quality-Aware Adaptive Kalman Filter)
* Thay vì sử dụng các giá trị tĩnh $Q$ và $R$ cho bộ lọc Kalman ở phần ổn định (`dsp_filters.py`), chúng tôi nâng cấp lên bộ lọc Kalman thích ứng.
* **Tham số hóa R động (Dynamic Measurement Noise)**:
  * Tính toán chỉ số chất lượng phổ nhịp tim **Spectral Peak-to-Average Ratio (PAR)** từ phổ NDTFT.
  * Nếu phổ tim có đỉnh sắc nét (PAR cao), tín hiệu đáng tin $\rightarrow$ giảm $R$ để bám sát tức thời.
  * Nếu phổ tim phẳng, nhiều đỉnh nhiễu (PAR thấp) hoặc độ lệch nhịp thở (`breathing_deviation`) vượt ngưỡng $\rightarrow$ tăng mạnh $R$ để kích hoạt cơ chế giữ trạng thái và trơn hóa cao, bảo vệ nhịp tim không bị vọt/nhảy loạn.

---

## 📁 DANH SÁCH FILE CẦN THAY ĐỔI TRONG v2.0 (PROPOSED CHANGES)

### 1. [MODIFY] [dsp_advanced.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/dsp_advanced.py)
* **Nhiệm vụ**:
  * Hiện thực hóa lớp `RLSFilter` thay thế cho `LMSFilter`.
  * Nâng cấp `AdvancedVitalSignsDSP` tích hợp:
    * Chuẩn hóa căn bậc hai và detrending.
    * Sai phân pha (`np.diff`).
    * Vector tham chiếu đa hài cho RLS.
    * Thuật toán tạo mặt nạ lọc hài thở thích ứng (Harmonic Suppression Mask) trên phổ NDTFT.
    * Trả về thêm chỉ số chất lượng tín hiệu phổ nhịp tim (Heart Peak Confidence/PAR).

### 2. [MODIFY] [dsp_filters.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/dsp_filters.py)
* **Nhiệm vụ**:
  * Nâng cấp bộ lọc `KalmanFilter1D` để hỗ trợ cập nhật động sai số đo $R$ ở mỗi bước: `update(measurement, R_dynamic)`.
  * Cập nhật `VitalSignStabilizer` để tính toán $R_{dynamic}$ cho tim và phổi dựa trên chỉ số tự tin từ phổ NDTFT và độ biến thiên thở thực tế.

### 3. [MODIFY] [app.py](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/vital_signs/app.py)
* **Nhiệm vụ**:
  * Cập nhật luồng nhận và giải mã để tích hợp đầy đủ các giá trị đầu ra mới từ `AdvancedVitalSignsDSP` (bao gồm cả chỉ số confidence/PAR) đưa vào `VitalSignStabilizer`.
  * Trực quan hóa thêm chỉ số tự tin đo (Confidence Score) trên giao diện GUI để tăng tính chuyên nghiệp và minh bạch thông tin đo đạc cho người dùng.

### 4. [MODIFY] [implementation_plan.md](file:///c:/Users/Lirrak/Documents/Born%20Again/Radar%20Project/IWR6843AOP/Vital%20Sign/doc/implementation_plan.md)
* **Nhiệm vụ**: Cập nhật mục lục và bảng quản lý lịch sử phiên bản để bổ sung kế hoạch thiết kế kiến trúc xử lý nâng cao `v2.0` này.

---

## 🛠️ CHI TIẾT HIỆN THỰC THUẬT TOÁN (ALGORITHMIC BLUEPRINT IN PYTHON)

Dưới đây là thiết kế chi tiết bằng mã Python cho các lớp thuật toán cốt lõi để đảm bảo hiệu quả thực thi tối đa chỉ với thư viện nền `numpy`:

### Lớp RLSFilter (Recursive Least Squares) thay thế LMS
```python
class RLSFilter:
    """Recursive Least Squares (RLS) adaptive filter for rapid convergence."""
    def __init__(self, num_taps: int = 4, lmbda: float = 0.99, delta: float = 0.1) -> None:
        self.num_taps = num_taps
        self.lmbda = lmbda  # Forgetting factor
        self.w = np.zeros(num_taps)
        self.P = np.eye(num_taps) / delta  # Inverse correlation matrix

    def process(self, x_vector: np.ndarray, d_sample: float) -> float:
        """Process a sample vector x_vector and primary sample d_sample.
        x_vector: multi-dimensional noise reference (e.g. breath, breath^2, etc.)
        """
        u = x_vector
        
        # Predict noise
        y = np.dot(self.w, u)
        error = d_sample - y
        
        # RLS Gain Vector Update
        pi_vec = np.dot(self.P, u)
        gain = pi_vec / (self.lmbda + np.dot(u, pi_vec))
        
        # Update weights and covariance matrix
        self.w += gain * error
        self.P = (self.P - np.outer(gain, np.dot(u, self.P))) / self.lmbda
        
        return error

    def reset(self) -> None:
        self.w.fill(0.0)
        self.P = np.eye(self.num_taps) / 0.1
```

### Hàm Lọc & Ước Lượng Nhịp Tim Nâng Cao trong `dsp_advanced.py`
```python
def filter_and_estimate_hr_v2(
    self, 
    heart_history: np.ndarray, 
    breath_history: np.ndarray, 
    fs: float, 
    t_history: np.ndarray
) -> Tuple[float, float]:
    """Advanced Secondary DSP pipeline with Multi-Harmonic RLS & RHS NDTFT Masking.
    
    Returns:
        best_bpm: float - Estimated heart rate in BPM.
        confidence: float - Spectrum quality indicator (PAR value, e.g. 1.0 to 10.0+).
    """
    n = len(heart_history)
    if n < 64:
        return 72.0, 1.0

    # 1. Square-Root Normalization & Detrend
    breath_detrend = breath_history - np.median(breath_history)
    breath_norm = breath_detrend / (np.sqrt(np.var(breath_detrend) + 1e-6))
    
    heart_detrend = heart_history - np.median(heart_history)
    heart_norm = heart_detrend / (np.sqrt(np.var(heart_detrend) + 1e-6))

    # 2. Phase Differencing (Sai phân pha để làm nổi bật nhịp tim, triệt tiêu thở)
    diff_heart = np.diff(heart_norm, prepend=heart_norm[0])
    
    # 3. Butterworth-equivalent Spectral Bandpass Filtering via FFT
    # Respiration band: 0.1 to 0.6 Hz
    b_fft = np.fft.fft(breath_norm)
    freqs = np.fft.fftfreq(n, d=1.0/fs)
    b_fft[(np.abs(freqs) < 0.1) | (np.abs(freqs) > 0.6)] = 0
    clean_breath = np.real(np.fft.ifft(b_fft))
    
    # Heart band: 0.75 to 3.0 Hz
    h_fft = np.fft.fft(diff_heart)
    h_fft[(np.abs(freqs) < 0.75) | (np.abs(freqs) > 3.0)] = 0
    bp_heart = np.real(np.fft.ifft(h_fft))

    # 4. Multi-Harmonic RLS Adaptive Respiration Noise Cancellation
    self.rls.reset()
    clean_heart = np.zeros_like(bp_heart)
    for i in range(n):
        b_val = clean_breath[i]
        b_prev = clean_breath[max(0, i-1)]
        # Vector tham chiếu hài: [Thở, Thở^2, Thở trễ 1 mẫu, Thở^2 trễ 1 mẫu]
        x_ref = np.array([b_val, b_val**2, b_prev, b_prev**2])
        clean_heart[i] = self.rls.process(x_ref, bp_heart[i])

    # 5. Fine-Grid Non-uniform DTFT
    phase_matrix = -2j * np.pi * np.outer(self.hr_freqs, t_history)
    dtft_vals = np.dot(np.exp(phase_matrix), clean_heart)
    power_spectrum = np.abs(dtft_vals) ** 2

    # 6. Tìm nhịp thở để xác định tần số hài hô hấp
    br_phase_matrix = -2j * np.pi * np.outer(self.br_freqs, t_history)
    br_dtft_vals = np.dot(np.exp(br_phase_matrix), clean_breath)
    br_power = np.abs(br_dtft_vals) ** 2
    best_br_idx = np.argmax(br_power)
    f_br = self.br_freqs[best_br_idx]  # Tần số thở cơ bản (Hz)

    # 7. Áp dụng Respiration Harmonic Suppression (RHS) Masking
    # Che phủ hài bậc 2 (2 * f_br) và hài bậc 3 (3 * f_br)
    mask = np.ones_like(self.hr_freqs)
    sigma_h = 0.08  # Băng thông sinh lý che hài (~5 BPM)
    for harmonic_k in [2, 3]:
        f_harmonic = harmonic_k * f_br
        harmonic_mask = 1.0 - np.exp(-((self.hr_freqs - f_harmonic) ** 2) / (2 * (sigma_h ** 2)))
        mask *= harmonic_mask
        
    masked_spectrum = power_spectrum * mask

    # 8. Trích xuất nhịp tim và tính toán confidence (Peak-to-Average Ratio)
    best_idx = np.argmax(masked_spectrum)
    best_bpm = self.hr_bpms[best_idx]
    
    mean_power = np.mean(masked_spectrum)
    peak_power = masked_spectrum[best_idx]
    confidence = float(peak_power / (mean_power + 1e-9))  # PAR indicator

    return float(best_bpm), confidence
```

---

## 🔬 KẾ HOẠCH XÁC MINH (VERIFICATION PLAN)

Để chứng minh tính hiệu quả vượt trội và độ ổn định của kiến trúc thế hệ mới **v2.0**, chúng tôi thiết lập quy trình kiểm thử chi tiết sau:

### 1. Kiểm thử Logic thuật toán giả lập (Offline Validation)
* **Kịch bản kiểm thử**: Thiết kế script python giả lập trong thư mục `scratch/` để tạo luồng tín hiệu tổng hợp:
  * Dao động ngực do thở ($0.25\text{ Hz}$ - $15\text{ BPM}$) kèm hài bậc 2 mạnh ($0.5\text{ Hz}$) và hài bậc 3 rất mạnh ($0.75\text{ Hz}$).
  * Dao động tim đập yếu ($1.2\text{ Hz}$ - $72\text{ BPM}$) bị chồng chập lên nhau.
  * Thêm nhiễu ngẫu nhiên Gaussian trắng SNR = $-5\text{ dB}$.
* **Tiêu chuẩn vượt qua (Pass Criteria)**: Thuật toán `v2.0` phải bóc tách thành công nhịp tim **$72.0 \pm 1.0\text{ BPM}$**, trong khi thuật toán cũ bị "bắt nhầm" vào đỉnh hài bậc 3 ($0.75\text{ Hz} \rightarrow 45\text{ BPM}$) hoặc hài bậc 4 ($1.0\text{ Hz} \rightarrow 60\text{ BPM}$).

### 2. Kiểm thử Tích hợp Thực tế (Online Verification)
* **Chạy ứng dụng**: Kích hoạt giao diện đồ họa thông qua `python run_gui.py`.
* **Đo đạc thực tế**: 
  1. Người dùng ngồi yên trước radar ở các cự ly $1.0\text{m}$, $2.0\text{m}$ và $3.5\text{m}$.
  2. Bật đồng thời Smartwatch hoặc đai đo tim đeo ngực Polar làm tham chiếu đối chứng chuẩn.
  3. Quan sát biến số `confidence` trên terminal/GUI: Khi ngồi yên thở đều, `confidence` đạt giá trị cao ($> 4.0$). Khi người dùng chuyển động mạnh hoặc rời đi, `confidence` giảm mạnh xuống sát $1.0$, hệ thống lập tức đóng băng (freeze) hiển thị nhịp tim hoặc đưa ra thông báo "Signal Weak / Motion Detected" thay vì tính toán giá trị rác.
  4. Xác nhận sự liên tục, không bị giật cục hoặc lệch bước đo nhịp tim khi so sánh trực tiếp với smartwatch.

---

> [!NOTE]
> Bản kế hoạch này mở ra một chương mới cho độ chính xác và tính chuyên nghiệp của hệ thống Vital Signs đo bằng mmWave radar trong môi trường thực tế nhiều nhiễu động. Rất mong nhận được phản hồi và phê duyệt từ bạn để bắt tay vào triển khai trực tiếp vào mã nguồn!
