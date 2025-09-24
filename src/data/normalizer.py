"""Data normalization and preprocessing utilities."""

from typing import Optional

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)


class DataNormalizer:
    """Data normalizer for cleaning and preprocessing market data."""

    def __init__(self) -> None:
        """Initialize data normalizer."""
        self.logger = logger

    def clean_ohlcv_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean OHLCV data by removing invalid entries and outliers.

        Args:
            df: DataFrame with OHLCV data

        Returns:
            Cleaned DataFrame
        """
        self.logger.info(f"Cleaning OHLCV data with {len(df)} rows")

        original_count = len(df)

        # Remove rows with missing critical data
        df = df.dropna(subset=["open", "high", "low", "close", "volume"])

        # Remove rows with invalid OHLC relationships
        invalid_mask = (
            (df["high"] < df["low"])
            | (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
            | (df["volume"] <= 0)
            | (df["close"] <= 0)
        )
        df = df[~invalid_mask]

        # Remove extreme outliers (price changes > 50% in one day)
        df = df.sort_values(["symbol", "datetime"])
        df["prev_close"] = df.groupby("symbol")["close"].shift(1)
        df["daily_return"] = (df["close"] - df["prev_close"]) / df["prev_close"]

        # Remove returns > 50% (likely data errors)
        df = df[(df["daily_return"].abs() < 0.5) | df["daily_return"].isna()]

        # Clean up temporary columns
        df = df.drop(["prev_close", "daily_return"], axis=1)

        cleaned_count = len(df)
        self.logger.info(
            f"Cleaned data: {original_count} -> {cleaned_count} rows "
            f"({original_count - cleaned_count} removed)"
        )

        return df.reset_index(drop=True)

    def adjust_for_splits_and_dividends(
        self, df: pd.DataFrame, adjustment_factor_col: str = "adjustment_factor"
    ) -> pd.DataFrame:
        """Adjust prices for stock splits and dividends.

        Args:
            df: DataFrame with price data
            adjustment_factor_col: Column name for adjustment factor

        Returns:
            Adjusted DataFrame
        """
        if adjustment_factor_col not in df.columns:
            self.logger.warning(
                f"No {adjustment_factor_col} column found, skipping adjustment"
            )
            return df

        price_cols = ["open", "high", "low", "close"]

        for col in price_cols:
            if col in df.columns:
                df[col] = df[col] * df[adjustment_factor_col]

        # Volume should be adjusted inversely
        if "volume" in df.columns:
            df["volume"] = df["volume"] / df[adjustment_factor_col]

        self.logger.info("Applied split and dividend adjustments")
        return df

    def fill_missing_data(
        self, df: pd.DataFrame, method: str = "forward_fill"
    ) -> pd.DataFrame:
        """Fill missing data using specified method.

        Args:
            df: DataFrame with potential missing data
            method: Method to use ('forward_fill', 'backward_fill', 'interpolate')

        Returns:
            DataFrame with filled data
        """
        original_na_count = df.isna().sum().sum()

        if method == "forward_fill":
            df = df.groupby("symbol").fillna(method="ffill")
        elif method == "backward_fill":
            df = df.groupby("symbol").fillna(method="bfill")
        elif method == "interpolate":
            numeric_cols = df.select_dtypes(include=[np.number]).columns
            df[numeric_cols] = df.groupby("symbol")[numeric_cols].interpolate()

        final_na_count = df.isna().sum().sum()

        self.logger.info(
            f"Filled missing data using {method}: "
            f"{original_na_count} -> {final_na_count} NA values"
        )

        return df

    def resample_data(
        self, df: pd.DataFrame, freq: str = "D", agg_methods: Optional[dict] = None
    ) -> pd.DataFrame:
        """Resample data to different frequency.

        Args:
            df: DataFrame with datetime index
            freq: Frequency to resample to ('D', 'W', 'M')
            agg_methods: Dictionary of column -> aggregation method

        Returns:
            Resampled DataFrame
        """
        if agg_methods is None:
            agg_methods = {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
            }

        # Ensure datetime column is datetime type
        if "datetime" in df.columns:
            df["datetime"] = pd.to_datetime(df["datetime"])
            df = df.set_index("datetime")

        # Resample by symbol
        resampled_dfs = []
        for symbol in df["symbol"].unique():
            symbol_df = df[df["symbol"] == symbol]
            resampled_df = symbol_df.resample(freq).agg(agg_methods)
            resampled_df["symbol"] = symbol
            resampled_dfs.append(resampled_df)

        result = pd.concat(resampled_dfs)
        result = result.reset_index()

        self.logger.info(f"Resampled data to {freq} frequency: {len(result)} rows")
        return result
