from __future__ import annotations

import math
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Deque, List, Optional, Tuple

from .mmwave_parser import VitalSignData
from .app_config import (
    MIN_RANGE_M,
    MAX_RANGE_M,
    ENABLE_KALMAN_RANGE,
    ENABLE_KALMAN_VITAL,
    KF_RANGE_Q,
    KF_RANGE_R,
    KF_VITAL_Q,
    KF_VITAL_R,
    TRACKING_MODE,
    FOCUS_CENTER_M,
    FOCUS_SPAN_M,
)


@dataclass
class FilteredVitalSign:
    raw_heart_rate_bpm: float
    raw_breathing_rate_bpm: float
    filtered_heart_rate_bpm: Optional[float]
    filtered_breathing_rate_bpm: Optional[float]
    filtered_range_m: Optional[float]
    is_valid: bool
    reason: str


class KalmanFilter1D:
    """
    1D Kalman Filter for smoothing and tracking noisy radar signals
    (e.g., target range or estimated vital sign rates).
    """

    def __init__(self, q: float, r: float, initial_x: float = 0.0, initial_p: float = 1.0) -> None:
        self.q = q  # Process noise covariance
        self.r = r  # Measurement noise covariance
        self.x = initial_x  # State estimate
        self.p = initial_p  # Estimate covariance
        self.initialized = False

    def update(self, measurement: float) -> float:
        if not self.initialized:
            self.x = measurement
            self.p = 1.0
            self.initialized = True
            return self.x

        # Prediction step
        self.p = self.p + self.q

        # Measurement update step
        k = self.p / (self.p + self.r)  # Kalman gain
        self.x = self.x + k * (measurement - self.x)
        self.p = (1.0 - k) * self.p

        return self.x

    def reset(self, initial_x: float) -> None:
        self.x = initial_x
        self.p = 1.0
        self.initialized = True


