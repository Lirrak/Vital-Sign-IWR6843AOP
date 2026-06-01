from __future__ import annotations

import numpy as np
from typing import List, Tuple
from scipy.interpolate import CubicSpline


class RLSFilter:
    """Recursive Least Squares (RLS) adaptive filter for rapid convergence and harmonic tracking."""

    def __init__(self, num_taps: int = 4, lmbda: float = 0.98, delta: float = 0.1) -> None:
        self.num_taps = num_taps
        self.lmbda = lmbda  # Forgetting factor (typically 0.95 to 0.99)
        self.w = np.zeros(num_taps)
        self.P = np.eye(num_taps) / delta  # Inverse correlation matrix

    def process(self, x_vector: np.ndarray, d_sample: float) -> float:
        """Process a multi-harmonic noise reference vector and return the filtered error.

        Args:
            x_vector: Multi-dimensional noise reference vector.
            d_sample: Primary signal containing desired signal + noise.

        Returns:
            Filtered error signal (clean cardiac component).
        """
        u = x_vector
        # Predict noise
        y = np.dot(self.w, u)
        error = d_sample - y

        # Compute gain vector
        pi_vec = np.dot(self.P, u)
        gain = pi_vec / (self.lmbda + np.dot(u, pi_vec))

        # Update weight vector and covariance matrix
        self.w += gain * error
        self.P = (self.P - np.outer(gain, np.dot(u, self.P))) / self.lmbda

        return error

    def reset(self) -> None:
        self.w.fill(0.0)
        self.P = np.eye(self.num_taps) / 0.1


def burg_ar_estimation(x: np.ndarray, order: int) -> Tuple[np.ndarray, float]:
    """Estimates the Autoregressive (AR) model parameters using Burg's Method.

    Args:
        x: The 1D signal.
        order: The AR model order (typically 10 to 16 for vital signs).

    Returns:
        AR coefficients (a) and prediction error variance (variance).
    """
    N = len(x)
    if N <= order:
        raise ValueError("Signal length must be greater than AR order.")

    f = x[1:].copy()
    b = x[:-1].copy()
    a = np.zeros(order)
    variance = np.dot(x, x) / N

    for i in range(order):
        num = -2.0 * np.dot(f, b)
        den = np.dot(f, f) + np.dot(b, b)

        if den == 0:
            k = 0.0
        else:
            k = num / den

        variance *= (1.0 - k**2)

        # Update AR parameters using Levinson-Durbin recursion
        a_prev = a.copy()
        a[i] = k
        for j in range(i):
            a[j] = a_prev[j] + k * a_prev[i - 1 - j]

        # Update forward and backward prediction errors
        f_next = f[1:] + k * b[1:]
        b_next = b[:-1] + k * f[:-1]
        f = f_next
        b = b_next

    return a, float(variance)


def compute_ar_spectrum(a: np.ndarray, variance: float, freqs: np.ndarray, fs: float) -> np.ndarray:
    """Computes the all-pole AR power spectrum over a given frequency grid.

    Args:
        a: AR model coefficients.
        variance: AR model prediction error variance.
        freqs: Grid of target frequencies (Hz).
        fs: Sampling frequency (Hz).

    Returns:
        Power spectrum values corresponding to the target frequencies.
    """
    spectrum = np.zeros_like(freqs)
    for idx, f in enumerate(freqs):
        # Denominator: 1 + sum(a_k * e^(-2j * pi * f * k / fs))
        k = np.arange(1, len(a) + 1)
        z = np.exp(-2j * np.pi * f * k / fs)
        denom = 1.0 + np.dot(a, z)
        spectrum[idx] = variance / (np.abs(denom) ** 2)
    return spectrum


