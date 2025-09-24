"""Database models for the trading system."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class OrderStatus(Enum):
    """Order status enumeration."""

    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIALLY_FILLED = "partially_filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderType(Enum):
    """Order type enumeration."""

    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side enumeration."""

    BUY = "buy"
    SELL = "sell"


class Asset(Base):
    """Asset model."""

    __tablename__ = "assets"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(10), unique=True, nullable=False, index=True)
    name = Column(String(200))
    asset_class = Column(String(50))  # equity, forex, crypto, etc.
    exchange = Column(String(50))
    tradable = Column(Boolean, default=True)
    marginable = Column(Boolean, default=False)
    min_order_size = Column(Numeric(15, 5), default=1)
    min_price_increment = Column(Numeric(10, 5), default=0.01)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    positions = relationship("Position", back_populates="asset")
    orders = relationship("Order", back_populates="asset")
    trades = relationship("Trade", back_populates="asset")

    def __repr__(self) -> str:
        return f"<Asset(symbol='{self.symbol}', name='{self.name}')>"


class Portfolio(Base):
    """Portfolio model."""

    __tablename__ = "portfolios"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    strategy = Column(String(100))
    initial_capital = Column(Numeric(15, 2), nullable=False)
    current_capital = Column(Numeric(15, 2), nullable=False)
    cash_balance = Column(Numeric(15, 2), nullable=False)
    total_pnl = Column(Numeric(15, 2), default=0)
    daily_pnl = Column(Numeric(15, 2), default=0)
    max_drawdown = Column(Numeric(8, 4), default=0)  # As percentage
    sharpe_ratio = Column(Numeric(8, 4))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    positions = relationship("Position", back_populates="portfolio")
    orders = relationship("Order", back_populates="portfolio")
    trades = relationship("Trade", back_populates="portfolio")

    def __repr__(self) -> str:
        return f"<Portfolio(name='{self.name}', capital={self.current_capital})>"


class Position(Base):
    """Position model."""

    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("portfolio_id", "asset_id"),)

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    quantity = Column(Numeric(15, 5), nullable=False)
    avg_price = Column(Numeric(15, 5), nullable=False)
    market_value = Column(Numeric(15, 2))
    unrealized_pnl = Column(Numeric(15, 2), default=0)
    realized_pnl = Column(Numeric(15, 2), default=0)
    last_price = Column(Numeric(15, 5))
    cost_basis = Column(Numeric(15, 2))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="positions")
    asset = relationship("Asset", back_populates="positions")

    def __repr__(self) -> str:
        return f"<Position(symbol={self.asset.symbol if self.asset else 'N/A'}, qty={self.quantity})>"


class Order(Base):
    """Order model."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    broker_order_id = Column(String(100), unique=True)
    order_type = Column(SQLEnum(OrderType), nullable=False)
    side = Column(SQLEnum(OrderSide), nullable=False)
    quantity = Column(Numeric(15, 5), nullable=False)
    filled_quantity = Column(Numeric(15, 5), default=0)
    limit_price = Column(Numeric(15, 5))
    stop_price = Column(Numeric(15, 5))
    status = Column(SQLEnum(OrderStatus), default=OrderStatus.PENDING)
    submitted_at = Column(DateTime)
    filled_at = Column(DateTime)
    cancelled_at = Column(DateTime)
    commission = Column(Numeric(10, 4), default=0)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="orders")
    asset = relationship("Asset", back_populates="orders")
    trades = relationship("Trade", back_populates="order")

    def __repr__(self) -> str:
        return f"<Order({self.side.value} {self.quantity} {self.asset.symbol if self.asset else 'N/A'} @ {self.status.value})>"


class Trade(Base):
    """Trade model for executed transactions."""

    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    portfolio_id = Column(Integer, ForeignKey("portfolios.id"), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"))
    broker_trade_id = Column(String(100), unique=True)
    side = Column(SQLEnum(OrderSide), nullable=False)
    quantity = Column(Numeric(15, 5), nullable=False)
    price = Column(Numeric(15, 5), nullable=False)
    value = Column(Numeric(15, 2), nullable=False)  # quantity * price
    commission = Column(Numeric(10, 4), default=0)
    fees = Column(Numeric(10, 4), default=0)
    net_amount = Column(Numeric(15, 2))  # value +/- commission + fees
    executed_at = Column(DateTime, nullable=False)
    settlement_date = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    portfolio = relationship("Portfolio", back_populates="trades")
    asset = relationship("Asset", back_populates="trades")
    order = relationship("Order", back_populates="trades")

    def __repr__(self) -> str:
        return f"<Trade({self.side.value} {self.quantity} {self.asset.symbol if self.asset else 'N/A'} @ ${self.price})>"