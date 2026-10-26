"""
Trailing Stop Logic (REDESIGNED)
Moves SL every time price advances another 15% of the total distance
from Entry → Take Profit.
Locks in profit in 15% steps until TP is reached.
"""

from typing import Dict, Optional
from config import TRAILING_STEP_PCT
from utils.logger import get_logger

logger = get_logger(__name__)


class TrailingStopManager:
    """
    Step-based trailing stop.
    Every time price travels another TRAILING_STEP_PCT (default 15%)
    of the full Entry→TP distance, SL is moved to that level.
    """

    def __init__(
        self,
        instrument: str,
        direction: str,
        entry_price: float,
        initial_sl: float,
        tp_price: float,
        step_pct: float = TRAILING_STEP_PCT,
    ):
        self.instrument = instrument
        self.direction = direction
        self.entry_price = entry_price
        self.initial_sl = initial_sl
        self.current_sl = initial_sl
        self.tp_price = tp_price
        self.step_pct = step_pct
        self.total_distance = abs(tp_price - entry_price)
        self.steps_locked = 0
        self.active = False

        logger.info(
            "TrailingStop (15%% steps) init: %s %s entry=%.5f SL=%.5f TP=%.5f dist=%.5f",
            instrument, direction, entry_price, initial_sl, tp_price, self.total_distance
        )

    def update(self, current_price: float) -> Dict:
        """
        Update trailing stop based on current price.
        Returns dict with new SL and status.
        """
        if self.total_distance <= 0:
            return {
                "active": False,
                "current_sl": self.current_sl,
                "steps_locked": 0,
                "progress_pct": 0.0,
            }

        # Progress toward TP (0.0 → 1.0)
        if self.direction == "bullish":
            progress = (current_price - self.entry_price) / self.total_distance
        else:
            progress = (self.entry_price - current_price) / self.total_distance

        progress = max(0.0, min(1.0, progress))
        steps_done = int(progress // self.step_pct)

        if steps_done > self.steps_locked:
            self.steps_locked = steps_done
            self.active = True
            lock_ratio = self.steps_locked * self.step_pct

            if self.direction == "bullish":
                new_sl = self.entry_price + (lock_ratio * self.total_distance)
                # Never move SL down
                if new_sl > self.current_sl:
                    self.current_sl = new_sl
            else:
                new_sl = self.entry_price - (lock_ratio * self.total_distance)
                # Never move SL up
                if new_sl < self.current_sl:
                    self.current_sl = new_sl

            logger.info(
                "Trailing step %d locked (%.0f%%) → new SL=%.5f | price=%.5f",
                self.steps_locked, lock_ratio * 100, self.current_sl, current_price
            )

        return {
            "active": self.active,
            "current_sl": round(self.current_sl, 5),
            "steps_locked": self.steps_locked,
            "progress_pct": round(progress * 100, 1),
        }

    def should_exit(self, current_price: float) -> bool:
        """True if price has hit the current trailing stop."""
        if self.direction == "bullish":
            return current_price <= self.current_sl
        else:
            return current_price >= self.current_sl

    def get_status(self) -> Dict:
        return {
            "current_sl": round(self.current_sl, 5),
            "steps_locked": self.steps_locked,
            "active": self.active,
            "tp": self.tp_price,
        }
