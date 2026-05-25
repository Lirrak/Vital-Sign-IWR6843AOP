from __future__ import annotations

import numpy as np
from typing import List, Tuple


class LMSFilter:
    """Least Mean Squares (LMS) adaptive filter for respiration harmonic cancellation."""

    def __init__(self, num_taps: int = 8, mu: float = 0.005) -> None:
        self.num_taps = num_taps
        self.mu = mu
        self.weights = np.zeros(num_taps)
        self.buffer = np.zeros(num_taps)

    def process(self, x_sample: float, d_sample: float) -> float:
        """Process a single sample.
        
        Args:
            x_sample: Noise reference (e.g. respiration signal)
            d_sample: Primary signal containing desired signal + noise (e.g. heartbeat)
            
        Returns:
            Filtered error signal (clean heartbeat)
        """
        # Shift buffer and insert new sample
        self.buffer = np.roll(self.buffer, 1)
        self.buffer[0] = x_sample

        # Predict noise component
        y = np.dot(self.weights, self.buffer)

        # Compute error (clean signal)
        error = d_sample - y

        # Update weights
        self.weights += self.mu * error * self.buffer

        return error

    def reset(self) -> None:
        self.weights.fill(0.0)
        self.buffer.fill(0.0)


class RLSFilter:
    """Recursive Least Squares (RLS) adaptive filter for rapid convergence."""

    def __init__(self, num_taps: int = 4, lmbda: float = 0.99, delta: float = 0.1) -> None:
        self.num_taps = num_taps
        self.lmbda = lmbda  # Forgetting factor
        self.w = np.zeros(num_taps)
        self.P = np.eye(num_taps) / delta  # Inverse correlation matrix

    def process(self, x_vector: np.ndarray, d_sample: float) -> float:
        """Process a sample vector x_vector and primary sample d_sample.
        
        Args:
            x_vector: multi-dimensional noise reference (e.g. breath, breath^2, etc.)
            d_sample: Primary signal containing desired signal + noise (e.g. heartbeat)
            
        Returns:
            Filtered error signal (clean heartbeat)
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


class AdvancedVitalSignsDSP:
    """Advanced DSP processor for high-accuracy vital signs frequency estimation.
    
    Uses:
    1. Square-Root Normalization & Median Detrending (Hao et al., 2025)
    2. Phase Differencing High-Frequency Enhancement
    3. Multi-Harmonic RLS Adaptive Noise Canceller (Chen et al., 2024)
    4. NDTFT Respiration Harmonic Suppression (RHS) Masking
    5. DTFT Fine-grid Fourier Interpolation (0.1 BPM resolution)
    """

    def __init__(self, fs: float = 11.11, buffer_size: int = 256) -> None:
        self.fs = fs
        self.buffer_size = buffer_size
        self.lms = LMSFilter(num_taps=12, mu=0.01)
        self.rls = RLSFilter(num_taps=4, lmbda=0.99, delta=0.1)

        # Setup fine grid for Heart Rate (45 to 180 BPM with 0.1 BPM steps)
        self.hr_bpms = np.arange(45.0, 180.1, 0.1)
        self.hr_freqs = self.hr_bpms / 60.0

        # Setup fine grid for Breathing Rate (6 to 40 BPM with 0.1 BPM steps)
        self.br_bpms = np.arange(6.0, 40.1, 0.1)
        self.br_freqs = self.br_bpms / 60.0

    def filter_and_estimate_hr(self, heart_history: np.ndarray, breath_history: np.ndarray, fs: float, t_history: np.ndarray) -> Tuple[float, float]:
        """Performs advanced filtering and estimates the exact heart rate in BPM using Non-uniform DTFT.
        
        Args:
            heart_history: Array of raw heart waveform values.
            breath_history: Array of raw breath waveform values.
            fs: Estimated actual sampling frequency.
            t_history: Array of actual timestamps relative to the first sample.
            
        Returns:
            Estimated heart rate in BPM (0.1 BPM resolution) and spectral confidence score (PAR).
        """
        n = len(heart_history)
        if n < 64:
            return 72.0, 1.0  # Default initial value, confidence 1.0

        # 1. Square-Root Normalization & Median Detrending (Hao et al., 2025)
        breath_detrend = breath_history - np.median(breath_history)
        breath_norm = breath_detrend / (np.sqrt(np.var(breath_detrend) + 1e-6))
        
        heart_detrend = heart_history - np.median(heart_history)
        heart_norm = heart_detrend / (np.sqrt(np.var(heart_detrend) + 1e-6))

        # 2. Phase Differencing (Sai phân pha để làm nổi bật nhịp tim, giảm thở)
        diff_heart = np.diff(heart_norm, prepend=heart_norm[0])

        # 3. Spectral Bandpass Filter for Respiration (0.1 to 0.6 Hz, i.e., 6 to 36 BPM)
        breath_fft = np.fft.fft(breath_norm)
        breath_freqs = np.fft.fftfreq(n, d=1.0/fs)
        breath_fft[(np.abs(breath_freqs) < 0.1) | (np.abs(breath_freqs) > 0.6)] = 0
        clean_breath = np.real(np.fft.ifft(breath_fft))

        # 4. Spectral Bandpass Filter for Heart Waveform (0.75 to 3.0 Hz, i.e., 45 to 180 BPM)
        heart_fft = np.fft.fft(diff_heart)
        heart_freqs = np.fft.fftfreq(n, d=1.0/fs)
        heart_fft[(np.abs(heart_freqs) < 0.75) | (np.abs(heart_freqs) > 3.0)] = 0
        bp_heart = np.real(np.fft.ifft(heart_fft))

        # 5. Multi-Harmonic RLS Adaptive Respiration Noise Cancellation (Chen et al., 2024)
        self.rls.reset()
        clean_heart = np.zeros_like(bp_heart)
        for i in range(n):
            b_val = clean_breath[i]
            b_prev = clean_breath[max(0, i-1)]
            # Multi-harmonic reference: [breath, breath^2, breath_prev, breath_prev^2]
            x_ref = np.array([b_val, b_val**2, b_prev, b_prev**2])
            clean_heart[i] = self.rls.process(x_ref, bp_heart[i])

        # 6. High-Resolution Non-uniform DTFT on fine grid
        phase_matrix = -2j * np.pi * np.outer(self.hr_freqs, t_history)
        dtft_vals = np.dot(np.exp(phase_matrix), clean_heart)
        power_spectrum = np.abs(dtft_vals) ** 2

        # 7. Respiration Harmonic Suppression (RHS) Masking
        # Compute breathing spectrum first to find fundamental frequency f_br
        br_phase_matrix = -2j * np.pi * np.outer(self.br_freqs, t_history)
        br_dtft_vals = np.dot(np.exp(br_phase_matrix), clean_breath)
        br_power = np.abs(br_dtft_vals) ** 2
        best_br_idx = np.argmax(br_power)
        f_br = self.br_freqs[best_br_idx]

        # Apply inverse Gaussian notch filter around 2x and 3x breathing frequencies
        mask = np.ones_like(self.hr_freqs)
        sigma_h = 0.08  # Physiological harmonic bandwidth (~5 BPM)
        for harmonic_k in [2, 3]:
            f_harmonic = harmonic_k * f_br
            harmonic_mask = 1.0 - np.exp(-((self.hr_freqs - f_harmonic) ** 2) / (2 * (sigma_h ** 2)))
            mask *= harmonic_mask
            
        masked_spectrum = power_spectrum * mask

        # Find the peak frequency
        best_idx = np.argmax(masked_spectrum)
        best_bpm = self.hr_bpms[best_idx]

        # Calculate peak confidence (Peak-to-Average Ratio)
        mean_power = np.mean(masked_spectrum)
        peak_power = masked_spectrum[best_idx]
        confidence = float(peak_power / (mean_power + 1e-9))

        return float(best_bpm), confidence

    def estimate_br(self, breath_history: np.ndarray, fs: float, t_history: np.ndarray) -> float:
        """Estimates the exact breathing rate in BPM using high-resolution Non-uniform DTFT.
        
        Args:
            breath_history: Array of raw breath waveform values.
            fs: Estimated actual sampling frequency.
            t_history: Array of actual timestamps relative to the first sample.
            
        Returns:
            Estimated breathing rate in BPM (0.1 BPM resolution).
        """
        n = len(breath_history)
        if n < 64:
            return 12.0  # Default initial value

        # 1. Square-Root Normalization & Detrending
        breath_detrend = breath_history - np.median(breath_history)
        breath_norm = breath_detrend / (np.sqrt(np.var(breath_detrend) + 1e-6))

        # 2. Spectral Bandpass Filter for Respiration (0.1 to 0.6 Hz)
        breath_fft = np.fft.fft(breath_norm)
        breath_freqs = np.fft.fftfreq(n, d=1.0/fs)
        breath_fft[(np.abs(breath_freqs) < 0.1) | (np.abs(breath_freqs) > 0.6)] = 0
        clean_breath = np.real(np.fft.ifft(breath_fft))

        # 3. High-Resolution Non-uniform DTFT
        phase_matrix = -2j * np.pi * np.outer(self.br_freqs, t_history)
        dtft_vals = np.dot(np.exp(phase_matrix), clean_breath)
        power_spectrum = np.abs(dtft_vals) ** 2

        best_idx = np.argmax(power_spectrum)
        best_bpm = self.br_bpms[best_idx]

        return float(best_bpm)