class RobustVitalFilter:
    """
    Upgraded filter for HR/BR/Range tracking.
    Integrates Nearest-Cluster Priority (NCP) tracking, Range Focus manual lock,
    Adaptive Kalman Filtering, and Bin-Jump Transient Gating.
    """

    def __init__(
        self,
        hr_min: float = 35.0,
        hr_max: float = 180.0,
        br_min: float = 5.0,
        br_max: float = 40.0,
        max_hr_jump_bpm: float = 28.0,
        max_br_jump_bpm: float = 10.0,
        median_window: int = 7,
        min_valid_samples: int = 3,
        max_consecutive_rejections: int = 10,
    ) -> None:
        self.hr_min = hr_min
        self.hr_max = hr_max
        self.br_min = br_min
        self.br_max = br_max
        self.max_hr_jump_bpm = max_hr_jump_bpm
        self.max_br_jump_bpm = max_br_jump_bpm
        
        # Median buffers as a fallback/secondary filter
        self.hr_values: Deque[float] = deque(maxlen=median_window)
        self.br_values: Deque[float] = deque(maxlen=median_window)
        self.min_valid_samples = min_valid_samples
        
        # Lockout statistics
        self.max_consecutive_rejections = max_consecutive_rejections
        self.consecutive_rejections = 0
        
        self.last_hr: Optional[float] = None
        self.last_br: Optional[float] = None
        
        # Kalman filter instances
        self.range_kf = KalmanFilter1D(q=KF_RANGE_Q, r=KF_RANGE_R)
        self.hr_kf = KalmanFilter1D(q=KF_VITAL_Q, r=KF_VITAL_R)
        self.br_kf = KalmanFilter1D(q=KF_VITAL_Q, r=KF_VITAL_R)
        
        # Target Tracking & Bin Jitter Management
        self.last_raw_bin: Optional[int] = None
        self.frames_since_bin_jump = 999

        # Version 3 Point Cloud Tracking and Range Lock states
        self.last_point_cloud: List[Tuple[float, float, float, float]] = []
        self.tracking_mode = TRACKING_MODE
        self.focus_center = FOCUS_CENTER_M
        self.focus_span = FOCUS_SPAN_M

    def set_last_point_cloud(self, pc: List[Tuple[float, float, float, float]]) -> None:
        self.last_point_cloud = pc

    def set_tracking_parameters(self, mode: str, center: float, span: float) -> None:
        self.tracking_mode = mode
        self.focus_center = center
        self.focus_span = span

    def _get_target_range_from_point_cloud(self) -> Optional[Tuple[float, int]]:
        """
        Applies Nearest-Cluster Priority (NCP) or Manual Focus Lock on the Point Cloud
        to identify the true subject distance, bypassing wall/chair reflections.
        Returns: Tuple (centroid_y_meters, range_bin) or None if no cluster found.
        """
        if not self.last_point_cloud:
            return None

        # 1. Bounds Determination based on Mode
        if self.tracking_mode == "manual":
            min_y = max(MIN_RANGE_M, self.focus_center - self.focus_span)
            max_y = min(MAX_RANGE_M, self.focus_center + self.focus_span)
        else:
            min_y = MIN_RANGE_M
            max_y = MAX_RANGE_M

        # 2. Filter points inside depth range
        valid_pts = sorted([p for p in self.last_point_cloud if min_y <= p[1] <= max_y], key=lambda x: x[1])
        if not valid_pts:
            return None

        # 3. Dynamic Distance Clustering (0.18m threshold)
        clusters: List[List[Tuple[float, float, float, float]]] = []
        current_cluster = [valid_pts[0]]
        for p in valid_pts[1:]:
            if p[1] - current_cluster[-1][1] <= 0.18:
                current_cluster.append(p)
            else:
                clusters.append(current_cluster)
                current_cluster = [p]
        clusters.append(current_cluster)

        # 4. Nearest-Cluster Priority selection
        # For Auto mode: Pick the closest cluster (index 0 since sorted by Y)
        # For Manual mode: Pick the cluster closest to focus_center
        if self.tracking_mode == "manual":
            target_cluster = min(clusters, key=lambda c: abs(sum(p[1] for p in c)/len(c) - self.focus_center))
        else:
            target_cluster = clusters[0]  # NCP (Nearest Cluster)

        # 5. Compute Centroid Y
        y_vals = [p[1] for p in target_cluster]
        centroid_y = sum(y_vals) / len(y_vals)
        range_bin = int(round(centroid_y / 0.04))

        return centroid_y, range_bin, target_cluster

    def update(self, vital: VitalSignData) -> FilteredVitalSign:
        hr = vital.heart_rate_bpm
        br = vital.breathing_rate_bpm
        
        # 1. Resolve target range bin and distance via NCP/Manual override
        pc_result = self._get_target_range_from_point_cloud()
        target_cluster = []
        
        if pc_result is not None:
            raw_range, target_bin, target_cluster = pc_result
            # Override target bin in vital struct to align pha analysis
            vital.range_bin = target_bin
        else:
            # Fallback to DSP range bin if Point Cloud is absent/empty
            raw_range = vital.range_bin * 0.04

        # 2. Range Bounding Box Check (Range-gate Limiter)
        if self.tracking_mode == "manual":
            min_y = max(MIN_RANGE_M, self.focus_center - self.focus_span)
            max_y = min(MAX_RANGE_M, self.focus_center + self.focus_span)
        else:
            min_y = MIN_RANGE_M
            max_y = MAX_RANGE_M
            
        range_valid = min_y <= raw_range <= max_y

        # 3. Kalman filter for Range Tracking
        if ENABLE_KALMAN_RANGE:
            filtered_range = self.range_kf.update(raw_range)
        else:
            filtered_range = raw_range

        # 4. Bin Jump Transient Detection
        if self.last_raw_bin is not None and vital.range_bin != self.last_raw_bin:
            self.frames_since_bin_jump = 0  # Reset counter
        else:
            self.frames_since_bin_jump += 1
        self.last_raw_bin = vital.range_bin

        # 5. Circular Buffer DC Removal (Mean subtraction)
        if vital.heart_circular_buffer:
            mean_h = sum(vital.heart_circular_buffer) / len(vital.heart_circular_buffer)
            vital.heart_circular_buffer = [x - mean_h for x in vital.heart_circular_buffer]
        if vital.breath_circular_buffer:
            mean_b = sum(vital.breath_circular_buffer) / len(vital.breath_circular_buffer)
            vital.breath_circular_buffer = [x - mean_b for x in vital.breath_circular_buffer]

        # 6. Gating check
        if not range_valid:
            valid = False
            reason = f"range_out_of_bounds_{raw_range:.2f}m"
        elif self.frames_since_bin_jump < 3:
            valid = False
            reason = "transient_bin_jump_gating"
        else:
            valid, reason = self._validate_basic(hr, br)

        # 7. Apply adaptive filtering
        if valid:
            self.hr_values.append(hr)
            self.br_values.append(br)
            self.last_hr = hr
            self.last_br = br
            self.consecutive_rejections = 0

            # Update Adaptive Kalman Filters (dynamic R covariance based on point count & deviation)
            if ENABLE_KALMAN_VITAL:
                n_points = len(target_cluster) if target_cluster else 3
                dev = vital.breathing_deviation
                
                # Signal Confidence (C)
                confidence = 0.2 * n_points + 5.0 * dev
                
                # Adjust R dynamically
                if confidence > 1.5:
                    r_scale = max(0.1, 1.5 / confidence)
                else:
                    r_scale = min(10.0, 1.5 / (confidence + 1e-6))
                
                self.hr_kf.r = KF_VITAL_R * r_scale
                self.br_kf.r = KF_VITAL_R * r_scale
                
                filtered_hr = self.hr_kf.update(hr)
                filtered_br = self.br_kf.update(br)
            else:
                filtered_hr = float(statistics.median(self.hr_values)) if len(self.hr_values) >= self.min_valid_samples else None
                filtered_br = float(statistics.median(self.br_values)) if len(self.br_values) >= self.min_valid_samples else None
        else:
            self.consecutive_rejections += 1
            
            # Lockout recovery
            if self.consecutive_rejections >= self.max_consecutive_rejections and range_valid:
                self.hr_values.clear()
                self.br_values.clear()
                self.hr_values.append(hr)
                self.br_values.append(br)
                self.last_hr = hr
                self.last_br = br
                
                self.hr_kf.reset(hr)
                self.br_kf.reset(br)
                
                self.consecutive_rejections = 0
                valid = True
                reason = "filter_lockout_recovery_reset"
                
                filtered_hr = hr
                filtered_br = br
            else:
                if ENABLE_KALMAN_VITAL and self.hr_kf.initialized and self.br_kf.initialized:
                    filtered_hr = self.hr_kf.x
                    filtered_br = self.br_kf.x
                else:
                    filtered_hr = None
                    filtered_br = None

        if not ENABLE_KALMAN_VITAL:
            if len(self.hr_values) < self.min_valid_samples:
                filtered_hr = None
                filtered_br = None
                if valid:
                    reason = f"warming_up_{len(self.hr_values)}/{self.min_valid_samples}"

        return FilteredVitalSign(
            raw_heart_rate_bpm=hr,
            raw_breathing_rate_bpm=br,
            filtered_heart_rate_bpm=filtered_hr,
            filtered_breathing_rate_bpm=filtered_br,
            filtered_range_m=filtered_range,
            is_valid=valid,
            reason=reason,
        )

    def _validate_basic(self, hr: float, br: float) -> tuple[bool, str]:
        if not _finite(hr) or not _finite(br):
            return False, "nan_or_inf"
        if hr == 0 or br == 0:
            return False, "zero_value_from_firmware"
        if not (self.hr_min <= hr <= self.hr_max):
            return False, f"hr_out_of_range_{hr:.2f}"
        if not (self.br_min <= br <= self.br_max):
            return False, f"br_out_of_range_{br:.2f}"
        if self.last_hr is not None and abs(hr - self.last_hr) > self.max_hr_jump_bpm:
            return False, f"hr_jump_{self.last_hr:.2f}_to_{hr:.2f}"
        if self.last_br is not None and abs(br - self.last_br) > self.max_br_jump_bpm:
            return False, f"br_jump_{self.last_br:.2f}_to_{br:.2f}"
        return True, "ok"


def _finite(value: float) -> bool:
    return isinstance(value, float) and math.isfinite(value)
