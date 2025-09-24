"""Mean reversion trading strategy implementation."""

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import coint

from src.strategies.base import BaseStrategy, Signal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class MeanReversionStrategy(BaseStrategy):
    """Mean reversion strategy using statistical arbitrage and pairs trading."""

    def __init__(self, config: Dict) -> None:
        """Initialize mean reversion strategy.

        Args:
            config: Strategy configuration
        """
        super().__init__("MeanReversion", config)
        
        # Strategy parameters
        self.lookback_days = config.get('lookback_days', 20)
        self.zscore_threshold = config.get('zscore_threshold', 2.0)
        self.pairs_count = config.get('pairs_count', 10)
        self.half_life_days = config.get('half_life_days', 5)
        self.cointegration_window = config.get('cointegration_window', 60)
        
        # State tracking
        self.cointegrated_pairs = []
        self.pair_spreads = {}
        self.last_pair_selection = None

    def find_cointegrated_pairs(
        self, data: pd.DataFrame, timestamp: datetime
    ) -> List[Tuple[str, str]]:
        """Find cointegrated pairs for trading.

        Args:
            data: Historical price data
            timestamp: Current timestamp

        Returns:
            List of cointegrated symbol pairs
        """
        # Only recalculate pairs periodically to save computation
        if (self.last_pair_selection is not None and 
            (timestamp - self.last_pair_selection).days < 7):
            return self.cointegrated_pairs
        
        pairs = []
        
        # Filter data to cointegration window
        lookback_date = timestamp - timedelta(days=self.cointegration_window + 5)
        recent_data = data[data['datetime'] >= lookback_date].copy()
        
        if recent_data.empty:
            self.logger.warning("No recent data for cointegration analysis")
            return pairs
        
        # Create price pivot table
        price_pivot = recent_data.pivot_table(
            index='datetime', columns='symbol', values='close'
        )
        
        # Fill missing values
        price_pivot = price_pivot.fillna(method='ffill').dropna(axis=1)
        
        symbols = price_pivot.columns.tolist()
        
        if len(symbols) < 2:
            self.logger.warning("Not enough symbols for pair analysis")
            return pairs
        
        self.logger.info(f"Testing cointegration for {len(symbols)} symbols")
        
        # Test all symbol pairs for cointegration
        tested_pairs = 0
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                symbol1, symbol2 = symbols[i], symbols[j]
                
                # Get price series
                series1 = price_pivot[symbol1].dropna()
                series2 = price_pivot[symbol2].dropna()
                
                # Need minimum data points
                if len(series1) < 30 or len(series2) < 30:
                    continue
                
                # Align series
                aligned_data = pd.concat([series1, series2], axis=1).dropna()
                if len(aligned_data) < 30:
                    continue
                
                try:
                    # Test cointegration
                    score, pvalue, _ = coint(aligned_data.iloc[:, 0], aligned_data.iloc[:, 1])
                    
                    # If p-value < 0.05, pairs are cointegrated
                    if pvalue < 0.05:
                        pairs.append((symbol1, symbol2))
                        
                        self.logger.debug(
                            f"Found cointegrated pair: {symbol1}-{symbol2} "
                            f"(p-value: {pvalue:.4f})"
                        )
                        
                        # Limit number of pairs to manage complexity
                        if len(pairs) >= self.pairs_count:
                            break
                    
                    tested_pairs += 1
                    
                except Exception as e:
                    self.logger.debug(f"Cointegration test failed for {symbol1}-{symbol2}: {e}")
                    continue
            
            if len(pairs) >= self.pairs_count:
                break
        
        self.cointegrated_pairs = pairs
        self.last_pair_selection = timestamp
        
        self.logger.info(
            f"Found {len(pairs)} cointegrated pairs out of {tested_pairs} tested"
        )
        
        return pairs

    def calculate_pair_signals(
        self, data: pd.DataFrame, timestamp: datetime
    ) -> List[Signal]:
        """Calculate mean reversion signals for pairs.

        Args:
            data: Historical price data
            timestamp: Current timestamp

        Returns:
            List of trading signals
        """
        signals = []
        
        if not self.cointegrated_pairs:
            return signals
        
        # Filter data to lookback period
        lookback_date = timestamp - timedelta(days=self.lookback_days + 5)
        recent_data = data[data['datetime'] >= lookback_date].copy()
        
        if recent_data.empty:
            return signals
        
        # Create price pivot
        price_pivot = recent_data.pivot_table(
            index='datetime', columns='symbol', values='close'
        )
        price_pivot = price_pivot.fillna(method='ffill')
        
        for symbol1, symbol2 in self.cointegrated_pairs:
            try:
                if symbol1 not in price_pivot.columns or symbol2 not in price_pivot.columns:
                    continue
                
                # Get price series
                series1 = price_pivot[symbol1].dropna()
                series2 = price_pivot[symbol2].dropna()
                
                # Align series
                aligned_data = pd.concat([series1, series2], axis=1).dropna()
                
                if len(aligned_data) < self.lookback_days:
                    continue
                
                # Take recent data
                recent_aligned = aligned_data.tail(self.lookback_days)
                
                # Calculate spread (residuals from linear regression)
                from sklearn.linear_model import LinearRegression
                
                X = recent_aligned.iloc[:, 0].values.reshape(-1, 1)
                y = recent_aligned.iloc[:, 1].values
                
                model = LinearRegression().fit(X, y)
                spread = y - model.predict(X)
                
                # Calculate z-score of current spread
                current_spread = spread[-1]
                spread_mean = np.mean(spread)
                spread_std = np.std(spread)
                
                if spread_std == 0:
                    continue
                
                zscore = (current_spread - spread_mean) / spread_std
                
                # Store spread for tracking
                pair_key = f"{symbol1}_{symbol2}"
                self.pair_spreads[pair_key] = {
                    'current_spread': current_spread,
                    'zscore': zscore,
                    'timestamp': timestamp
                }
                
                # Generate signals based on z-score
                if abs(zscore) > self.zscore_threshold:
                    signal_strength = min(abs(zscore) / self.zscore_threshold, 2.0) / 2.0
                    
                    if zscore > self.zscore_threshold:
                        # Spread is high: short symbol2 (overvalued), long symbol1 (undervalued)
                        signals.append(Signal(
                            symbol=symbol1,
                            signal_type="BUY",
                            strength=signal_strength,
                            timestamp=timestamp,
                            metadata={
                                'pair': pair_key,
                                'zscore': zscore,
                                'strategy': 'mean_reversion'
                            }
                        ))
                        
                        signals.append(Signal(
                            symbol=symbol2,
                            signal_type="SELL",
                            strength=signal_strength,
                            timestamp=timestamp,
                            metadata={
                                'pair': pair_key,
                                'zscore': zscore,
                                'strategy': 'mean_reversion'
                            }
                        ))
                    
                    elif zscore < -self.zscore_threshold:
                        # Spread is low: long symbol2 (undervalued), short symbol1 (overvalued)
                        signals.append(Signal(
                            symbol=symbol1,
                            signal_type="SELL",
                            strength=signal_strength,
                            timestamp=timestamp,
                            metadata={
                                'pair': pair_key,
                                'zscore': zscore,
                                'strategy': 'mean_reversion'
                            }
                        ))
                        
                        signals.append(Signal(
                            symbol=symbol2,
                            signal_type="BUY",
                            strength=signal_strength,
                            timestamp=timestamp,
                            metadata={
                                'pair': pair_key,
                                'zscore': zscore,
                                'strategy': 'mean_reversion'
                            }
                        ))
                
            except Exception as e:
                self.logger.debug(f"Error calculating pair signal for {symbol1}-{symbol2}: {e}")
                continue
        
        return signals

    def generate_signals(self, data: pd.DataFrame, timestamp: datetime) -> List[Signal]:
        """Generate mean reversion trading signals.

        Args:
            data: Historical market data
            timestamp: Current timestamp

        Returns:
            List of trading signals
        """
        # Find cointegrated pairs
        pairs = self.find_cointegrated_pairs(data, timestamp)
        
        if not pairs:
            self.logger.info("No cointegrated pairs found")
            return []
        
        # Calculate pair-based signals
        signals = self.calculate_pair_signals(data, timestamp)
        
        self.logger.info(f"Generated {len(signals)} mean reversion signals")
        
        return signals

    def calculate_position_sizes(
        self,
        signals: List[Signal],
        portfolio_value: float,
        current_positions: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate position sizes for mean reversion signals.

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
        
        # Group signals by pairs
        pair_signals = {}
        for signal in signals:
            pair_key = signal.metadata.get('pair', '')
            if pair_key not in pair_signals:
                pair_signals[pair_key] = []
            pair_signals[pair_key].append(signal)
        
        # Calculate position sizes for each pair
        if pair_signals:
            # Equal allocation across pairs
            capital_per_pair = portfolio_value / len(pair_signals)
            
            latest_prices = self._get_latest_prices(signals)
            
            for pair_key, pair_signal_list in pair_signals.items():
                # Each leg gets half the pair allocation
                capital_per_leg = capital_per_pair / 2
                
                for signal in pair_signal_list:
                    if signal.symbol in latest_prices and latest_prices[signal.symbol] > 0:
                        # Calculate target dollar amount
                        target_value = capital_per_leg * signal.strength
                        
                        # Convert to shares
                        target_shares = target_value / latest_prices[signal.symbol]
                        
                        # Apply sign based on signal type
                        if signal.signal_type == "SELL":
                            target_shares = -target_shares  # Short position
                        
                        target_positions[signal.symbol] = target_shares
        
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