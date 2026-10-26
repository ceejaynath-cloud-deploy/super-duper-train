"""
Signal Builder (REDESIGNED)
Assembles final signal from H4 + H1 + M15 confluence.
Uses ATR-based SL/TP. AI narrative completely removed.
"""

from typing import Dict, Optional, List

from utils.logger import get_logger
from utils.time_utils import now_gmt, get_current_session, format_gmt
from risk.sl_tp_calculator import calculate_sl_tp, find_m15_swing, find_m30_swing
from risk.lot_sizer import calculate_lot_size
from config import (
    DEFAULT_CAPITAL,
    DEFAULT_RISK_PCT,
    MIN_CONFLUENCE_SCORE,
)

logger = get_logger(__name__)


class SignalBuilder:
    """Builds complete trading signals from analysis results."""

    def __init__(self):
        self.user_capital = {}
        self.user_risk = {}

    def set_user_risk(self, chat_id: int, capital: float, risk_pct: float) -> None:
        self.user_capital[chat_id] = capital
        self.user_risk[chat_id] = risk_pct
        logger.info("Risk set for user %d: capital=$%.0f, risk=%.1f%%", chat_id, capital, risk_pct)

    def get_user_risk(self, chat_id: int) -> tuple:
        capital = self.user_capital.get(chat_id, DEFAULT_CAPITAL)
        risk_pct = self.user_risk.get(chat_id, DEFAULT_RISK_PCT)
        return capital, risk_pct

    def build_signal(
        self,
        pair: str,
        confluence_results: Dict,
        dataframes: Dict,
        news_events: List,
        chat_id: int = 0,
    ) -> Optional[Dict]:
        if not confluence_results.get("confluence_passed", False):
            logger.info(
                "Signal for %s rejected: confluence failed (%d/%d)",
                pair,
                confluence_results.get("confluence_score", 0),
                MIN_CONFLUENCE_SCORE,
            )
            return None

        direction = confluence_results.get("direction")
        if not direction:
            logger.info("Signal for %s rejected: no direction", pair)
            return None

        # Prefer M15 close as entry (execution timeframe)
        m15_df = dataframes.get("M15")
        if m15_df is not None and len(m15_df) > 0:
            entry_price = float(m15_df["close"].iloc[-1])
        else:
            # fallback to H1
            h1_df = dataframes.get("H1")
            if h1_df is None or len(h1_df) < 1:
                logger.warning("No price data for entry on %s", pair)
                return None
            entry_price = float(h1_df["close"].iloc[-1])

        # ATR source: prefer H1, fallback M15
        atr_df = dataframes.get("H1")
        if atr_df is None or len(atr_df) < 20:
            atr_df = dataframes.get("M15")

        # CRT swing still calculated for fallback
        crt_swing = find_m15_swing(m15_df, direction) if m15_df is not None else None
        m30_swing = find_m30_swing(dataframes.get("M30"), direction) if dataframes.get("M30") is not None else None

        sl_tp = calculate_sl_tp(
            direction=direction,
            entry_price=entry_price,
            crt_swing=crt_swing,
            m30_swing=m30_swing,
            instrument=pair,
            atr_df=atr_df,
        )

        if not sl_tp.get("valid"):
            logger.warning("SL/TP calculation failed for %s: %s", pair, sl_tp.get("reason"))
            return None

        capital, risk_pct = self.get_user_risk(chat_id)
        risk = calculate_lot_size(
            capital=capital,
            risk_pct=risk_pct,
            sl_pips=sl_tp["sl_pip"],
            instrument=pair,
        )

        now = now_gmt()
        session = get_current_session(now)

        signal = {
            "pair": pair,
            "direction": direction,
            "session": session,
            "timestamp": format_gmt(now),
            "confluence_score": confluence_results["confluence_score"],
            "entry_price": round(entry_price, 5),
            "sl_tp": sl_tp,
            "risk": risk,
            "capital": capital,
            "risk_pct": risk_pct,
            "layers": confluence_results.get("layers", {}),
            "layer_results": confluence_results.get("layer_results", []),
            "news": news_events,
            "layer_summary": self._build_layer_summary(confluence_results),
            "narrative": None,  # AI removed
        }

        logger.info(
            "Signal built for %s %s: entry=%.5f, SL=%.5f, TP=%.5f, method=%s, lot=%.2f",
            pair, direction, entry_price,
            sl_tp["sl"], sl_tp.get("tp1"),
            sl_tp.get("method", "unknown"),
            risk.get("lot_size", 0),
        )
        return signal

    @staticmethod
    def _build_layer_summary(confluence_results: Dict) -> str:
        lines = []
        for lr in confluence_results.get("layer_results", []):
            icon = "PASS" if lr.get("valid", False) else "FAIL"
            lines.append(f"{lr.get('name', 'Unknown')}: {icon}")
        return " | ".join(lines)

    async def build_with_narrative(
        self,
        pair: str,
        confluence_results: Dict,
        dataframes: Dict,
        news_events: List,
        chat_id: int = 0,
    ) -> Optional[Dict]:
        """
        Compatibility wrapper. AI narrative is disabled.
        Just returns the normal signal.
        """
        signal = self.build_signal(pair, confluence_results, dataframes, news_events, chat_id)
        if signal:
            signal["narrative"] = "[AI narrative disabled in this redesign]"
        return signal
