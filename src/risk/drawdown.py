"""Drawdown monitoring and management."""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import pandas as pd

from src.config import config
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DrawdownManager:
    """Manager for monitoring and controlling portfolio drawdowns."""

    def __init__(self) -> None:
        """Initialize drawdown manager."""
        self.max_drawdown_pct = config.risk.max_drawdown_pct
        self.max_daily_loss_pct = config.risk.max_daily_loss_pct

        # State tracking
        self.equity_curve: List[Tuple[datetime, float]] = []
        self.daily_pnl: List[Tuple[datetime, float]] = []
        self.current_drawdown = 0.0
        self.max_drawdown_reached = 0.0
        self.peak_value = 0.0
        self.last_peak_date = None

        # Risk state
        self.is_max_drawdown_breached = False
        self.is_daily_loss_breached = False
        self.trading_halted = False

        self.logger = logger

    def update(self, timestamp: datetime, portfolio_value: float) -> None:
        """Update drawdown calculations with new portfolio value.

        Args:
            timestamp: Current timestamp
            portfolio_value: Current portfolio value
        """
        # Add to equity curve
        self.equity_curve.append((timestamp, portfolio_value))

        # Calculate daily PnL
        if len(self.equity_curve) > 1:
            prev_value = self.equity_curve[-2][1]
            daily_pnl = portfolio_value - prev_value
            self.daily_pnl.append((timestamp, daily_pnl))

        # Update peak
        if portfolio_value > self.peak_value:
            self.peak_value = portfolio_value
            self.last_peak_date = timestamp

        # Calculate current drawdown
        if self.peak_value > 0:
            self.current_drawdown = (
                self.peak_value - portfolio_value
            ) / self.peak_value
            self.max_drawdown_reached = max(
                self.max_drawdown_reached, self.current_drawdown
            )

        # Check drawdown breach
        if self.current_drawdown > self.max_drawdown_pct:
            if not self.is_max_drawdown_breached:
                self.logger.error(
                    f"Maximum drawdown breached: {self.current_drawdown:.2%} > "
                    f"{self.max_drawdown_pct:.2%}"
                )
                self.is_max_drawdown_breached = True
                self.trading_halted = True

        # Check daily loss
        if len(self.daily_pnl) > 0:
            daily_pnl = self.daily_pnl[-1][1]
            daily_loss_pct = (
                abs(daily_pnl) / self.peak_value if self.peak_value > 0 else 0
            )

            if daily_pnl < 0 and daily_loss_pct > self.max_daily_loss_pct:
                if not self.is_daily_loss_breached:
                    self.logger.error(
                        f"Daily loss limit breached: {daily_loss_pct:.2%} > "
                        f"{self.max_daily_loss_pct:.2%}"
                    )
                    self.is_daily_loss_breached = True
                    self.trading_halted = True

    def should_halt_trading(self) -> bool:
        """Check if trading should be halted due to risk limits.

        Returns:
            True if trading should be halted
        """
        return self.trading_halted

    def get_drawdown_stats(self) -> dict:
        """Get current drawdown statistics.

        Returns:
            Dictionary of drawdown statistics
        """
        if not self.equity_curve:
            return {}

        # Calculate drawdown duration
        drawdown_days = 0
        if self.last_peak_date and self.current_drawdown > 0:
            latest_date = self.equity_curve[-1][0]
            drawdown_days = (latest_date - self.last_peak_date).days

        return {
            "current_drawdown": self.current_drawdown,
            "max_drawdown": self.max_drawdown_reached,
            "peak_value": self.peak_value,
            "last_peak_date": self.last_peak_date,
            "drawdown_days": drawdown_days,
            "is_max_drawdown_breached": self.is_max_drawdown_breached,
            "is_daily_loss_breached": self.is_daily_loss_breached,
            "trading_halted": self.trading_halted,
        }

    def reset_daily_flags(self) -> None:
        """Reset daily flags (call at start of new trading day)."""
        self.is_daily_loss_breached = False

        # Only reset trading halt if not due to max drawdown
        if not self.is_max_drawdown_breached:
            self.trading_halted = False

    def reset_all(self) -> None:
        """Reset all drawdown tracking (use with caution)."""
        self.equity_curve = []
        self.daily_pnl = []
        self.current_drawdown = 0.0
        self.max_drawdown_reached = 0.0
        self.peak_value = 0.0
        self.last_peak_date = None
        self.is_max_drawdown_breached = False
        self.is_daily_loss_breached = False
        self.trading_halted = False
        self.logger.info("Drawdown manager reset")

    def calculate_historical_drawdowns(self, equity_curve: pd.Series) -> pd.DataFrame:
        """Calculate historical drawdowns from equity curve.

        Args:
            equity_curve: Time series of portfolio values

        Returns:
            DataFrame with drawdown statistics
        """
        if equity_curve.empty:
            return pd.DataFrame()

        # Calculate running maximum (peaks)
        peaks = equity_curve.cummax()

        # Calculate drawdowns
        drawdowns = (equity_curve - peaks) / peaks

        # Find drawdown periods
        in_drawdown = drawdowns < 0
        drawdown_starts = in_drawdown & ~in_drawdown.shift(1, fill_value=False)
        drawdown_ends = ~in_drawdown & in_drawdown.shift(1, fill_value=False)

        # Match starts and ends
        starts = drawdowns[drawdown_starts].index
        ends = drawdowns[drawdown_ends].index

        # Handle case where we're currently in drawdown
        if len(starts) > len(ends):
            ends = ends.append(pd.Index([drawdowns.index[-1]]))

        drawdown_periods = []
        for start, end in zip(starts, ends):
            period_drawdowns = drawdowns[start:end]
            min_drawdown = period_drawdowns.min()
            min_date = period_drawdowns.idxmin()

            drawdown_periods.append(
                {
                    "start_date": start,
                    "end_date": end,
                    "trough_date": min_date,
                    "max_drawdown": min_drawdown,
                    "duration_days": (end - start).days,
                    "recovery_days": (end - min_date).days if end > min_date else 0,
                }
            )

        return pd.DataFrame(drawdown_periods)

    def get_risk_adjusted_position_size(
        self, base_position_size: float, current_drawdown: Optional[float] = None
    ) -> float:
        """Adjust position size based on current drawdown.

        Args:
            base_position_size: Base position size
            current_drawdown: Current drawdown (uses internal if None)

        Returns:
            Risk-adjusted position size
        """
        drawdown = (
            current_drawdown if current_drawdown is not None else self.current_drawdown
        )

        # Reduce position size as drawdown increases
        if drawdown <= 0.02:  # <= 2% drawdown
            scale_factor = 1.0
        elif drawdown <= 0.05:  # 2-5% drawdown
            scale_factor = 0.8
        elif drawdown <= 0.08:  # 5-8% drawdown
            scale_factor = 0.6
        else:  # > 8% drawdown
            scale_factor = 0.4

        adjusted_size = base_position_size * scale_factor

        if scale_factor < 1.0:
            self.logger.info(
                f"Position size scaled by {scale_factor:.1f} due to "
                f"{drawdown:.2%} drawdown"
            )

        return adjusted_size
