import numpy as np
import pandas as pd
from scipy import stats
from scipy.signal import periodogram, find_peaks
from scipy.stats import linregress
from typing import Any, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

def compute_hurst_exponent(series: np.ndarray) -> float | None:
    """Estimate Hurst exponent."""
    n = len(series)
    if n < 20: return None
    try:
        lags = range(2, min(n // 2, 100))
        rs_vals = []
        for lag in lags:
            chunks = [series[i: i + lag] for i in range(0, n - lag, lag)]
            rs_chunk = []
            for chunk in chunks:
                mean_c = np.mean(chunk)
                deviation = np.cumsum(chunk - mean_c)
                r = np.max(deviation) - np.min(deviation)
                s = np.std(chunk, ddof=1)
                if s > 0: rs_chunk.append(r / s)
            if rs_chunk: rs_vals.append(np.mean(rs_chunk))
        if len(rs_vals) < 2: return None
        log_lags = np.log(list(range(2, 2 + len(rs_vals))))
        log_rs = np.log(rs_vals)
        slope, *_ = linregress(log_lags, log_rs)
        return float(slope)
    except: return None

def detect_change_points(series: np.ndarray, min_size: int = 10) -> list[int]:
    """CUSUM change-point detection."""
    n = len(series)
    if n < min_size * 2: return []
    try:
        t = np.arange(n, dtype=float)
        slope, intercept, *_ = linregress(t, series)
        residuals = series - (slope * t + intercept)
        total_var = np.var(residuals)
        if total_var == 0: return []
        scores = []
        for i in range(min_size, n - min_size):
            left, right = residuals[:i], residuals[i:]
            within = (np.var(left)*len(left) + np.var(right)*len(right))/n
            scores.append((i, (total_var - within)/(total_var + 1e-12)))
        score_arr = np.array([s[1] for s in scores])
        peaks, _ = find_peaks(score_arr, height=np.mean(score_arr) + 1.5*np.std(score_arr), distance=min_size)
        return sorted([scores[p][0] for p in peaks], key=lambda i: scores[i-min_size][1], reverse=True)[:5]
    except: return []

def compute_spectral_seasonality(series: np.ndarray, fs: float = 1.0) -> dict:
    """Find dominant period via periodogram."""
    if len(series) < 8: return {"period": None, "strength": None}
    try:
        freqs, power = periodogram(series - np.mean(series), fs=fs)
        if len(freqs) < 2: return {"period": None, "strength": None}
        idx = int(np.argmax(power[1:])) + 1
        return {"period": round(1.0/freqs[idx]) if freqs[idx] > 0 else None, "strength": float(power[idx]/np.sum(power))}
    except: return {"period": None, "strength": None}