class AdvancedVitalSignsDSP:
    """Advanced secondary DSP pipeline for ultra-high accuracy mmWave vital signs extraction.

    Features:
    1. Cubic Spline Resampling: Interpolates jittery UART samples to a uniform grid.
    2. Square-Root Normalization & Detrending: Stabilizes amplitude against distance.
    3. Phase Differencing: Highlights high-frequency cardiac micro-movements.
    4. Multi-Harmonic RLS Filter: Adaptive cancellation of 1st and 2nd respiration harmonics.
    5. Joint NDTFT & Burg AR Spectral Fusion: Multiplying Non-uniform DTFT and Autoregressive
       Burg spectra to isolate true vital sign peaks with 0.05 BPM resolution.
    6. Respiration Harmonic Suppression (RHS) Masking: Inverse-Gaussian notches at 2x and 3x BR.
    """

    def __init__(self, fs: float = 11.11, buffer_size: int = 256) -> None:
        self.fs = fs
        self.buffer_size = buffer_size
        self.rls = RLSFilter(num_taps=4, lmbda=0.98, delta=0.1)

        # Heart Rate fine grid (40 to 180 BPM with 0.05 BPM steps)
        self.hr_bpms = np.arange(40.0, 180.05, 0.05)
        self.hr_freqs = self.hr_bpms / 60.0

        # Breathing Rate fine grid (4 to 40 BPM with 0.05 BPM steps)
        self.br_bpms = np.arange(4.0, 40.05, 0.05)
        self.br_freqs = self.br_bpms / 60.0

    def filter_and_estimate_hr(
        self,
        heart_history: np.ndarray,
        breath_history: np.ndarray,
        fs: float,
        t_history: np.ndarray,
    ) -> Tuple[float, float]:
        """Filters chest phase and estimates the exact heart rate using Burg AR & NDTFT Fusion.

        Args:
            heart_history: Array of raw cardiac waveforms.
            breath_history: Array of raw respiration waveforms.
            fs: Estimated actual sampling rate.
            t_history: Array of actual relative timestamps.

        Returns:
            Fused Heart Rate in BPM (0.05 BPM resolution) and Peak-to-Average Confidence Score.
        """
        n = len(heart_history)
        if n < 64:
            return 72.0, 1.0  # Initial warm-up values

        # 1. Cubic Spline Resampling for Jitter Correction
        t_uniform = np.linspace(t_history[0], t_history[-1], n)
        fs_uniform = (n - 1) / (t_history[-1] - t_history[0] + 1e-9)

        try:
            cs_heart = CubicSpline(t_history, heart_history)
            heart_uniform = cs_heart(t_uniform)

            cs_breath = CubicSpline(t_history, breath_history)
            breath_uniform = cs_breath(t_uniform)
        except Exception:
            # Fallback if interpolation fails
            heart_uniform = heart_history
            breath_uniform = breath_history
            fs_uniform = fs

        # 2. Square-Root Normalization & Median Detrending (Hao et al., 2025)
        breath_detrend = breath_uniform - np.median(breath_uniform)
        breath_norm = breath_detrend / (np.sqrt(np.var(breath_detrend) + 1e-6))

        heart_detrend = heart_uniform - np.median(heart_uniform)
        heart_norm = heart_detrend / (np.sqrt(np.var(heart_detrend) + 1e-6))

        # 3. Phase Differencing (Boost cardiac micro-movements)
        diff_heart = np.diff(heart_norm, prepend=heart_norm[0])

        # 4. Bandpass Filtering for Respiration (0.08 to 0.6 Hz, i.e., 4.8 to 36 BPM)
        breath_fft = np.fft.fft(breath_norm)
        freqs = np.fft.fftfreq(n, d=1.0 / fs_uniform)
        breath_fft[(np.abs(freqs) < 0.08) | (np.abs(freqs) > 0.6)] = 0
        clean_breath = np.real(np.fft.ifft(breath_fft))

        # 5. Bandpass Filtering for Cardiac (0.65 to 3.0 Hz, i.e., 39 to 180 BPM)
        heart_fft = np.fft.fft(diff_heart)
        heart_fft[(np.abs(freqs) < 0.65) | (np.abs(freqs) > 3.0)] = 0
        bp_heart = np.real(np.fft.ifft(heart_fft))

        # 6. Multi-Harmonic RLS Adaptive Breathing Harmonic Suppression (Chen et al., 2024)
        self.rls.reset()
        clean_heart = np.zeros_like(bp_heart)
        for i in range(n):
            b_val = clean_breath[i]
            b_prev = clean_breath[max(0, i - 1)]
            # Construct multi-harmonic reference: [breath, breath^2, breath_prev, breath_prev^2]
            x_ref = np.array([b_val, b_val**2, b_prev, b_prev**2])
            clean_heart[i] = self.rls.process(x_ref, bp_heart[i])

        # 7. Joint Spectral Estimation
        # A. Non-uniform NDTFT Spectrum
        phase_matrix = -2j * np.pi * np.outer(self.hr_freqs, t_uniform)
        dtft_vals = np.dot(np.exp(phase_matrix), clean_heart)
        ndtft_power = np.abs(dtft_vals) ** 2

        # B. Burg Autoregressive Spectrum
        burg_power = np.zeros_like(self.hr_freqs)
        try:
            # Fit AR model of order 14 (optimal for vital signs frequency range)
            ar_coefs, noise_var = burg_ar_estimation(clean_heart, order=14)
            burg_power = compute_ar_spectrum(ar_coefs, noise_var, self.hr_freqs, fs_uniform)
        except Exception:
            # Fallback to flat Burg power if fitting fails
            burg_power.fill(1.0)

        # C. Spectral Normalization and Product Fusion
        ndtft_norm = ndtft_power / (np.max(ndtft_power) + 1e-9)
        burg_norm = burg_power / (np.max(burg_power) + 1e-9)
        fused_spectrum = ndtft_norm * burg_norm

        # 8. Respiration Harmonic Suppression (RHS) Masking
        # Compute breathing spectrum peak to find precise fundamental f_br
        br_phase_matrix = -2j * np.pi * np.outer(self.br_freqs, t_uniform)
        br_dtft_vals = np.dot(np.exp(br_phase_matrix), clean_breath)
        br_power = np.abs(br_dtft_vals) ** 2
        best_br_idx = np.argmax(br_power)
        f_br = self.br_freqs[best_br_idx]

        # Apply inverse Gaussian notch filter around 2x and 3x breathing frequencies
        mask = np.ones_like(self.hr_freqs)
        sigma_h = 0.08  # ~4.8 BPM bandwidth
        for harmonic_k in [2, 3]:
            f_harmonic = harmonic_k * f_br
            harmonic_mask = 1.0 - np.exp(
                -((self.hr_freqs - f_harmonic) ** 2) / (2 * (sigma_h**2))
            )
            mask *= harmonic_mask

        masked_spectrum = fused_spectrum * mask

        # Find Peak Fused Frequency
        best_idx = np.argmax(masked_spectrum)
        best_bpm = self.hr_bpms[best_idx]

        # Compute Spectral Peak-to-Average Ratio (PAR) for Quality-Aware Kalman
        mean_power = np.mean(masked_spectrum)
        peak_power = masked_spectrum[best_idx]
        confidence = float(peak_power / (mean_power + 1e-9))

        return float(best_bpm), confidence

    def estimate_br(
        self, breath_history: np.ndarray, fs: float, t_history: np.ndarray
    ) -> float:
        """Estimates the exact breathing rate using high-resolution Non-uniform DTFT.

        Args:
            breath_history: Array of raw breathing waveforms.
            fs: Estimated actual sampling rate.
            t_history: Array of relative timestamps.

        Returns:
            Estimated Breathing Rate in BPM (0.05 BPM resolution).
        """
        n = len(breath_history)
        if n < 64:
            return 12.0

        # 1. Cubic Spline Resampling
        t_uniform = np.linspace(t_history[0], t_history[-1], n)
        fs_uniform = (n - 1) / (t_history[-1] - t_history[0] + 1e-9)

        try:
            cs_breath = CubicSpline(t_history, breath_history)
            breath_uniform = cs_breath(t_uniform)
        except Exception:
            breath_uniform = breath_history
            fs_uniform = fs

        # 2. Square-Root Normalization & Detrending
        breath_detrend = breath_uniform - np.median(breath_uniform)
        breath_norm = breath_detrend / (np.sqrt(np.var(breath_detrend) + 1e-6))

        # 3. Bandpass Filtering for Respiration (0.08 to 0.6 Hz)
        breath_fft = np.fft.fft(breath_norm)
        freqs = np.fft.fftfreq(n, d=1.0 / fs_uniform)
        breath_fft[(np.abs(freqs) < 0.08) | (np.abs(freqs) > 0.6)] = 0
        clean_breath = np.real(np.fft.ifft(breath_fft))

        # 4. High-Resolution Non-uniform DTFT
        phase_matrix = -2j * np.pi * np.outer(self.br_freqs, t_uniform)
        dtft_vals = np.dot(np.exp(phase_matrix), clean_breath)
        power_spectrum = np.abs(dtft_vals) ** 2

        best_idx = np.argmax(power_spectrum)
        best_bpm = self.br_bpms[best_idx]

        return float(best_bpm)
