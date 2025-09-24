"""Simulated execution handler for backtesting."""

from typing import Optional

import numpy as np

from src.backtest.events import FillEvent, OrderEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class SimulatedExecutionHandler:
    """Simulated execution handler that fills orders with slippage and commission."""

    def __init__(
        self,
        commission_per_share: float = 0.0,
        slippage_bps: float = 5.0,
        market_impact_coeff: float = 0.1,
    ) -> None:
        """Initialize execution handler.

        Args:
            commission_per_share: Commission per share
            slippage_bps: Slippage in basis points
            market_impact_coeff: Market impact coefficient
        """
        self.commission_per_share = commission_per_share
        self.slippage_bps = slippage_bps
        self.market_impact_coeff = market_impact_coeff
        self.logger = logger

    def calculate_slippage(
        self, order: OrderEvent, bar: dict, base_slippage_bps: Optional[float] = None
    ) -> float:
        """Calculate slippage for an order.

        Args:
            order: Order to calculate slippage for
            bar: Current bar data
            base_slippage_bps: Override base slippage

        Returns:
            Slippage amount in price units
        """
        base_slippage = base_slippage_bps or self.slippage_bps
        current_price = bar["close"]

        # Base slippage
        slippage_amount = current_price * (base_slippage / 10000.0)

        # Add market impact based on order size relative to volume
        volume = bar.get("volume", 1000000)  # Default volume if not available
        if volume > 0:
            volume_ratio = order.quantity / volume
            market_impact = current_price * volume_ratio * self.market_impact_coeff
            slippage_amount += market_impact

        # Add some randomness to slippage
        random_factor = np.random.normal(1.0, 0.2)  # ±20% variation
        slippage_amount *= random_factor

        return abs(slippage_amount)  # Always positive

    def calculate_fill_price(
        self, order: OrderEvent, bar: dict, slippage: float
    ) -> float:
        """Calculate fill price including slippage.

        Args:
            order: Order being filled
            bar: Current bar data
            slippage: Slippage amount

        Returns:
            Fill price
        """
        if order.order_type == "MARKET":
            # Use close price as base for market orders
            base_price = bar["close"]

            # Apply slippage
            if order.direction == "BUY":
                fill_price = base_price + slippage  # Pay higher when buying
            else:
                fill_price = base_price - slippage  # Receive less when selling

            # Ensure fill price is within reasonable bounds (high-low range)
            fill_price = max(min(fill_price, bar["high"]), bar["low"])

        elif order.order_type == "LIMIT":
            # For limit orders, check if limit price would be hit
            if order.direction == "BUY":
                # Buy limit order fills if market goes at or below limit price
                if bar["low"] <= order.limit_price:
                    fill_price = min(order.limit_price, bar["close"] + slippage)
                else:
                    # Order not filled
                    return None
            else:
                # Sell limit order fills if market goes at or above limit price
                if bar["high"] >= order.limit_price:
                    fill_price = max(order.limit_price, bar["close"] - slippage)
                else:
                    # Order not filled
                    return None

        else:
            # For other order types, default to market execution
            fill_price = bar["close"]
            if order.direction == "BUY":
                fill_price += slippage
            else:
                fill_price -= slippage

        return round(fill_price, 4)  # Round to 4 decimal places

    def execute_order(self, order: OrderEvent, bar: dict) -> Optional[FillEvent]:
        """Execute an order and return fill event.

        Args:
            order: Order to execute
            bar: Current bar data for the symbol

        Returns:
            Fill event if order is filled, None if not filled
        """
        # Calculate slippage
        slippage_amount = self.calculate_slippage(order, bar)

        # Calculate fill price
        fill_price = self.calculate_fill_price(order, bar, slippage_amount)

        if fill_price is None:
            # Order not filled (e.g., limit order price not reached)
            self.logger.debug(f"Order not filled: {order}")
            return None

        # Calculate commission
        commission = self.commission_per_share * order.quantity

        # Create fill event
        fill_event = FillEvent(
            timestamp=order.timestamp,
            symbol=order.symbol,
            quantity=order.quantity,
            direction=order.direction,
            fill_price=fill_price,
            commission=commission,
            slippage=slippage_amount,
        )

        self.logger.debug(
            f"Filled order: {order.direction} {order.quantity} {order.symbol} "
            f"@ ${fill_price:.4f} (slippage: ${slippage_amount:.4f}, commission: ${commission:.2f})"
        )

        return fill_event
