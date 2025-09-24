"""Paper trading execution handler using Alpaca API."""

from typing import Dict, List, Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from src.config import config
from src.db.models import Order, OrderType, OrderSide as DbOrderSide, OrderStatus
from src.execution.base import ExecutionHandler
from src.utils.logging import get_logger

logger = get_logger(__name__)


class PaperAlpacaExecutionHandler(ExecutionHandler):
    """Paper trading execution handler using Alpaca API."""

    def __init__(self) -> None:
        """Initialize Alpaca execution handler."""
        self.client = TradingClient(
            api_key=config.alpaca.api_key,
            secret_key=config.alpaca.secret_key,
            paper=True,  # Always use paper trading for safety
        )
        self.logger = logger
        
        # Test connection
        try:
            account = self.client.get_account()
            self.logger.info(f"Connected to Alpaca paper trading account: {account.account_number}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Alpaca: {e}")
            raise

    def submit_order(self, order: Order) -> bool:
        """Submit order to Alpaca.

        Args:
            order: Order to submit

        Returns:
            True if submitted successfully
        """
        try:
            # Map order side
            if order.side == DbOrderSide.BUY:
                alpaca_side = OrderSide.BUY
            else:
                alpaca_side = OrderSide.SELL
            
            # Create order request based on type
            if order.order_type == OrderType.MARKET:
                order_request = MarketOrderRequest(
                    symbol=order.asset.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
            elif order.order_type == OrderType.LIMIT:
                if not order.limit_price:
                    self.logger.error("Limit price required for limit orders")
                    return False
                
                order_request = LimitOrderRequest(
                    symbol=order.asset.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order.limit_price,
                )
            else:
                self.logger.error(f"Unsupported order type: {order.order_type}")
                return False
            
            # Submit order
            alpaca_order = self.client.submit_order(order_request)
            
            # Update order with broker ID
            order.broker_order_id = alpaca_order.id
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = alpaca_order.submitted_at
            
            self.logger.info(
                f"Submitted order: {order.side.value} {order.quantity} {order.asset.symbol} "
                f"(Broker ID: {alpaca_order.id})"
            )
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error submitting order: {e}")
            order.status = OrderStatus.REJECTED
            order.notes = str(e)
            return False

    def cancel_order(self, order_id: str) -> bool:
        """Cancel order in Alpaca.

        Args:
            order_id: Alpaca order ID

        Returns:
            True if cancelled successfully
        """
        try:
            self.client.cancel_order_by_id(order_id)
            self.logger.info(f"Cancelled order: {order_id}")
            return True
        except Exception as e:
            self.logger.error(f"Error cancelling order {order_id}: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status from Alpaca.

        Args:
            order_id: Alpaca order ID

        Returns:
            Order status information
        """
        try:
            alpaca_order = self.client.get_order_by_id(order_id)
            
            return {
                'id': alpaca_order.id,
                'status': alpaca_order.status.value,
                'symbol': alpaca_order.symbol,
                'quantity': float(alpaca_order.qty),
                'filled_quantity': float(alpaca_order.filled_qty or 0),
                'side': alpaca_order.side.value,
                'order_type': alpaca_order.order_type.value,
                'limit_price': float(alpaca_order.limit_price) if alpaca_order.limit_price else None,
                'submitted_at': alpaca_order.submitted_at,
                'filled_at': alpaca_order.filled_at,
                'cancelled_at': alpaca_order.cancelled_at,
            }
            
        except Exception as e:
            self.logger.error(f"Error getting order status for {order_id}: {e}")
            return None

    def get_positions(self) -> Dict[str, float]:
        """Get current positions from Alpaca.

        Returns:
            Dictionary of positions
        """
        try:
            positions = self.client.get_all_positions()
            
            position_dict = {}
            for position in positions:
                position_dict[position.symbol] = float(position.qty)
            
            return position_dict
            
        except Exception as e:
            self.logger.error(f"Error getting positions: {e}")
            return {}

    def get_account_info(self) -> Dict:
        """Get account information from Alpaca.

        Returns:
            Account information
        """
        try:
            account = self.client.get_account()
            
            return {
                'account_number': account.account_number,
                'status': account.status.value,
                'currency': account.currency,
                'cash': float(account.cash),
                'portfolio_value': float(account.portfolio_value),
                'buying_power': float(account.buying_power),
                'equity': float(account.equity),
                'last_equity': float(account.last_equity),
                'multiplier': float(account.multiplier),
                'day_trade_count': int(account.day_trade_count),
                'day_trading_buying_power': float(account.day_trading_buying_power),
                'regt_buying_power': float(account.regt_buying_power),
                'initial_margin': float(account.initial_margin),
                'maintenance_margin': float(account.maintenance_margin),
            }
            
        except Exception as e:
            self.logger.error(f"Error getting account info: {e}")
            return {}

    def is_connected(self) -> bool:
        """Check if connected to Alpaca.

        Returns:
            True if connected
        """
        try:
            account = self.client.get_account()
            return account is not None
        except Exception:
            return False

    def sync_orders(self, db_orders: List[Order]) -> None:
        """Sync order status with Alpaca.

        Args:
            db_orders: List of database orders to sync
        """
        for order in db_orders:
            if order.broker_order_id and order.status in [OrderStatus.SUBMITTED, OrderStatus.PARTIALLY_FILLED]:
                alpaca_status = self.get_order_status(order.broker_order_id)
                
                if alpaca_status:
                    # Update order status
                    status_mapping = {
                        'new': OrderStatus.SUBMITTED,
                        'partially_filled': OrderStatus.PARTIALLY_FILLED,
                        'filled': OrderStatus.FILLED,
                        'done_for_day': OrderStatus.CANCELLED,
                        'canceled': OrderStatus.CANCELLED,
                        'expired': OrderStatus.CANCELLED,
                        'replaced': OrderStatus.CANCELLED,
                        'pending_cancel': OrderStatus.PENDING,
                        'pending_replace': OrderStatus.PENDING,
                        'accepted': OrderStatus.SUBMITTED,
                        'pending_new': OrderStatus.PENDING,
                        'accepted_for_bidding': OrderStatus.SUBMITTED,
                        'stopped': OrderStatus.CANCELLED,
                        'rejected': OrderStatus.REJECTED,
                        'suspended': OrderStatus.CANCELLED,
                        'calculated': OrderStatus.PENDING,
                    }
                    
                    new_status = status_mapping.get(
                        alpaca_status['status'], OrderStatus.PENDING
                    )
                    
                    if order.status != new_status:
                        self.logger.info(
                            f"Order {order.broker_order_id} status: "
                            f"{order.status.value} -> {new_status.value}"
                        )
                        order.status = new_status
                        
                        # Update fill information
                        if new_status == OrderStatus.FILLED:
                            order.filled_quantity = alpaca_status['filled_quantity']
                            order.filled_at = alpaca_status['filled_at']
                        elif new_status == OrderStatus.PARTIALLY_FILLED:
                            order.filled_quantity = alpaca_status['filled_quantity']
                        elif new_status == OrderStatus.CANCELLED:
                            order.cancelled_at = alpaca_status['cancelled_at']