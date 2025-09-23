"""Hedge Fund Quantitative Trading Stack.

A comprehensive automated trading system with backtesting, portfolio management,
risk controls, and live execution capabilities.
"""

__version__ = "0.1.0"
__author__ = "HF Quant Stack"

# Core imports for easy access
from src.config import Config
from src.utils.logging import setup_logging

__all__ = [
    "Config",
    "setup_logging",
]