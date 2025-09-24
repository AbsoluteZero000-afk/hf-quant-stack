"""Tests for trading strategies."""

import pytest
from datetime import datetime
import pandas as pd
import numpy as np

from src.strategies.momentum import MomentumStrategy
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.risk_parity import RiskParityStrategy


class TestMomentumStrategy:
    """Test cases for momentum strategy."""

    def test_strategy_initialization(self):
        """Test strategy initialization."""
        config = {
            'lookback_days': 21,
            'top_n_stocks': 10,
            'momentum_threshold': 0.02
        }
        strategy = MomentumStrategy(config)
        
        assert strategy.name == "Momentum"
        assert strategy.lookback_days == 21
        assert strategy.top_n_stocks == 10
        assert not strategy.initialized

    def test_strategy_initialization_with_data(self):
        """Test strategy initialization with sample data."""
        config = {'lookback_days': 21, 'top_n_stocks': 10}
        strategy = MomentumStrategy(config)
        
        # Create sample data
        symbols = ['AAPL', 'MSFT', 'GOOGL']
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        
        data_list = []
        for symbol in symbols:
            for date in dates:
                data_list.append({
                    'symbol': symbol,
                    'datetime': date,
                    'close': 100 + np.random.randn() * 5,
                    'volume': 1000000
                })
        
        data = pd.DataFrame(data_list)
        
        strategy.initialize(symbols, data)
        
        assert strategy.initialized
        assert len(strategy.universe) == 3
        assert len(strategy.historical_data) > 0


class TestMeanReversionStrategy:
    """Test cases for mean reversion strategy."""

    def test_strategy_initialization(self):
        """Test mean reversion strategy initialization."""
        config = {
            'lookback_days': 20,
            'zscore_threshold': 2.0,
            'pairs_count': 5
        }
        strategy = MeanReversionStrategy(config)
        
        assert strategy.name == "MeanReversion"
        assert strategy.lookback_days == 20
        assert strategy.zscore_threshold == 2.0
        assert strategy.pairs_count == 5


class TestRiskParityStrategy:
    """Test cases for risk parity strategy."""

    def test_strategy_initialization(self):
        """Test risk parity strategy initialization."""
        config = {
            'lookback_days': 60,
            'target_volatility': 0.15,
            'min_weight': 0.01,
            'max_weight': 0.10
        }
        strategy = RiskParityStrategy(config)
        
        assert strategy.name == "RiskParity"
        assert strategy.lookback_days == 60
        assert strategy.target_volatility == 0.15
        assert strategy.min_weight == 0.01
        assert strategy.max_weight == 0.10


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN']
    dates = pd.date_range('2023-01-01', periods=252, freq='B')  # Business days
    
    data_list = []
    np.random.seed(42)  # For reproducible tests
    
    for symbol in symbols:
        # Generate realistic price series
        base_price = 100 + hash(symbol) % 50
        returns = np.random.normal(0.0005, 0.02, len(dates))
        prices = base_price * np.exp(np.cumsum(returns))
        
        for i, date in enumerate(dates):
            price = prices[i]
            high = price * (1 + abs(np.random.normal(0, 0.01)))
            low = price * (1 - abs(np.random.normal(0, 0.01)))
            open_price = low + (high - low) * np.random.random()
            volume = int(np.random.normal(1000000, 200000))
            
            data_list.append({
                'symbol': symbol,
                'datetime': date,
                'open': round(open_price, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'close': round(price, 2),
                'volume': max(volume, 100000),
            })
    
    return pd.DataFrame(data_list)


def test_momentum_strategy_with_sample_data(sample_market_data):
    """Test momentum strategy with sample data."""
    config = {
        'lookback_days': 21,
        'top_n_stocks': 2,
        'momentum_threshold': 0.01
    }
    
    strategy = MomentumStrategy(config)
    symbols = sample_market_data['symbol'].unique().tolist()
    strategy.initialize(symbols, sample_market_data)
    
    # Generate signals for a specific timestamp
    test_timestamp = sample_market_data['datetime'].max()
    signals = strategy.generate_signals(sample_market_data, test_timestamp)
    
    # Should have generated some signals
    assert isinstance(signals, list)
    
    # Each signal should have valid properties
    for signal in signals:
        assert signal.symbol in symbols
        assert signal.signal_type in ['BUY', 'SELL', 'HOLD']
        assert 0 <= signal.strength <= 1
        assert signal.timestamp == test_timestamp