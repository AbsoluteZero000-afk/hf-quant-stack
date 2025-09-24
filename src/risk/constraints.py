"""Risk constraint checks for position sizing and portfolio management."""

from typing import Dict, List, Optional, Tuple

from src.config import config
from src.utils.logging import get_logger

logger = get_logger(__name__)


class RiskConstraints:
    """Risk constraint checker for portfolio positions."""

    def __init__(self) -> None:
        """Initialize risk constraints with configuration."""
        self.max_position_size_pct = config.risk.max_position_size_pct
        self.max_daily_loss_pct = config.risk.max_daily_loss_pct
        self.max_drawdown_pct = config.risk.max_drawdown_pct
        self.logger = logger

    def check_position_size(
        self,
        symbol: str,
        target_value: float,
        portfolio_value: float,
        current_positions: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, str, float]:
        """Check if position size violates constraints.

        Args:
            symbol: Symbol to check
            target_value: Target position value
            portfolio_value: Total portfolio value
            current_positions: Current position values by symbol

        Returns:
            Tuple of (is_valid, reason, adjusted_value)
        """
        if portfolio_value <= 0:
            return False, "Portfolio value is zero or negative", 0.0

        # Calculate position percentage
        position_pct = abs(target_value) / portfolio_value

        # Check maximum position size
        if position_pct > self.max_position_size_pct:
            adjusted_value = (
                portfolio_value * self.max_position_size_pct
                if target_value > 0
                else -portfolio_value * self.max_position_size_pct
            )

            self.logger.warning(
                f"Position size for {symbol} ({position_pct:.2%}) exceeds maximum "
                f"({self.max_position_size_pct:.2%}). Adjusting to ${adjusted_value:.2f}"
            )

            return (
                False,
                f"Position size {position_pct:.2%} > {self.max_position_size_pct:.2%}",
                adjusted_value,
            )

        return True, "Position size within limits", target_value

    def check_sector_concentration(
        self,
        target_positions: Dict[str, float],
        sector_map: Dict[str, str],
        max_sector_pct: float = 0.25,
    ) -> Tuple[bool, str, Dict[str, float]]:
        """Check sector concentration limits.

        Args:
            target_positions: Target positions {symbol: value}
            sector_map: Symbol to sector mapping
            max_sector_pct: Maximum sector concentration

        Returns:
            Tuple of (is_valid, reason, adjusted_positions)
        """
        if not sector_map:
            # No sector information available
            return True, "No sector constraints", target_positions

        # Calculate sector exposures
        sector_exposures = {}
        total_exposure = sum(abs(value) for value in target_positions.values())

        if total_exposure == 0:
            return True, "No positions", target_positions

        for symbol, value in target_positions.items():
            sector = sector_map.get(symbol, "Unknown")
            if sector not in sector_exposures:
                sector_exposures[sector] = 0.0
            sector_exposures[sector] += abs(value)

        # Check for violations
        violations = []
        for sector, exposure in sector_exposures.items():
            sector_pct = exposure / total_exposure
            if sector_pct > max_sector_pct:
                violations.append((sector, sector_pct))

        if violations:
            reason = f"Sector concentration violations: {violations}"
            self.logger.warning(reason)
            # For now, just warn - could implement sector rebalancing
            return False, reason, target_positions

        return True, "Sector concentration within limits", target_positions

    def check_portfolio_risk(
        self,
        target_positions: Dict[str, float],
        current_portfolio_value: float,
        volatility_estimates: Optional[Dict[str, float]] = None,
        correlation_matrix: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> Tuple[bool, str, Dict[str, float]]:
        """Check overall portfolio risk metrics.

        Args:
            target_positions: Target positions {symbol: value}
            current_portfolio_value: Current portfolio value
            volatility_estimates: Symbol volatility estimates
            correlation_matrix: Pairwise correlations

        Returns:
            Tuple of (is_valid, reason, adjusted_positions)
        """
        # Basic leverage check
        total_gross_exposure = sum(abs(value) for value in target_positions.values())
        
        if current_portfolio_value > 0:
            leverage = total_gross_exposure / current_portfolio_value
            max_leverage = 1.5  # 150% gross exposure limit
            
            if leverage > max_leverage:
                # Scale down positions proportionally
                scale_factor = max_leverage / leverage
                adjusted_positions = {
                    symbol: value * scale_factor
                    for symbol, value in target_positions.items()
                }
                
                self.logger.warning(
                    f"Portfolio leverage ({leverage:.2f}) exceeds maximum ({max_leverage:.2f}). "
                    f"Scaling positions by {scale_factor:.3f}"
                )
                
                return (
                    False,
                    f"Leverage {leverage:.2f} > {max_leverage:.2f}",
                    adjusted_positions,
                )

        # TODO: Add portfolio volatility check if data available
        if volatility_estimates and correlation_matrix:
            # Could implement portfolio volatility calculation here
            pass

        return True, "Portfolio risk within limits", target_positions

    def apply_all_constraints(
        self,
        target_positions: Dict[str, float],
        portfolio_value: float,
        sector_map: Optional[Dict[str, str]] = None,
        volatility_estimates: Optional[Dict[str, float]] = None,
    ) -> Tuple[bool, List[str], Dict[str, float]]:
        """Apply all risk constraints to target positions.

        Args:
            target_positions: Target positions {symbol: value}
            portfolio_value: Current portfolio value
            sector_map: Symbol to sector mapping
            volatility_estimates: Symbol volatility estimates

        Returns:
            Tuple of (all_valid, constraint_messages, final_positions)
        """
        all_valid = True
        messages = []
        final_positions = target_positions.copy()

        # Check individual position sizes
        for symbol, value in list(final_positions.items()):
            is_valid, reason, adjusted_value = self.check_position_size(
                symbol, value, portfolio_value
            )
            
            if not is_valid:
                all_valid = False
                messages.append(f"{symbol}: {reason}")
                final_positions[symbol] = adjusted_value

        # Check sector concentration
        if sector_map:
            is_valid, reason, adjusted_positions = self.check_sector_concentration(
                final_positions, sector_map
            )
            
            if not is_valid:
                all_valid = False
                messages.append(f"Sector: {reason}")
                final_positions = adjusted_positions

        # Check overall portfolio risk
        is_valid, reason, adjusted_positions = self.check_portfolio_risk(
            final_positions, portfolio_value, volatility_estimates
        )
        
        if not is_valid:
            all_valid = False
            messages.append(f"Portfolio: {reason}")
            final_positions = adjusted_positions

        # Remove positions that are too small
        min_position_value = portfolio_value * 0.001  # 0.1% minimum
        final_positions = {
            symbol: value
            for symbol, value in final_positions.items()
            if abs(value) >= min_position_value
        }

        if all_valid:
            self.logger.info("All risk constraints satisfied")
        else:
            self.logger.warning(f"Risk constraint violations: {'; '.join(messages)}")

        return all_valid, messages, final_positions