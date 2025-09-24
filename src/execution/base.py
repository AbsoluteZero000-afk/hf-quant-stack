"""Base execution handler interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from src.db.models import Order


class ExecutionHandler(ABC):
    """Abstract base class for execution handlers."""

    @abstractmethod
    def submit_order(self, order: Order) -> bool:
        """Submit an order to the broker.

        Args:
            order: Order to submit

        Returns:
            True if order submitted successfully
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: Broker order ID to cancel

        Returns:
            True if order cancelled successfully
        """
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """Get order status from broker.

        Args:
            order_id: Broker order ID

        Returns:
            Order status dictionary or None if not found
        """
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, float]:
        """Get current positions from broker.

        Returns:
            Dictionary of positions {symbol: quantity}
        """
        pass

    @abstractmethod
    def get_account_info(self) -> Dict:
        """Get account information.

        Returns:
            Account information dictionary
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected to broker.

        Returns:
            True if connected
        """
        pass