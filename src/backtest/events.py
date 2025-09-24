"""Event classes for the backtesting engine."""

from abc import ABC
from datetime import datetime
from typing import Dict, Optional


class Event(ABC):
    """Base class for all events in the backtesting system."""
    pass


class BarEvent(Event):
    """Market data bar event."""

    def __init__(self, timestamp: datetime, bars: Dict[str, Dict[str, float]]) -> None:
        """Initialize bar event.

        Args:
            timestamp: Event timestamp
            bars: Dictionary of symbol -> OHLCV data
        """
        self.timestamp = timestamp
        self.bars = bars  # {symbol: {'open': x, 'high': x, 'low': x, 'close': x, 'volume': x}}

    def get_bar(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get bar data for a symbol.

        Args:
            symbol: Symbol to get data for

        Returns:
            Bar data or None if symbol not found
        """
        return self.bars.get(symbol)

    def __repr__(self) -> str:
        return f"BarEvent({self.timestamp}, {len(self.bars)} symbols)"


class OrderEvent(Event):
    """Order placement event."""

    def __init__(
        self,
        timestamp: datetime,
        symbol: str,
        order_type: str,
        quantity: float,
        direction: str,  # 'BUY' or 'SELL'
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> None:
        """Initialize order event.

        Args:
            timestamp: Order timestamp
            symbol: Symbol to trade
            order_type: Order type ('MARKET', 'LIMIT', etc.)
            quantity: Order quantity
            direction: Order direction
            limit_price: Limit price for limit orders
            stop_price: Stop price for stop orders
        """
        self.timestamp = timestamp
        self.symbol = symbol
        self.order_type = order_type.upper()
        self.quantity = abs(quantity)  # Always positive
        self.direction = direction.upper()
        self.limit_price = limit_price
        self.stop_price = stop_price
        
        # Calculated fields
        self.signed_quantity = quantity if direction.upper() == 'BUY' else -quantity

    def __repr__(self) -> str:
        return f"OrderEvent({self.direction} {self.quantity} {self.symbol} {self.order_type})"


class FillEvent(Event):
    """Order fill event."""

    def __init__(
        self,
        timestamp: datetime,
        symbol: str,
        quantity: float,
        direction: str,
        fill_price: float,
        commission: float = 0.0,
        slippage: float = 0.0,
    ) -> None:
        """Initialize fill event.

        Args:
            timestamp: Fill timestamp
            symbol: Symbol traded
            quantity: Quantity filled
            direction: Fill direction
            fill_price: Price at which order was filled
            commission: Commission paid
            slippage: Slippage applied
        """
        self.timestamp = timestamp
        self.symbol = symbol
        self.quantity = abs(quantity)
        self.direction = direction.upper()
        self.fill_price = fill_price
        self.commission = commission
        self.slippage = slippage
        
        # Calculated fields
        self.signed_quantity = quantity if direction.upper() == 'BUY' else -quantity
        self.gross_amount = self.quantity * self.fill_price
        self.net_amount = self.gross_amount - self.commission

    def __repr__(self) -> str:
        return f"FillEvent({self.direction} {self.quantity} {self.symbol} @ ${self.fill_price})"


class SignalEvent(Event):
    """Trading signal event."""

    def __init__(
        self,
        timestamp: datetime,
        symbol: str,
        signal_type: str,
        strength: float,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Initialize signal event.

        Args:
            timestamp: Signal timestamp
            symbol: Symbol for signal
            signal_type: Type of signal ('BUY', 'SELL', 'HOLD')
            strength: Signal strength (0-1)
            metadata: Additional signal data
        """
        self.timestamp = timestamp
        self.symbol = symbol
        self.signal_type = signal_type.upper()
        self.strength = max(0, min(1, strength))
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"SignalEvent({self.symbol} {self.signal_type} {self.strength:.2f})"