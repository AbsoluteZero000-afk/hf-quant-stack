"""Sample data generation for testing and development."""

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)


def generate_sample_data(
    symbols: List[str],
    start_date: datetime,
    end_date: datetime,
    output_dir: str = "data/sample",
) -> str:
    """Generate sample OHLCV data for testing.

    Args:
        symbols: List of symbols to generate data for
        start_date: Start date for data
        end_date: End date for data
        output_dir: Directory to save data

    Returns:
        Path to generated data file
    """
    logger.info(
        f"Generating sample data for {len(symbols)} symbols "
        f"from {start_date.date()} to {end_date.date()}"
    )

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate business days
    dates = pd.bdate_range(start=start_date, end=end_date)

    data_list = []

    for symbol in symbols:
        # Set seed based on symbol for consistency
        np.random.seed(hash(symbol) % 2**32)

        # Base price for this symbol
        base_price = 50 + (hash(symbol) % 100)

        # Generate price series with random walk
        n_days = len(dates)
        daily_returns = np.random.normal(0.0005, 0.02, n_days)  # Small positive drift

        # Add some trend and seasonality
        trend = np.linspace(0, 0.1, n_days)  # 10% trend over period
        seasonality = 0.05 * np.sin(
            2 * np.pi * np.arange(n_days) / 252
        )  # Annual seasonality

        combined_returns = daily_returns + trend / n_days + seasonality / n_days
        prices = base_price * np.exp(np.cumsum(combined_returns))

        for i, date in enumerate(dates):
            close_price = prices[i]

            # Generate intraday range
            daily_volatility = abs(np.random.normal(0, 0.015))  # 1.5% avg daily range
            range_pct = daily_volatility

            # Generate OHLC
            high = close_price * (1 + range_pct * np.random.random())
            low = close_price * (1 - range_pct * np.random.random())

            # Ensure high >= close >= low
            high = max(high, close_price)
            low = min(low, close_price)

            # Open price somewhere in the range
            open_price = low + (high - low) * np.random.random()

            # Generate volume with some correlation to volatility
            base_volume = 1000000 * (1 + hash(symbol) % 5)  # Different base volumes
            volume_multiplier = (
                1 + daily_volatility * 10
            )  # Higher volume on volatile days
            volume = int(base_volume * volume_multiplier * (0.5 + np.random.random()))

            data_list.append(
                {
                    "symbol": symbol,
                    "datetime": date,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close_price, 2),
                    "volume": volume,
                }
            )

    # Create DataFrame and save
    df = pd.DataFrame(data_list)

    # Save to CSV
    filename = (
        f"sample_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
    )
    filepath = output_path / filename

    df.to_csv(filepath, index=False)

    logger.info(f"Generated {len(df)} rows of sample data saved to {filepath}")

    return str(filepath)


def load_sample_data(filepath: str) -> pd.DataFrame:
    """Load sample data from CSV file.

    Args:
        filepath: Path to sample data file

    Returns:
        DataFrame with sample data
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Sample data file not found: {filepath}")

    df = pd.read_csv(filepath, parse_dates=["datetime"])
    logger.info(f"Loaded sample data: {len(df)} rows from {filepath}")

    return df


def create_default_sample_data() -> str:
    """Create default sample data for the repository.

    Returns:
        Path to generated sample data file
    """
    symbols = [
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

    end_date = datetime(2024, 1, 1)
    start_date = datetime(2023, 1, 1)

    return generate_sample_data(symbols, start_date, end_date)


if __name__ == "__main__":
    # Generate default sample data when run directly
    create_default_sample_data()
