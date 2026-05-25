from __future__ import annotations

from typing import List, Optional, Tuple


class MovingMedianFilter:
    """Sliding window median filter to eliminate spike noise (impulses)."""

    def __init__(self, window_size: int) -> None:
        self.window_size = window_size
        self.values: List[float] = []

    def update(self, val: float) -> float:
        self.values.append(val)
        if len(self.values) > self.window_size:
            self.values.pop(0)

        sorted_vals = sorted(self.values)
        n = len(sorted_vals)
        if n == 0:
            return val
        if n % 2 == 1:
            return sorted_vals[n // 2]
        else:
            return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / 2.0

    def reset(self) -> None:
        self.values.clear()


class KalmanFilter1D:
    """1D Kalman filter to smooth micro-noises/ripples with low phase lag."""

    def __init__(self, Q: float, R: float, x0: float = 0.0, P0: float = 1.0) -> None:
        self.Q = Q  # Process noise covariance
        self.R = R  # Measurement noise covariance
        self.x = x0  # Estimated state
        self.P = P0  # Estimated error covariance
        self.initialized = False

    def update(self, measurement: float, R_dynamic: Optional[float] = None) -> float:
        if not self.initialized:
            self.x = measurement
            self.P = 1.0
            self.initialized = True
            return self.x

        current_R = R_dynamic if R_dynamic is not None else self.R

        # Prediction
        self.P = self.P + self.Q

        # Correction (Measurement Update)
        K = self.P / (self.P + current_R)
        self.x = self.x + K * (measurement - self.x)
        self.P = (1.0 - K) * self.P

        return self.x

    def reset(self, x0: float = 0.0, P0: float = 1.0) -> None:
        self.x = x0
        self.P = P0
        self.initialized = False


class VitalSignStabilizer:
    """Dual-stage filter stabilizer (Median -> Kalman) for vital signs tracking.

    Includes state freezing to hold the last stable estimate when radar packets
    report invalid metrics (e.g. out of range, body movement artifacts).
    Also supports dynamic quality-aware Kalman measurement noise scaling.
    """

    def __init__(
        self,
        hr_window: int = 7,
        br_window: int = 9,
        hr_Q: float = 0.05,
        hr_R: float = 1.0,
        br_Q: float = 0.02,
        br_R: float = 0.5,
    ) -> None:
        self.hr_median = MovingMedianFilter(hr_window)
        self.br_median = MovingMedianFilter(br_window)

        self.hr_kalman = KalmanFilter1D(Q=hr_Q, R=hr_R)
        self.br_kalman = KalmanFilter1D(Q=br_Q, R=br_R)

        self.last_valid_hr: Optional[float] = None
        self.last_valid_br: Optional[float] = None

    def process(
        self,
        hr_raw: float,
        hr_valid: bool,
        br_raw: float,
        br_valid: bool,
        hr_conf: float = 1.0,
        br_deviation: float = 0.0,
    ) -> Tuple[float, float]:
        # 1. Process Heart Rate with quality-aware R_dynamic scaling
        if hr_valid:
            # Map hr_conf (spectral Peak-to-Average Ratio) to dynamic Kalman measurement covariance R
            # High confidence (PAR >= 5.0) -> small R (trust measurements)
            # Low confidence (PAR <= 2.0) -> large R (trust prediction/history)
            if hr_conf >= 5.0:
                hr_R_dyn = self.hr_kalman.R * 0.15
            elif hr_conf <= 2.0:
                hr_R_dyn = self.hr_kalman.R * 12.0
            else:
                # Smooth interpolation between factors 12.0 and 0.15
                t = (hr_conf - 2.0) / 3.0
                hr_R_dyn = self.hr_kalman.R * (12.0 - 11.85 * t)

            median_hr = self.hr_median.update(hr_raw)
            smoothed_hr = self.hr_kalman.update(median_hr, R_dynamic=hr_R_dyn)
            self.last_valid_hr = smoothed_hr
        else:
            smoothed_hr = self.last_valid_hr if self.last_valid_hr is not None else hr_raw

        # 2. Process Breathing Rate with breathing_deviation quality adaptation
        if br_valid:
            # High breathing deviation indicates possible micro-motions or irregular breathing.
            # Scale br_R up if deviation is high to smooth out sudden irregular breathing spikes.
            # Normal deviation values are typically < 0.1
            if br_deviation > 0.15:
                br_R_dyn = self.br_kalman.R * 5.0
            else:
                br_R_dyn = self.br_kalman.R

            median_br = self.br_median.update(br_raw)
            smoothed_br = self.br_kalman.update(median_br, R_dynamic=br_R_dyn)
            self.last_valid_br = smoothed_br
        else:
            smoothed_br = self.last_valid_br if self.last_valid_br is not None else br_raw

        return smoothed_hr, smoothed_br

    def reset(self) -> None:
        self.hr_median.reset()
        self.br_median.reset()
        self.hr_kalman.reset()
        self.br_kalman.reset()
        self.last_valid_hr = None
        self.last_valid_br = None
