"""Broker interface for order management."""

from typing import Dict, List, Optional, Type

from src.db.models import Asset, Order, OrderSide, OrderStatus, OrderType, Portfolio
from src.db.session import get_db_session
from src.execution.base import ExecutionHandler
from src.execution.paper_alpaca import PaperAlpacaExecutionHandler
from src.strategies.base import Signal
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BrokerInterface:
    """Interface for managing orders and positions across brokers."""

    def __init__(self, execution_handler: ExecutionHandler) -> None:
        """Initialize broker interface.

        Args:
            execution_handler: Execution handler to use
        """
        self.execution_handler = execution_handler
        self.logger = logger

    @classmethod
    def create_alpaca_interface(cls) -> "BrokerInterface":
        """Create broker interface with Alpaca execution handler.

        Returns:
            BrokerInterface instance
        """
        return cls(PaperAlpacaExecutionHandler())

    def submit_signals_as_orders(
        self,
        signals: List[Signal],
        portfolio: Portfolio,
        target_positions: Dict[str, float],
    ) -> List[Order]:
        """Convert signals to orders and submit them.

        Args:
            signals: Trading signals
            portfolio: Target portfolio
            target_positions: Target position sizes

        Returns:
            List of submitted orders
        """
        submitted_orders = []

        with get_db_session() as session:
            # Get current positions
            current_positions = self.execution_handler.get_positions()

            # Get assets for symbols
            symbols = set(target_positions.keys()) | set(current_positions.keys())
            assets = {}

            for symbol in symbols:
                asset = session.query(Asset).filter(Asset.symbol == symbol).first()
                if not asset:
                    # Create asset if it doesn't exist
                    asset = Asset(
                        symbol=symbol,
                        name=symbol,
                        asset_class="equity",
                        exchange="NASDAQ",
                        tradable=True,
                    )
                    session.add(asset)
                    session.flush()

                assets[symbol] = asset

            # Create orders for position changes
            for symbol in symbols:
                current_qty = current_positions.get(symbol, 0.0)
                target_qty = target_positions.get(symbol, 0.0)

                qty_diff = target_qty - current_qty

                # Only create order if change is significant
                if abs(qty_diff) < 0.001:
                    continue

                # Determine order side
                side = OrderSide.BUY if qty_diff > 0 else OrderSide.SELL

                # Create order
                order = Order(
                    portfolio_id=portfolio.id,
                    asset_id=assets[symbol].id,
                    order_type=OrderType.MARKET,
                    side=side,
                    quantity=abs(qty_diff),
                    status=OrderStatus.PENDING,
                )

                session.add(order)
                session.flush()  # Get order ID

                # Submit to broker
                if self.execution_handler.submit_order(order):
                    submitted_orders.append(order)
                    self.logger.info(f"Submitted order: {order}")
                else:
                    self.logger.error(f"Failed to submit order: {order}")

            session.commit()

        return submitted_orders

    def sync_orders(self, portfolio_id: int) -> None:
        """Sync order status with broker.

        Args:
            portfolio_id: Portfolio ID to sync orders for
        """
        with get_db_session() as session:
            # Get pending/submitted orders
            orders = (
                session.query(Order)
                .filter(
                    Order.portfolio_id == portfolio_id,
                    Order.status.in_(
                        [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]
                    ),
                )
                .all()
            )

            if hasattr(self.execution_handler, "sync_orders"):
                self.execution_handler.sync_orders(orders)

            session.commit()

    def cancel_all_orders(self, portfolio_id: int) -> int:
        """Cancel all pending orders for a portfolio.

        Args:
            portfolio_id: Portfolio ID

        Returns:
            Number of orders cancelled
        """
        cancelled_count = 0

        with get_db_session() as session:
            # Get cancellable orders
            orders = (
                session.query(Order)
                .filter(
                    Order.portfolio_id == portfolio_id,
                    Order.status.in_([OrderStatus.SUBMITTED, OrderStatus.PENDING]),
                )
                .all()
            )

            for order in orders:
                if order.broker_order_id:
                    if self.execution_handler.cancel_order(order.broker_order_id):
                        order.status = OrderStatus.CANCELLED
                        cancelled_count += 1
                        self.logger.info(f"Cancelled order: {order}")
                    else:
                        self.logger.error(f"Failed to cancel order: {order}")
                else:
                    # Order not yet submitted to broker
                    order.status = OrderStatus.CANCELLED
                    cancelled_count += 1

            session.commit()

        return cancelled_count

    def get_account_summary(self) -> Dict:
        """Get account summary from broker.

        Returns:
            Account summary dictionary
        """
        account_info = self.execution_handler.get_account_info()
        positions = self.execution_handler.get_positions()

        return {
            "account_info": account_info,
            "positions": positions,
            "is_connected": self.execution_handler.is_connected(),
        }

    def create_manual_order(
        self,
        portfolio_id: int,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        limit_price: Optional[float] = None,
    ) -> Optional[Order]:
        """Create and submit a manual order.

        Args:
            portfolio_id: Portfolio ID
            symbol: Symbol to trade
            side: Order side ('BUY' or 'SELL')
            quantity: Order quantity
            order_type: Order type ('MARKET' or 'LIMIT')
            limit_price: Limit price for limit orders

        Returns:
            Created order or None if failed
        """
        with get_db_session() as session:
            # Get or create asset
            asset = session.query(Asset).filter(Asset.symbol == symbol).first()
            if not asset:
                asset = Asset(
                    symbol=symbol,
                    name=symbol,
                    asset_class="equity",
                    tradable=True,
                )
                session.add(asset)
                session.flush()

            # Create order
            order = Order(
                portfolio_id=portfolio_id,
                asset_id=asset.id,
                order_type=OrderType(order_type.lower()),
                side=OrderSide(side.lower()),
                quantity=quantity,
                limit_price=limit_price,
                status=OrderStatus.PENDING,
                notes="Manual order",
            )

            session.add(order)
            session.flush()

            # Submit to broker
            if self.execution_handler.submit_order(order):
                session.commit()
                self.logger.info(f"Submitted manual order: {order}")
                return order
            else:
                session.rollback()
                self.logger.error(f"Failed to submit manual order: {order}")
                return None
