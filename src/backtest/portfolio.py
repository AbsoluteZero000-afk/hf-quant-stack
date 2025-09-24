"""Portfolio management for backtesting."""

from typing import Dict

from src.backtest.events import FillEvent
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BacktestPortfolio:
    """Portfolio manager for backtesting that tracks positions and PnL."""

    def __init__(self, initial_capital: float) -> None:
        """Initialize portfolio.

        Args:
            initial_capital: Starting capital
        """
        self.initial_capital = initial_capital
        self.cash = initial_capital

        # Position tracking: {symbol: quantity}
        self.positions = {}  # Current positions
        self.avg_prices = {}  # Average cost basis per symbol
        self.realized_pnl = 0.0  # Total realized PnL

        # Market data for position valuation
        self.current_prices = {}  # Latest market prices

        self.logger = logger

    def update_from_fill(self, fill_event: FillEvent) -> None:
        """Update portfolio from a fill event.

        Args:
            fill_event: Fill event to process
        """
        symbol = fill_event.symbol
        quantity = fill_event.signed_quantity  # Positive for buy, negative for sell
        fill_price = fill_event.fill_price
        commission = fill_event.commission

        # Update cash position
        cash_change = -quantity * fill_price - commission
        self.cash += cash_change

        # Update positions
        current_position = self.positions.get(symbol, 0.0)
        new_position = current_position + quantity

        if abs(new_position) < 1e-6:  # Close to zero
            # Position is closed
            if symbol in self.positions:
                del self.positions[symbol]
            if symbol in self.avg_prices:
                del self.avg_prices[symbol]
        else:
            # Update position
            self.positions[symbol] = new_position

            # Update average price (cost basis)
            if current_position == 0:  # Opening new position
                self.avg_prices[symbol] = fill_price
            elif (current_position > 0) == (
                quantity > 0
            ):  # Adding to existing position
                # Calculate new average price
                total_cost = (
                    current_position * self.avg_prices[symbol] + quantity * fill_price
                )
                self.avg_prices[symbol] = total_cost / new_position
            else:  # Reducing position or flipping
                if abs(quantity) < abs(current_position):  # Partial close
                    # Realize PnL on the closed portion
                    closed_quantity = abs(quantity)
                    avg_price = self.avg_prices[symbol]

                    if current_position > 0:  # Long position, selling
                        pnl = closed_quantity * (fill_price - avg_price)
                    else:  # Short position, buying to cover
                        pnl = closed_quantity * (avg_price - fill_price)

                    self.realized_pnl += pnl - commission

                    # Average price remains the same for remaining position
                else:  # Complete close or flip
                    # Realize PnL on the entire current position
                    if current_position != 0:
                        avg_price = self.avg_prices[symbol]

                        if current_position > 0:  # Closing long
                            pnl = abs(current_position) * (fill_price - avg_price)
                        else:  # Closing short
                            pnl = abs(current_position) * (avg_price - fill_price)

                        self.realized_pnl += pnl

                    # If flipping position, set new average price
                    if abs(quantity) > abs(current_position):
                        self.avg_prices[symbol] = fill_price

        self.logger.debug(
            f"Portfolio updated: {symbol} position {current_position:.2f} -> {new_position:.2f}, "
            f"cash ${self.cash:.2f}, realized PnL ${self.realized_pnl:.2f}"
        )

    def update_market_values(self, bars: Dict[str, Dict[str, float]]) -> None:
        """Update market prices for position valuation.

        Args:
            bars: Current bar data {symbol: {OHLCV}}
        """
        for symbol, bar in bars.items():
            self.current_prices[symbol] = bar["close"]

    def get_positions(self) -> Dict[str, float]:
        """Get current positions.

        Returns:
            Dictionary of positions {symbol: quantity}
        """
        return self.positions.copy()

    def get_positions_value(self) -> float:
        """Get total value of current positions.

        Returns:
            Total market value of positions
        """
        total_value = 0.0

        for symbol, quantity in self.positions.items():
            if symbol in self.current_prices:
                market_value = quantity * self.current_prices[symbol]
                total_value += market_value

        return total_value

    def get_unrealized_pnl(self) -> float:
        """Get unrealized PnL on current positions.

        Returns:
            Total unrealized PnL
        """
        unrealized_pnl = 0.0

        for symbol, quantity in self.positions.items():
            if symbol in self.current_prices and symbol in self.avg_prices:
                current_price = self.current_prices[symbol]
                avg_price = self.avg_prices[symbol]

                # Calculate PnL per share
                if quantity > 0:  # Long position
                    pnl_per_share = current_price - avg_price
                else:  # Short position
                    pnl_per_share = avg_price - current_price

                position_pnl = abs(quantity) * pnl_per_share
                unrealized_pnl += position_pnl

        return unrealized_pnl

    def get_realized_pnl(self) -> float:
        """Get total realized PnL.

        Returns:
            Total realized PnL
        """
        return self.realized_pnl

    def get_total_value(self) -> float:
        """Get total portfolio value.

        Returns:
            Total portfolio value (cash + positions)
        """
        return self.cash + self.get_positions_value()

    def get_portfolio_summary(self) -> Dict:
        """Get portfolio summary.

        Returns:
            Portfolio summary dictionary
        """
        positions_value = self.get_positions_value()
        unrealized_pnl = self.get_unrealized_pnl()
        total_value = self.get_total_value()

        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "positions_value": positions_value,
            "total_value": total_value,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": self.realized_pnl + unrealized_pnl,
            "total_return": (total_value - self.initial_capital) / self.initial_capital,
            "num_positions": len(self.positions),
            "positions": self.positions.copy(),
        }
