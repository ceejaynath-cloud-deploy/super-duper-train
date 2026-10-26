"""
Stop Loss and Take Profit Calculator (REDESIGNED)
Primary method: ATR(14) based
  SL = 1 × ATR(14)
  TP = 5 × ATR(14)
Fallback to original CRT swing method if ATR unavailable.
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np

from config import (
    SL_ATR_MULT,
    TP_ATR_MULT,
    ATR_PERIOD,
    USE_ATR_SL_TP,
    MIN_SL_PIPS,
    MAX_SL_PIPS,
    TP1_RR,
    TP2_RR,
)
from utils.logger import get_logger
from utils.pip_calculator import (
    get_pip_value,
    pips_to_price,
    price_to_pips,
)

logger = get_logger(__name__)


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate ATR(period) from OHLCV DataFrame. Returns last value."""
    if df is None or len(df) < period + 1:
        return 0.0

    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    atr = tr.rolling(window=period).mean()
    val = float(atr.iloc[-1])
    return val if not np.isnan(val) else 0.0


def calculate_sl_tp_atr(
    direction: str,
    entry_price: float,
    atr_value: float,
    instrument: str,
) -> Dict:
    """
    ATR-based SL / TP.
    SL = entry ± (SL_ATR_MULT * ATR)
    TP = entry ± (TP_ATR_MULT * ATR)
    """
    if atr_value <= 0:
        return {
            "valid": False,
            "reason": "invalid_atr",
            "sl": None,
            "tp1": None,
            "tp2": None,
            "sl_pip": 0,
            "rr1": 0,
            "rr2": 0,
            "fallback_used": False,
            "atr": 0,
        }

    if direction == "bullish":
        sl = entry_price - (SL_ATR_MULT * atr_value)
        tp = entry_price + (TP_ATR_MULT * atr_value)
    elif direction == "bearish":
        sl = entry_price + (SL_ATR_MULT * atr_value)
        tp = entry_price - (TP_ATR_MULT * atr_value)
    else:
        return {"valid": False, "reason": "invalid_direction"}

    sl_pips = price_to_pips(instrument, abs(entry_price - sl))

    logger.info(
        "ATR SL/TP %s %s | entry=%.5f | ATR=%.5f | SL=%.5f (%.1f pips) | TP=%.5f (%.1fx ATR)",
        instrument, direction, entry_price, atr_value, sl, sl_pips, tp, TP_ATR_MULT
    )

    return {
        "valid": True,
        "sl": round(sl, 5),
        "tp1": round(tp, 5),      # single TP at 5×ATR
        "tp2": None,
        "sl_pip": round(sl_pips, 1),
        "rr1": TP_ATR_MULT / SL_ATR_MULT,   # e.g. 5.0
        "rr2": 0,
        "fallback_used": False,
        "reason": None,
        "atr": round(atr_value, 5),
        "method": "ATR",
    }


def find_m15_swing(
    df: pd.DataFrame,
    direction: str,
    crt_sweep_level: Optional[float] = None
) -> Dict:
    """Kept for fallback / compatibility."""
    if df is None or len(df) < 5:
        return {"valid": False, "swing_low": None, "swing_high": None}

    closed = df.iloc[:-1]

    if crt_sweep_level:
        if direction == "bullish":
            return {"valid": True, "swing_low": crt_sweep_level, "swing_high": None}
        else:
            return {"valid": True, "swing_low": None, "swing_high": crt_sweep_level}

    window = 3
    swing_lows = []
    swing_highs = []

    for i in range(window, len(closed) - window):
        if closed["low"].iloc[i] == closed["low"].iloc[i - window:i + window + 1].min():
            swing_lows.append(float(closed["low"].iloc[i]))
        if closed["high"].iloc[i] == closed["high"].iloc[i - window:i + window + 1].max():
            swing_highs.append(float(closed["high"].iloc[i]))

    return {
        "valid": True,
        "swing_low": swing_lows[-1] if swing_lows else float(closed["low"].tail(5).min()),
        "swing_high": swing_highs[-1] if swing_highs else float(closed["high"].tail(5).max()),
    }


def find_m30_swing(df: pd.DataFrame, direction: str) -> Dict:
    """Kept for fallback."""
    if df is None or len(df) < 5:
        return {"valid": False, "swing_low": None, "swing_high": None}

    closed = df.iloc[:-1]
    window = 3
    swing_lows = []
    swing_highs = []

    for i in range(window, len(closed) - window):
        if closed["low"].iloc[i] == closed["low"].iloc[i - window:i + window + 1].min():
            swing_lows.append(float(closed["low"].iloc[i]))
        if closed["high"].iloc[i] == closed["high"].iloc[i - window:i + window + 1].max():
            swing_highs.append(float(closed["high"].iloc[i]))

    return {
        "valid": True,
        "swing_low": swing_lows[-1] if swing_lows else float(closed["low"].tail(5).min()),
        "swing_high": swing_highs[-1] if swing_highs else float(closed["high"].tail(5).max()),
    }


def calculate_sl_tp(
    direction: str,
    entry_price: float,
    crt_swing: Optional[Dict],
    m30_swing: Optional[Dict],
    instrument: str,
    atr_df: Optional[pd.DataFrame] = None,
) -> Dict:
    """
    Main entry point.
    Prefer ATR method when USE_ATR_SL_TP is True and we have data.
    """
    if USE_ATR_SL_TP and atr_df is not None:
        atr_val = calculate_atr(atr_df, ATR_PERIOD)
        if atr_val > 0:
            return calculate_sl_tp_atr(direction, entry_price, atr_val, instrument)

    # ---------- Original CRT swing fallback ----------
    buffer = pips_to_price(instrument, 2)

    if direction == "bullish":
        if crt_swing and crt_swing.get("swing_low"):
            sl_price = crt_swing["swing_low"] - buffer
        elif m30_swing and m30_swing.get("swing_low"):
            sl_price = m30_swing["swing_low"] - buffer
        else:
            sl_price = entry_price - pips_to_price(instrument, 15)
        sl_distance = entry_price - sl_price
        tp1 = entry_price + (sl_distance * TP1_RR)
        tp2 = entry_price + (sl_distance * TP2_RR)
    elif direction == "bearish":
        if crt_swing and crt_swing.get("swing_high"):
            sl_price = crt_swing["swing_high"] + buffer
        elif m30_swing and m30_swing.get("swing_high"):
            sl_price = m30_swing["swing_high"] + buffer
        else:
            sl_price = entry_price + pips_to_price(instrument, 15)
        sl_distance = sl_price - entry_price
        tp1 = entry_price - (sl_distance * TP1_RR)
        tp2 = entry_price - (sl_distance * TP2_RR)
    else:
        return {"valid": False, "reason": "invalid_direction"}

    sl_pips = price_to_pips(instrument, abs(entry_price - sl_price))

    return {
        "valid": True,
        "sl": round(sl_price, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "sl_pip": round(sl_pips, 1),
        "rr1": TP1_RR,
        "rr2": TP2_RR,
        "fallback_used": True,
        "reason": None,
        "method": "CRT_swing",
    }
