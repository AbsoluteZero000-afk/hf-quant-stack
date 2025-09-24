"""Data fetchers for retrieving market data from various sources."""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
from alpaca.data import StockHistoricalDataClient, TimeFrame
from alpaca.data.requests import StockBarsRequest

from src.config import config
from src.utils.logging import get_logger

logger = get_logger(__name__)


class DataFetcher(ABC):
    """Abstract base class for data fetchers."""

    @abstractmethod
    def get_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Get bar data for symbols.

        Args:
            symbols: List of symbols to fetch
            start_date: Start date
            end_date: End date
            timeframe: Timeframe (1Day, 1Hour, etc.)

        Returns:
            DataFrame with OHLCV data
        """
        pass

    @abstractmethod
    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get latest prices for symbols.

        Args:
            symbols: List of symbols

        Returns:
            Dictionary mapping symbol to price
        """
        pass


class AlpacaDataFetcher(DataFetcher):
    """Alpaca data fetcher implementation."""

    def __init__(self) -> None:
        """Initialize Alpaca data client."""
        self.client = StockHistoricalDataClient(
            api_key=config.alpaca.api_key,
            secret_key=config.alpaca.secret_key,
        )
        logger.info("Initialized Alpaca data fetcher")

    def get_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Get bar data from Alpaca.

        Args:
            symbols: List of symbols to fetch
            start_date: Start date
            end_date: End date
            timeframe: Timeframe string

        Returns:
            DataFrame with OHLCV data
        """
        logger.info(
            f"Fetching {timeframe} bars for {len(symbols)} symbols "
            f"from {start_date.date()} to {end_date.date()}"
        )

        # Map timeframe string to Alpaca TimeFrame
        timeframe_map = {
            "1Day": TimeFrame.Day,
            "1Hour": TimeFrame.Hour,
            "1Min": TimeFrame.Minute,
        }

        alpaca_timeframe = timeframe_map.get(timeframe, TimeFrame.Day)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=alpaca_timeframe,
                start=start_date,
                end=end_date,
                adjustment="all",  # Adjust for splits and dividends
            )

            bars = self.client.get_stock_bars(request)
            
            if bars.df.empty:
                logger.warning("No data received from Alpaca")
                return pd.DataFrame()

            df = bars.df.reset_index()
            
            # Rename columns to standard format
            df = df.rename(
                columns={
                    "symbol": "symbol",
                    "timestamp": "datetime",
                    "open": "open",
                    "high": "high",
                    "low": "low",
                    "close": "close",
                    "volume": "volume",
                }
            )

            # Convert timezone-aware datetime to naive datetime
            if "datetime" in df.columns:
                df["datetime"] = pd.to_datetime(df["datetime"]).dt.tz_convert(None)

            logger.info(f"Successfully fetched {len(df)} bars")
            return df

        except Exception as e:
            logger.error(f"Error fetching data from Alpaca: {e}")
            raise

    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get latest prices from Alpaca.

        Args:
            symbols: List of symbols

        Returns:
            Dictionary mapping symbol to price
        """
        logger.info(f"Fetching latest prices for {len(symbols)} symbols")

        try:
            # Get latest bar for each symbol
            end_date = datetime.now()
            start_date = end_date - timedelta(days=7)  # Get last week to ensure data

            df = self.get_bars(symbols, start_date, end_date, "1Day")
            
            if df.empty:
                logger.warning("No price data available")
                return {}

            # Get the latest close price for each symbol
            latest_prices = (
                df.groupby("symbol")
                .apply(lambda x: x.loc[x["datetime"].idxmax(), "close"])
                .to_dict()
            )

            logger.info(f"Retrieved latest prices for {len(latest_prices)} symbols")
            return latest_prices

        except Exception as e:
            logger.error(f"Error fetching latest prices: {e}")
            return {}


class SampleDataFetcher(DataFetcher):
    """Sample data fetcher for testing and development."""

    def get_bars(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        timeframe: str = "1Day",
    ) -> pd.DataFrame:
        """Generate sample bar data.

        Args:
            symbols: List of symbols to generate data for
            start_date: Start date
            end_date: End date
            timeframe: Timeframe string

        Returns:
            DataFrame with sample OHLCV data
        """
        logger.info(f"Generating sample data for {len(symbols)} symbols")

        import numpy as np

        # Generate date range
        if timeframe == "1Day":
            dates = pd.bdate_range(start=start_date, end=end_date)
        else:
            # For simplicity, just use daily data
            dates = pd.bdate_range(start=start_date, end=end_date)

        data_list = []
        
        for symbol in symbols:
            # Generate random walk price data
            np.random.seed(hash(symbol) % 2**32)  # Consistent seed per symbol
            n_days = len(dates)
            
            # Starting price based on symbol hash for consistency
            base_price = 50 + (hash(symbol) % 100)
            
            # Generate returns with some volatility
            returns = np.random.normal(0.0005, 0.02, n_days)  # ~0.05% daily return, 2% volatility
            prices = base_price * np.exp(np.cumsum(returns))
            
            for i, date in enumerate(dates):
                price = prices[i]
                # Generate OHLC from close price
                high = price * (1 + abs(np.random.normal(0, 0.01)))
                low = price * (1 - abs(np.random.normal(0, 0.01)))
                open_price = low + (high - low) * np.random.random()
                
                volume = int(np.random.normal(1000000, 200000))  # Average 1M volume
                
                data_list.append({
                    "symbol": symbol,
                    "datetime": date,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(price, 2),
                    "volume": max(volume, 100000),  # Minimum volume
                })

        df = pd.DataFrame(data_list)
        logger.info(f"Generated {len(df)} sample bars")
        return df

    def get_latest_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get sample latest prices.

        Args:
            symbols: List of symbols

        Returns:
            Dictionary mapping symbol to sample price
        """
        import numpy as np
        
        prices = {}
        for symbol in symbols:
            # Generate consistent price based on symbol
            np.random.seed(hash(symbol) % 2**32)
            prices[symbol] = round(50 + np.random.random() * 100, 2)
        
        return prices