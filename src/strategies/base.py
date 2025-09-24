"""Base strategy class for all trading strategies."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)


class Signal:
    """Trading signal representation."""

    def __init__(
        self,
        symbol: str,
        signal_type: str,  # 'BUY', 'SELL', 'HOLD'
        strength: float,  # Signal strength 0-1
        timestamp: datetime,
        metadata: Optional[Dict] = None,
    ) -> None:
        """Initialize trading signal.

        Args:
            symbol: Asset symbol
            signal_type: Type of signal
            strength: Signal strength (0-1)
            timestamp: Signal timestamp
            metadata: Additional signal metadata
        """
        self.symbol = symbol
        self.signal_type = signal_type.upper()
        self.strength = max(0, min(1, strength))  # Clamp to 0-1
        self.timestamp = timestamp
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"Signal({self.symbol}, {self.signal_type}, {self.strength:.2f})"


class BaseStrategy(ABC):
    """Abstract base class for all trading strategies."""

    def __init__(self, name: str, config: Dict) -> None:
        """Initialize strategy.

        Args:
            name: Strategy name
            config: Strategy configuration
        """
        self.name = name
        self.config = config
        self.logger = logger.bind(strategy=name)
        self.initialized = False
        self.universe: List[str] = []
        self.historical_data: pd.DataFrame = pd.DataFrame()

        # Performance tracking
        self.signals_generated = 0
        self.last_update = None

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, timestamp: datetime) -> List[Signal]:
        """Generate trading signals based on current data.

        Args:
            data: Historical market data
            timestamp: Current timestamp

        Returns:
            List of trading signals
        """
        pass

    @abstractmethod
    def calculate_position_sizes(
        self,
        signals: List[Signal],
        portfolio_value: float,
        current_positions: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate position sizes based on signals.

        Args:
            signals: Generated trading signals
            portfolio_value: Current portfolio value
            current_positions: Current positions {symbol: quantity}

        Returns:
            Target positions {symbol: target_quantity}
        """
        pass

    def initialize(self, universe: List[str], historical_data: pd.DataFrame) -> None:
        """Initialize strategy with universe and historical data.

        Args:
            universe: List of tradable symbols
            historical_data: Historical price data
        """
        self.universe = universe
        self.historical_data = historical_data
        self.initialized = True

        self.logger.info(
            f"Initialized {self.name} strategy with {len(universe)} symbols "
            f"and {len(historical_data)} data points"
        )

    def update_data(self, new_data: pd.DataFrame) -> None:
        """Update strategy with new market data.

        Args:
            new_data: New market data
        """
        if not self.initialized:
            raise RuntimeError("Strategy not initialized")

        # Append new data and keep only recent history
        self.historical_data = pd.concat([self.historical_data, new_data])

        # Keep only recent data to manage memory
        lookback_days = self.config.get("lookback_days", 252)
        if len(self.historical_data) > 0:
            cutoff_date = self.historical_data["datetime"].max() - pd.Timedelta(
                days=lookback_days
            )
            self.historical_data = self.historical_data[
                self.historical_data["datetime"] >= cutoff_date
            ]

        self.last_update = datetime.now()

    def get_strategy_metrics(self) -> Dict:
        """Get strategy performance metrics.

        Returns:
            Dictionary of strategy metrics
        """
        return {
            "name": self.name,
            "initialized": self.initialized,
            "universe_size": len(self.universe),
            "signals_generated": self.signals_generated,
            "last_update": self.last_update,
            "data_points": len(self.historical_data),
        }

    def validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """Validate generated signals.

        Args:
            signals: List of signals to validate

        Returns:
            List of validated signals
        """
        valid_signals = []

        for signal in signals:
            # Check if symbol is in universe
            if signal.symbol not in self.universe:
                self.logger.warning(
                    f"Signal for {signal.symbol} not in universe, skipping"
                )
                continue

            # Check signal type
            if signal.signal_type not in ["BUY", "SELL", "HOLD"]:
                self.logger.warning(
                    f"Invalid signal type {signal.signal_type}, skipping"
                )
                continue

            # Check signal strength
            if not 0 <= signal.strength <= 1:
                self.logger.warning(
                    f"Invalid signal strength {signal.strength}, clamping"
                )
                signal.strength = max(0, min(1, signal.strength))

            valid_signals.append(signal)

        return valid_signals

    def run(
        self,
        timestamp: datetime,
        portfolio_value: float,
        current_positions: Dict[str, float],
    ) -> Tuple[List[Signal], Dict[str, float]]:
        """Main strategy execution method.

        Args:
            timestamp: Current timestamp
            portfolio_value: Current portfolio value
            current_positions: Current positions

        Returns:
            Tuple of (signals, target_positions)
        """
        if not self.initialized:
            raise RuntimeError("Strategy not initialized")

        # Generate signals
        signals = self.generate_signals(self.historical_data, timestamp)

        # Validate signals
        signals = self.validate_signals(signals)

        # Calculate position sizes
        target_positions = self.calculate_position_sizes(
            signals, portfolio_value, current_positions
        )

        self.signals_generated += len(signals)

        self.logger.info(
            f"Generated {len(signals)} signals, {len(target_positions)} position targets"
        )

        return signals, target_positions
