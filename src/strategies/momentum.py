"""Momentum trading strategy implementation."""

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd

from src.strategies.base import BaseStrategy, Signal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MomentumStrategy(BaseStrategy):
    """Momentum strategy that buys high-momentum stocks and sells low-momentum stocks."""

    def __init__(self, config: Dict) -> None:
        """Initialize momentum strategy.

        Args:
            config: Strategy configuration
        """
        super().__init__("Momentum", config)
        
        # Strategy parameters
        self.lookback_days = config.get('lookback_days', 21)
        self.top_n_stocks = config.get('top_n_stocks', 20)
        self.momentum_threshold = config.get('momentum_threshold', 0.02)
        self.rebalance_frequency = config.get('rebalance_frequency', 'daily')
        
        # State tracking
        self.last_rebalance = None
        self.momentum_scores = {}

    def calculate_momentum(
        self, data: pd.DataFrame, timestamp: datetime
    ) -> Dict[str, float]:
        """Calculate momentum scores for all symbols.

        Args:
            data: Historical price data
            timestamp: Current timestamp

        Returns:
            Dictionary of momentum scores by symbol
        """
        momentum_scores = {}
        
        # Filter data to lookback period
        lookback_date = timestamp - timedelta(days=self.lookback_days + 5)  # Buffer
        recent_data = data[data['datetime'] >= lookback_date].copy()
        
        if recent_data.empty:
            self.logger.warning("No recent data available for momentum calculation")
            return momentum_scores
        
        for symbol in self.universe:
            symbol_data = recent_data[recent_data['symbol'] == symbol].copy()
            
            if len(symbol_data) < self.lookback_days:
                continue
            
            # Sort by date and take last N days
            symbol_data = symbol_data.sort_values('datetime').tail(self.lookback_days)
            
            if len(symbol_data) < 2:
                continue
            
            # Calculate momentum as total return over lookback period
            start_price = symbol_data.iloc[0]['close']
            end_price = symbol_data.iloc[-1]['close']
            
            if start_price > 0:
                momentum = (end_price - start_price) / start_price
                
                # Adjust for volatility (risk-adjusted momentum)
                returns = symbol_data['close'].pct_change().dropna()
                if len(returns) > 1:
                    volatility = returns.std() * np.sqrt(252)  # Annualized volatility
                    if volatility > 0:
                        risk_adjusted_momentum = momentum / volatility
                    else:
                        risk_adjusted_momentum = momentum
                else:
                    risk_adjusted_momentum = momentum
                
                momentum_scores[symbol] = risk_adjusted_momentum
        
        self.momentum_scores = momentum_scores
        self.logger.info(f"Calculated momentum for {len(momentum_scores)} symbols")
        
        return momentum_scores

    def should_rebalance(self, timestamp: datetime) -> bool:
        """Check if portfolio should be rebalanced.

        Args:
            timestamp: Current timestamp

        Returns:
            True if should rebalance
        """
        if self.last_rebalance is None:
            return True
        
        if self.rebalance_frequency == 'daily':
            return timestamp.date() > self.last_rebalance.date()
        elif self.rebalance_frequency == 'weekly':
            return (timestamp - self.last_rebalance).days >= 7
        elif self.rebalance_frequency == 'monthly':
            return (timestamp - self.last_rebalance).days >= 30
        
        return False

    def generate_signals(self, data: pd.DataFrame, timestamp: datetime) -> List[Signal]:
        """Generate momentum-based trading signals.

        Args:
            data: Historical market data
            timestamp: Current timestamp

        Returns:
            List of trading signals
        """
        signals = []
        
        # Check if we should rebalance
        if not self.should_rebalance(timestamp):
            self.logger.info("No rebalancing needed")
            return signals
        
        # Calculate momentum scores
        momentum_scores = self.calculate_momentum(data, timestamp)
        
        if not momentum_scores:
            self.logger.warning("No momentum scores calculated")
            return signals
        
        # Sort symbols by momentum score
        sorted_symbols = sorted(
            momentum_scores.items(), key=lambda x: x[1], reverse=True
        )
        
        # Generate BUY signals for top momentum stocks
        top_symbols = sorted_symbols[:self.top_n_stocks]
        for symbol, momentum in top_symbols:
            if momentum > self.momentum_threshold:
                # Signal strength based on momentum rank and absolute momentum
                rank_strength = 1 - (sorted_symbols.index((symbol, momentum)) / len(sorted_symbols))
                momentum_strength = min(abs(momentum) * 2, 1.0)  # Scale momentum to 0-1
                signal_strength = (rank_strength + momentum_strength) / 2
                
                signals.append(Signal(
                    symbol=symbol,
                    signal_type="BUY",
                    strength=signal_strength,
                    timestamp=timestamp,
                    metadata={
                        'momentum_score': momentum,
                        'rank': sorted_symbols.index((symbol, momentum)) + 1,
                        'strategy': 'momentum'
                    }
                ))
        
        # Generate SELL signals for bottom momentum stocks (if they're negative momentum)
        bottom_symbols = sorted_symbols[-self.top_n_stocks:]
        for symbol, momentum in bottom_symbols:
            if momentum < -self.momentum_threshold:
                signals.append(Signal(
                    symbol=symbol,
                    signal_type="SELL",
                    strength=min(abs(momentum) * 2, 1.0),
                    timestamp=timestamp,
                    metadata={
                        'momentum_score': momentum,
                        'rank': sorted_symbols.index((symbol, momentum)) + 1,
                        'strategy': 'momentum'
                    }
                ))
        
        self.last_rebalance = timestamp
        self.logger.info(f"Generated {len(signals)} momentum signals")
        
        return signals

    def calculate_position_sizes(
        self,
        signals: List[Signal],
        portfolio_value: float,
        current_positions: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate equal-weight position sizes for momentum signals.

        Args:
            signals: Generated trading signals
            portfolio_value: Current portfolio value
            current_positions: Current positions

        Returns:
            Target positions dictionary
        """
        target_positions = {}
        
        # Start with current positions
        for symbol in current_positions:
            target_positions[symbol] = current_positions[symbol]
        
        # Get buy signals
        buy_signals = [s for s in signals if s.signal_type == "BUY"]
        sell_signals = [s for s in signals if s.signal_type == "SELL"]
        
        # Set sell positions to zero
        for signal in sell_signals:
            target_positions[signal.symbol] = 0
        
        # Calculate equal weights for buy signals
        if buy_signals:
            weight_per_position = 1.0 / len(buy_signals)
            
            # Get latest prices for position sizing
            latest_prices = self._get_latest_prices(buy_signals)
            
            for signal in buy_signals:
                if signal.symbol in latest_prices and latest_prices[signal.symbol] > 0:
                    # Calculate target dollar amount
                    target_value = portfolio_value * weight_per_position * signal.strength
                    
                    # Convert to shares
                    target_shares = target_value / latest_prices[signal.symbol]
                    target_positions[signal.symbol] = target_shares
        
        # Remove zero positions
        target_positions = {k: v for k, v in target_positions.items() if v > 0}
        
        self.logger.info(f"Calculated position sizes for {len(target_positions)} symbols")
        
        return target_positions

    def _get_latest_prices(self, signals: List[Signal]) -> Dict[str, float]:
        """Get latest prices for signals.

        Args:
            signals: List of signals

        Returns:
            Dictionary of latest prices
        """
        prices = {}
        
        if self.historical_data.empty:
            return prices
        
        # Get latest date in data
        latest_date = self.historical_data['datetime'].max()
        latest_data = self.historical_data[
            self.historical_data['datetime'] == latest_date
        ]
        
        for signal in signals:
            symbol_data = latest_data[latest_data['symbol'] == signal.symbol]
            if not symbol_data.empty:
                prices[signal.symbol] = symbol_data.iloc[0]['close']
        
        return prices