"""Universe selection for trading strategies."""

from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from src.data.fetcher import DataFetcher
from src.utils.logging import get_logger

logger = get_logger(__name__)


class UniverseSelector:
    """Universe selector for choosing tradable assets."""

    def __init__(self, data_fetcher: DataFetcher) -> None:
        """Initialize universe selector.

        Args:
            data_fetcher: Data fetcher instance
        """
        self.data_fetcher = data_fetcher
        self.logger = logger

    def get_sp500_universe(self) -> List[str]:
        """Get S&P 500 universe (simplified list).

        Returns:
            List of S&P 500 symbols
        """
        # Simplified S&P 500 list - in production, this would be fetched from a data provider
        sp500_symbols = [
            "AAPL",
            "MSFT",
            "AMZN",
            "GOOGL",
            "GOOG",
            "TSLA",
            "BRK.B",
            "UNH",
            "JNJ",
            "META",
            "NVDA",
            "JPM",
            "V",
            "PG",
            "XOM",
            "HD",
            "CVX",
            "PFE",
            "MA",
            "BAC",
            "ABBV",
            "KO",
            "AVGO",
            "PEP",
            "COST",
            "TMO",
            "WMT",
            "DIS",
            "ABT",
            "ACN",
            "MRK",
            "VZ",
            "NFLX",
            "ADBE",
            "CRM",
            "NKE",
            "DHR",
            "TXN",
            "NEE",
            "RTX",
            "CMCSA",
            "ORCL",
            "QCOM",
            "WFC",
            "UPS",
            "PM",
            "T",
            "HON",
            "IBM",
            "SPGI",
            "LOW",
            "AMD",
            "GS",
            "CAT",
            "INTU",
            "CVS",
            "AXP",
            "BLK",
            "DE",
            "LMT",
            "MS",
            "ISRG",
            "AMGN",
            "BKNG",
            "GE",
            "AMD",
            "MU",
            "SYK",
            "ADP",
            "NOW",
            "TJX",
            "SCHW",
            "ZTS",
            "PLD",
            "ADI",
            "GILD",
            "CB",
            "MO",
            "DUK",
            "PYPL",
            "CI",
            "ICE",
            "SO",
            "EQIX",
            "AON",
            "SHW",
            "CL",
            "APD",
            "D",
            "ITW",
            "USB",
            "CSX",
            "MMC",
            "REGN",
            "EL",
            "NOC",
            "FCX",
            "PGR",
            "BSX",
            "BDX",
        ]

        self.logger.info(
            f"Retrieved S&P 500 universe with {len(sp500_symbols)} symbols"
        )
        return sp500_symbols

    def get_liquid_universe(
        self,
        min_price: float = 5.0,
        min_volume: int = 1000000,
        min_market_cap: float = 1e9,
        max_symbols: int = 100,
        lookback_days: int = 30,
    ) -> List[str]:
        """Get liquid universe based on volume and price criteria.

        Args:
            min_price: Minimum average price
            min_volume: Minimum average daily volume
            min_market_cap: Minimum market capitalization (not implemented)
            max_symbols: Maximum number of symbols to return
            lookback_days: Days to look back for averages

        Returns:
            List of liquid symbols
        """
        self.logger.info(
            f"Selecting liquid universe with criteria: "
            f"min_price={min_price}, min_volume={min_volume}, max_symbols={max_symbols}"
        )

        # Start with S&P 500 universe
        base_universe = self.get_sp500_universe()

        # Get recent data for filtering
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days + 10)  # Extra buffer

        try:
            df = self.data_fetcher.get_bars(
                symbols=base_universe, start_date=start_date, end_date=end_date
            )

            if df.empty:
                self.logger.warning("No data available for universe filtering")
                return base_universe[:max_symbols]

            # Calculate average price and volume per symbol
            symbol_stats = (
                df.groupby("symbol").agg({"close": "mean", "volume": "mean"}).round(2)
            )

            symbol_stats.columns = ["avg_price", "avg_volume"]

            # Apply filters
            filtered_symbols = symbol_stats[
                (symbol_stats["avg_price"] >= min_price)
                & (symbol_stats["avg_volume"] >= min_volume)
            ]

            # Sort by volume (liquidity) and take top N
            filtered_symbols = filtered_symbols.sort_values(
                "avg_volume", ascending=False
            )
            liquid_universe = filtered_symbols.head(max_symbols).index.tolist()

            self.logger.info(
                f"Filtered universe: {len(base_universe)} -> {len(liquid_universe)} symbols"
            )

            return liquid_universe

        except Exception as e:
            self.logger.error(f"Error filtering universe: {e}")
            # Fallback to top symbols from base universe
            return base_universe[:max_symbols]

    def get_sample_universe(self, size: int = 20) -> List[str]:
        """Get a sample universe for testing.

        Args:
            size: Number of symbols to return

        Returns:
            List of sample symbols
        """
        sample_symbols = [
            "AAPL",
            "MSFT",
            "AMZN",
            "GOOGL",
            "TSLA",
            "META",
            "NVDA",
            "JPM",
            "V",
            "UNH",
            "JNJ",
            "PG",
            "HD",
            "MA",
            "DIS",
            "NFLX",
            "KO",
            "PFE",
            "VZ",
            "WMT",
        ]

        result = sample_symbols[: min(size, len(sample_symbols))]
        self.logger.info(f"Retrieved sample universe with {len(result)} symbols")
        return result

    def filter_by_sector(self, symbols: List[str], sectors: List[str]) -> List[str]:
        """Filter symbols by sector (placeholder implementation).

        Args:
            symbols: List of symbols to filter
            sectors: List of sectors to include

        Returns:
            Filtered list of symbols
        """
        # This is a placeholder - in production, you'd have sector data
        self.logger.warning("Sector filtering not implemented - returning all symbols")
        return symbols

    def get_universe_by_strategy(self, strategy: str, **kwargs) -> List[str]:
        """Get universe tailored for specific strategy.

        Args:
            strategy: Strategy name
            **kwargs: Strategy-specific parameters

        Returns:
            List of symbols for the strategy
        """
        if strategy == "momentum":
            return self.get_liquid_universe(
                min_volume=2000000,  # Higher volume for momentum
                max_symbols=kwargs.get("universe_size", 50),
            )
        elif strategy == "mean_reversion":
            return self.get_liquid_universe(
                min_volume=1000000, max_symbols=kwargs.get("universe_size", 100)
            )
        elif strategy == "risk_parity":
            # For risk parity, we want diversified sectors
            return self.get_sp500_universe()[: kwargs.get("universe_size", 100)]
        elif strategy == "sample":
            return self.get_sample_universe(kwargs.get("universe_size", 20))
        else:
            return self.get_liquid_universe(
                max_symbols=kwargs.get("universe_size", 100)
            )
