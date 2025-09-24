"""Timing utilities for the trading system."""

import time
from datetime import datetime, timedelta
from typing import List

import pandas as pd
from pandas.tseries.offsets import BDay


class Timer:
    """Context manager for timing operations."""

    def __init__(self, name: str = "Operation") -> None:
        """Initialize timer.

        Args:
            name: Name of the operation being timed
        """
        self.name = name
        self.start_time: float = 0.0
        self.end_time: float = 0.0

    def __enter__(self) -> "Timer":
        """Start timing.

        Returns:
            Timer instance
        """
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, *args) -> None:
        """Stop timing and print result."""
        self.end_time = time.perf_counter()
        elapsed = self.end_time - self.start_time
        print(f"{self.name} took {elapsed:.4f} seconds")

    @property
    def elapsed(self) -> float:
        """Get elapsed time.

        Returns:
            Elapsed time in seconds
        """
        if self.end_time == 0:
            return time.perf_counter() - self.start_time
        return self.end_time - self.start_time


def trading_days_between(start_date: datetime, end_date: datetime) -> int:
    """Calculate number of trading days between two dates.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        Number of trading days
    """
    return len(pd.bdate_range(start_date, end_date))


def get_trading_days(start_date: datetime, end_date: datetime) -> List[datetime]:
    """Get list of trading days between two dates.

    Args:
        start_date: Start date
        end_date: End date

    Returns:
        List of trading days
    """
    return pd.bdate_range(start_date, end_date).to_pydatetime().tolist()


def is_trading_day(date: datetime) -> bool:
    """Check if a date is a trading day.

    Args:
        date: Date to check

    Returns:
        True if trading day, False otherwise
    """
    # Monday=0, Sunday=6
    return date.weekday() < 5


def next_trading_day(date: datetime) -> datetime:
    """Get next trading day after given date.

    Args:
        date: Reference date

    Returns:
        Next trading day
    """
    next_day = date + BDay(1)
    return next_day


def previous_trading_day(date: datetime) -> datetime:
    """Get previous trading day before given date.

    Args:
        date: Reference date

    Returns:
        Previous trading day
    """
    prev_day = date - BDay(1)
    return prev_day
