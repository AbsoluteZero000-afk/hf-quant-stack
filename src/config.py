"""Configuration management for the trading system."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()


class DatabaseConfig(BaseModel):
    """Database configuration."""

    url: str = Field(..., description="Database URL")
    echo: bool = Field(default=False, description="Echo SQL queries")
    pool_size: int = Field(default=5, description="Connection pool size")
    max_overflow: int = Field(default=10, description="Max connection overflow")


class AlpacaConfig(BaseModel):
    """Alpaca broker configuration."""

    api_key: str = Field(..., description="Alpaca API key")
    secret_key: str = Field(..., description="Alpaca secret key")
    base_url: str = Field(
        default="https://paper-api.alpaca.markets", description="Alpaca base URL"
    )
    data_url: str = Field(
        default="https://data.alpaca.markets", description="Alpaca data URL"
    )


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_daily_loss_pct: float = Field(default=0.02, description="Max daily loss %")
    max_drawdown_pct: float = Field(default=0.10, description="Max drawdown %")
    max_position_size_pct: float = Field(
        default=0.05, description="Max position size %"
    )
    kelly_fraction: float = Field(default=0.25, description="Kelly criterion fraction")
    volatility_lookback_days: int = Field(
        default=21, description="Volatility lookback period"
    )


class TradingConfig(BaseModel):
    """Trading configuration."""

    timezone: str = Field(default="America/New_York", description="Trading timezone")
    initial_capital: float = Field(default=100000, description="Initial capital")
    commission_per_share: float = Field(default=0.0, description="Commission per share")
    slippage_bps: float = Field(default=5.0, description="Slippage in basis points")


class Config:
    """Main configuration class."""

    def __init__(self, config_path: Optional[str] = None) -> None:
        """Initialize configuration.

        Args:
            config_path: Path to configuration file
        """
        self.config_path = config_path or "config.yml"
        self._config_data = self._load_config()

        # Initialize sub-configurations
        self.database = self._get_database_config()
        self.alpaca = self._get_alpaca_config()
        self.risk = self._get_risk_config()
        self.trading = self._get_trading_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file.

        Returns:
            Configuration dictionary
        """
        config_file = Path(self.config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, "r") as f:
            return yaml.safe_load(f)

    def _get_database_config(self) -> DatabaseConfig:
        """Get database configuration.

        Returns:
            Database configuration
        """
        db_url = os.getenv("DATABASE_URL", "sqlite:///trading.db")
        return DatabaseConfig(
            url=db_url,
            echo=os.getenv("ENVIRONMENT", "production") == "development",
        )

    def _get_alpaca_config(self) -> AlpacaConfig:
        """Get Alpaca configuration.

        Returns:
            Alpaca configuration
        """
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise ValueError(
                "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in environment"
            )

        return AlpacaConfig(
            api_key=api_key,
            secret_key=secret_key,
            base_url=os.getenv(
                "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
            ),
        )

    def _get_risk_config(self) -> RiskConfig:
        """Get risk management configuration.

        Returns:
            Risk configuration
        """
        risk_config = self._config_data.get("risk", {})
        return RiskConfig(**risk_config)

    def _get_trading_config(self) -> TradingConfig:
        """Get trading configuration.

        Returns:
            Trading configuration
        """
        trading_config = self._config_data.get("trading", {})
        portfolio_config = self._config_data.get("portfolio", {})
        costs_config = self._config_data.get("costs", {})

        return TradingConfig(
            timezone=trading_config.get("timezone", "America/New_York"),
            initial_capital=portfolio_config.get("initial_capital", 100000),
            commission_per_share=costs_config.get("commission_per_share", 0.0),
            slippage_bps=costs_config.get("slippage_bps", 5.0),
        )

    def get_strategy_config(self, strategy_name: str) -> Dict[str, Any]:
        """Get strategy-specific configuration.

        Args:
            strategy_name: Name of the strategy

        Returns:
            Strategy configuration dictionary
        """
        strategies_config = self._config_data.get("strategies", {})
        return strategies_config.get(strategy_name, {})

    def get_backtest_config(self) -> Dict[str, Any]:
        """Get backtesting configuration.

        Returns:
            Backtest configuration dictionary
        """
        return self._config_data.get("backtest", {})


# Global configuration instance
config = Config()