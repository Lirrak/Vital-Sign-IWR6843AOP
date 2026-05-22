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


class AdvancedVitalSignsDSP:
    """Advanced DSP processor for high-accuracy vital signs frequency estimation.
    
    Uses:
    1. Spectral Brick-wall Bandpass Filter (Zero-phase distortion)
    2. LMS Adaptive Noise Canceller (Resp harmonic cancellation)
    3. DTFT Fine-grid Fourier Interpolation (0.1 BPM resolution)
    """

    def __init__(self, fs: float = 20.0, buffer_size: int = 256) -> None:
        self.fs = fs
        self.buffer_size = buffer_size
        self.lms = LMSFilter(num_taps=12, mu=0.01)

        # Setup fine grid for Heart Rate (45 to 180 BPM with 0.1 BPM steps)
        self.hr_bpms = np.arange(45.0, 180.1, 0.1)
        self.hr_freqs = self.hr_bpms / 60.0

        # Setup fine grid for Breathing Rate (6 to 40 BPM with 0.1 BPM steps)
        self.br_bpms = np.arange(6.0, 40.1, 0.1)
        self.br_freqs = self.br_bpms / 60.0

    def filter_and_estimate_hr(self, heart_history: np.ndarray, breath_history: np.ndarray, fs: float, t_history: np.ndarray) -> float:
        """Performs advanced filtering and estimates the exact heart rate in BPM using Non-uniform DTFT.
        
        Args:
            heart_history: Array of raw heart waveform values.
            breath_history: Array of raw breath waveform values.
            fs: Estimated actual sampling frequency.
            t_history: Array of actual timestamps relative to the first sample.
            
        Returns:
            Estimated heart rate in BPM (0.1 BPM resolution).
        """
        n = len(heart_history)
        if n < 64:
            return 72.0  # Default initial value

        # 1. Spectral Bandpass Filter for Respiration (0.1 to 0.6 Hz, i.e., 6 to 36 BPM)
        breath_fft = np.fft.fft(breath_history)
        breath_freqs = np.fft.fftfreq(n, d=1.0/fs)
        breath_fft[(np.abs(breath_freqs) < 0.1) | (np.abs(breath_freqs) > 0.6)] = 0
        clean_breath = np.real(np.fft.ifft(breath_fft))

        # 2. Spectral Bandpass Filter for Heart Waveform (0.75 to 3.0 Hz, i.e., 45 to 180 BPM)
        heart_fft = np.fft.fft(heart_history)
        heart_freqs = np.fft.fftfreq(n, d=1.0/fs)
        heart_fft[(np.abs(heart_freqs) < 0.75) | (np.abs(heart_freqs) > 3.0)] = 0
        bp_heart = np.real(np.fft.ifft(heart_fft))

        # 3. LMS Adaptive Respiration Cancellation
        # Cancel breathing harmonics leaked into the heartbeat signal
        self.lms.reset()
        clean_heart = np.zeros_like(bp_heart)
        for i in range(n):
            # Use clean breath as noise reference, bp_heart as primary signal
            clean_heart[i] = self.lms.process(clean_breath[i], bp_heart[i])

        # 4. High-Resolution Non-uniform DTFT using actual timestamps to eliminate jitter
        # Compute NDTFT on fine grid using matrix multiplication with real time vectors
        phase_matrix = -2j * np.pi * np.outer(self.hr_freqs, t_history)
        dtft_vals = np.dot(np.exp(phase_matrix), clean_heart)
        power_spectrum = np.abs(dtft_vals) ** 2

        # Find the peak frequency
        best_idx = np.argmax(power_spectrum)
        best_bpm = self.hr_bpms[best_idx]

        return float(best_bpm)

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

        # 1. Spectral Bandpass Filter for Respiration (0.1 to 0.6 Hz)
        breath_fft = np.fft.fft(breath_history)
        breath_freqs = np.fft.fftfreq(n, d=1.0/fs)
        breath_fft[(np.abs(breath_freqs) < 0.1) | (np.abs(breath_freqs) > 0.6)] = 0
        clean_breath = np.real(np.fft.ifft(breath_fft))

        # 2. High-Resolution Non-uniform DTFT
        phase_matrix = -2j * np.pi * np.outer(self.br_freqs, t_history)
        dtft_vals = np.dot(np.exp(phase_matrix), clean_breath)
        power_spectrum = np.abs(dtft_vals) ** 2

        best_idx = np.argmax(power_spectrum)
        best_bpm = self.br_bpms[best_idx]

        return float(best_bpm)
