"""Risk parity strategy implementation."""

from datetime import datetime, timedelta
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from src.strategies.base import BaseStrategy, Signal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskParityStrategy(BaseStrategy):
    """Risk parity strategy that allocates capital based on risk contribution."""

    def __init__(self, config: Dict) -> None:
        """Initialize risk parity strategy.

        Args:
            config: Strategy configuration
        """
        super().__init__("RiskParity", config)

        # Strategy parameters
        self.lookback_days = config.get("lookback_days", 60)
        self.target_volatility = config.get("target_volatility", 0.15)
        self.rebalance_frequency = config.get("rebalance_frequency", "weekly")
        self.min_weight = config.get("min_weight", 0.01)
        self.max_weight = config.get("max_weight", 0.10)

        # State tracking
        self.last_rebalance = None
        self.covariance_matrix = None
        self.risk_contributions = {}

    def calculate_covariance_matrix(
        self, data: pd.DataFrame, timestamp: datetime
    ) -> np.ndarray:
        """Calculate covariance matrix from historical returns.

        Args:
            data: Historical price data
            timestamp: Current timestamp

        Returns:
            Covariance matrix as numpy array
        """
        # Filter data to lookback period
        lookback_date = timestamp - timedelta(days=self.lookback_days + 10)
        recent_data = data[data["datetime"] >= lookback_date].copy()

        if recent_data.empty:
            self.logger.warning("No recent data for covariance calculation")
            return np.array([[]])

        # Create returns matrix
        price_pivot = recent_data.pivot_table(
            index="datetime", columns="symbol", values="close"
        )

        # Fill missing values and calculate returns
        price_pivot = price_pivot.fillna(method="ffill").dropna(axis=1)
        returns = price_pivot.pct_change().dropna()

        if returns.empty or len(returns.columns) < 2:
            self.logger.warning("Insufficient data for covariance calculation")
            return np.array([[]])

        # Calculate covariance matrix (annualized)
        cov_matrix = returns.cov() * 252  # Annualize

        # Store symbol order for later use
        self.symbol_order = returns.columns.tolist()

        self.logger.info(
            f"Calculated covariance matrix for {len(self.symbol_order)} symbols"
        )

        return cov_matrix.values

    def calculate_risk_parity_weights(self, cov_matrix: np.ndarray) -> np.ndarray:
        """Calculate risk parity weights using optimization.

        Args:
            cov_matrix: Covariance matrix

        Returns:
            Optimal weights array
        """
        n_assets = len(cov_matrix)

        if n_assets == 0:
            return np.array([])

        # Objective function: minimize sum of squared risk contributions
        def risk_parity_objective(weights):
            portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))

            if portfolio_vol == 0:
                return 1e6  # Large penalty

            # Risk contributions
            marginal_risk = np.dot(cov_matrix, weights) / portfolio_vol
            risk_contributions = weights * marginal_risk

            # Target risk contribution (equal for all assets)
            target_risk_contrib = portfolio_vol / n_assets

            # Minimize sum of squared deviations from target
            return np.sum((risk_contributions - target_risk_contrib) ** 2)

        # Constraints
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},  # Weights sum to 1
        ]

        # Bounds
        bounds = [(self.min_weight, self.max_weight) for _ in range(n_assets)]

        # Initial guess (equal weights)
        x0 = np.ones(n_assets) / n_assets

        try:
            # Optimize
            result = minimize(
                risk_parity_objective,
                x0,
                method="SLSQP",
                bounds=bounds,
                constraints=constraints,
                options={"maxiter": 1000, "ftol": 1e-9},
            )

            if result.success:
                weights = result.x

                # Calculate final risk contributions for monitoring
                portfolio_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights)))
                if portfolio_vol > 0:
                    marginal_risk = np.dot(cov_matrix, weights) / portfolio_vol
                    risk_contributions = weights * marginal_risk

                    self.risk_contributions = {
                        self.symbol_order[i]: risk_contributions[i]
                        for i in range(len(self.symbol_order))
                    }

                self.logger.info("Risk parity optimization successful")
                return weights
            else:
                self.logger.warning(
                    f"Risk parity optimization failed: {result.message}"
                )
                return np.ones(n_assets) / n_assets  # Fall back to equal weights

        except Exception as e:
            self.logger.error(f"Error in risk parity optimization: {e}")
            return np.ones(n_assets) / n_assets  # Fall back to equal weights

    def should_rebalance(self, timestamp: datetime) -> bool:
        """Check if portfolio should be rebalanced.

        Args:
            timestamp: Current timestamp

        Returns:
            True if should rebalance
        """
        if self.last_rebalance is None:
            return True

        if self.rebalance_frequency == "daily":
            return timestamp.date() > self.last_rebalance.date()
        elif self.rebalance_frequency == "weekly":
            return (timestamp - self.last_rebalance).days >= 7
        elif self.rebalance_frequency == "monthly":
            return (timestamp - self.last_rebalance).days >= 30

        return False

    def generate_signals(self, data: pd.DataFrame, timestamp: datetime) -> List[Signal]:
        """Generate risk parity rebalancing signals.

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

        # Calculate covariance matrix
        cov_matrix = self.calculate_covariance_matrix(data, timestamp)

        if cov_matrix.size == 0:
            self.logger.warning("No covariance matrix available")
            return signals

        # Calculate risk parity weights
        optimal_weights = self.calculate_risk_parity_weights(cov_matrix)

        if len(optimal_weights) == 0:
            return signals

        # Generate signals for each asset
        for i, symbol in enumerate(self.symbol_order):
            weight = optimal_weights[i]

            # All risk parity signals are "BUY" with different strengths
            # The strength represents the target weight
            signals.append(
                Signal(
                    symbol=symbol,
                    signal_type="BUY",
                    strength=weight,  # Use weight as signal strength
                    timestamp=timestamp,
                    metadata={
                        "target_weight": weight,
                        "risk_contribution": self.risk_contributions.get(symbol, 0),
                        "strategy": "risk_parity",
                    },
                )
            )

        self.last_rebalance = timestamp
        self.logger.info(f"Generated {len(signals)} risk parity signals")

        return signals

    def calculate_position_sizes(
        self,
        signals: List[Signal],
        portfolio_value: float,
        current_positions: Dict[str, float],
    ) -> Dict[str, float]:
        """Calculate position sizes based on target weights.

        Args:
            signals: Generated trading signals
            portfolio_value: Current portfolio value
            current_positions: Current positions

        Returns:
            Target positions dictionary
        """
        target_positions = {}

        # Get latest prices
        latest_prices = self._get_latest_prices(signals)

        # Calculate target positions based on weights
        for signal in signals:
            if signal.symbol in latest_prices and latest_prices[signal.symbol] > 0:
                target_weight = signal.metadata.get("target_weight", signal.strength)
                target_value = portfolio_value * target_weight
                target_shares = target_value / latest_prices[signal.symbol]
                target_positions[signal.symbol] = target_shares

        # Apply volatility scaling
        total_target_vol = self._calculate_portfolio_volatility(
            target_positions, latest_prices
        )
        if total_target_vol > 0:
            vol_scalar = self.target_volatility / total_target_vol
            # Don't scale up beyond 100% (vol_scalar > 1), only scale down
            vol_scalar = min(vol_scalar, 1.0)

            for symbol in target_positions:
                target_positions[symbol] *= vol_scalar

        self.logger.info(
            f"Calculated position sizes for {len(target_positions)} symbols "
            f"with volatility scaling of {vol_scalar:.3f}"
        )

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
        latest_date = self.historical_data["datetime"].max()
        latest_data = self.historical_data[
            self.historical_data["datetime"] == latest_date
        ]

        for signal in signals:
            symbol_data = latest_data[latest_data["symbol"] == signal.symbol]
            if not symbol_data.empty:
                prices[signal.symbol] = symbol_data.iloc[0]["close"]

        return prices

    def _calculate_portfolio_volatility(
        self, positions: Dict[str, float], prices: Dict[str, float]
    ) -> float:
        """Calculate expected portfolio volatility.

        Args:
            positions: Target positions
            prices: Current prices

        Returns:
            Expected portfolio volatility
        """
        if self.covariance_matrix is None or len(positions) == 0:
            return 0.0

        try:
            # Calculate weights
            total_value = sum(
                positions[s] * prices[s] for s in positions if s in prices
            )

            if total_value == 0:
                return 0.0

            weights = np.array(
                [
                    positions[symbol] * prices[symbol] / total_value
                    if symbol in positions and symbol in prices
                    else 0.0
                    for symbol in self.symbol_order
                ]
            )

            # Calculate portfolio volatility
            portfolio_var = np.dot(weights, np.dot(self.covariance_matrix, weights))
            return np.sqrt(max(portfolio_var, 0))

        except Exception as e:
            self.logger.debug(f"Error calculating portfolio volatility: {e}")
            return 0.0
