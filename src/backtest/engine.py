"""Event-driven backtesting engine."""

import queue
from datetime import datetime
from typing import Dict, List, Optional, Type

import pandas as pd

from src.backtest.events import Event, BarEvent, OrderEvent, FillEvent, SignalEvent
from src.backtest.execution import SimulatedExecutionHandler
from src.backtest.portfolio import BacktestPortfolio
from src.strategies.base import BaseStrategy
from src.utils.logging import get_logger

logger = get_logger(__name__)


class BacktestEngine:
    """Event-driven backtesting engine."""

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float = 100000.0,
        commission_per_share: float = 0.0,
        slippage_bps: float = 5.0,
    ) -> None:
        """Initialize backtest engine.

        Args:
            strategy: Trading strategy to backtest
            initial_capital: Initial portfolio capital
            commission_per_share: Commission per share traded
            slippage_bps: Slippage in basis points
        """
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.commission_per_share = commission_per_share
        self.slippage_bps = slippage_bps
        
        # Event queue for event-driven simulation
        self.events = queue.Queue()
        
        # Components
        self.portfolio = BacktestPortfolio(initial_capital)
        self.execution_handler = SimulatedExecutionHandler(
            commission_per_share=commission_per_share,
            slippage_bps=slippage_bps
        )
        
        # State tracking
        self.current_time = None
        self.current_bars = {}
        self.is_running = False
        
        # Results storage
        self.performance_history = []
        self.trade_history = []
        self.signal_history = []
        
        self.logger = logger.bind(strategy=strategy.name)

    def _generate_bar_events(self, data: pd.DataFrame) -> None:
        """Generate bar events from historical data.

        Args:
            data: Historical OHLCV data
        """
        # Group data by timestamp
        grouped = data.groupby('datetime')
        
        for timestamp, group in grouped:
            bars = {}
            for _, row in group.iterrows():
                bars[row['symbol']] = {
                    'open': row['open'],
                    'high': row['high'],
                    'low': row['low'],
                    'close': row['close'],
                    'volume': row['volume'],
                }
            
            self.events.put(BarEvent(timestamp, bars))

    def _handle_bar_event(self, event: BarEvent) -> None:
        """Handle bar event.

        Args:
            event: Bar event to handle
        """
        self.current_time = event.timestamp
        self.current_bars = event.bars
        
        # Update portfolio with latest prices
        self.portfolio.update_market_values(event.bars)
        
        # Generate strategy signals
        try:
            # Get current portfolio state
            portfolio_value = self.portfolio.get_total_value()
            current_positions = self.portfolio.get_positions()
            
            # Run strategy
            signals, target_positions = self.strategy.run(
                timestamp=event.timestamp,
                portfolio_value=portfolio_value,
                current_positions=current_positions,
            )
            
            # Convert signals to signal events
            for signal in signals:
                signal_event = SignalEvent(
                    timestamp=event.timestamp,
                    symbol=signal.symbol,
                    signal_type=signal.signal_type,
                    strength=signal.strength,
                    metadata=signal.metadata,
                )
                self.events.put(signal_event)
                self.signal_history.append({
                    'timestamp': event.timestamp,
                    'symbol': signal.symbol,
                    'signal_type': signal.signal_type,
                    'strength': signal.strength,
                    'strategy': self.strategy.name,
                })
            
            # Generate orders to reach target positions
            orders = self._generate_orders_from_targets(target_positions, event.timestamp)
            for order in orders:
                self.events.put(order)
                
        except Exception as e:
            self.logger.error(f"Error in strategy execution: {e}")

    def _generate_orders_from_targets(
        self, target_positions: Dict[str, float], timestamp: datetime
    ) -> List[OrderEvent]:
        """Generate orders to reach target positions.

        Args:
            target_positions: Target positions by symbol
            timestamp: Current timestamp

        Returns:
            List of order events
        """
        orders = []
        current_positions = self.portfolio.get_positions()
        
        # Combine all symbols from current and target positions
        all_symbols = set(current_positions.keys()) | set(target_positions.keys())
        
        for symbol in all_symbols:
            current_qty = current_positions.get(symbol, 0.0)
            target_qty = target_positions.get(symbol, 0.0)
            
            qty_diff = target_qty - current_qty
            
            # Only generate order if difference is significant
            if abs(qty_diff) > 0.001:  # Minimum order size
                direction = 'BUY' if qty_diff > 0 else 'SELL'
                
                order = OrderEvent(
                    timestamp=timestamp,
                    symbol=symbol,
                    order_type='MARKET',
                    quantity=abs(qty_diff),
                    direction=direction,
                )
                orders.append(order)
        
        return orders

    def _handle_signal_event(self, event: SignalEvent) -> None:
        """Handle signal event.

        Args:
            event: Signal event to handle
        """
        # For now, signal events are just logged
        # In a more complex system, they might trigger additional logic
        pass

    def _handle_order_event(self, event: OrderEvent) -> None:
        """Handle order event by sending to execution.

        Args:
            event: Order event to handle
        """
        if event.symbol in self.current_bars:
            bar = self.current_bars[event.symbol]
            fill_event = self.execution_handler.execute_order(event, bar)
            
            if fill_event:
                self.events.put(fill_event)
        else:
            self.logger.warning(f"No market data for {event.symbol}, skipping order")

    def _handle_fill_event(self, event: FillEvent) -> None:
        """Handle fill event by updating portfolio.

        Args:
            event: Fill event to handle
        """
        self.portfolio.update_from_fill(event)
        
        # Record trade
        self.trade_history.append({
            'timestamp': event.timestamp,
            'symbol': event.symbol,
            'quantity': event.signed_quantity,
            'price': event.fill_price,
            'commission': event.commission,
            'gross_amount': event.gross_amount,
            'net_amount': event.net_amount,
            'strategy': self.strategy.name,
        })

    def run_backtest(self, data: pd.DataFrame) -> Dict:
        """Run the backtest on historical data.

        Args:
            data: Historical OHLCV data

        Returns:
            Backtest results dictionary
        """
        self.logger.info(f"Starting backtest with {len(data)} data points")
        
        # Initialize strategy
        universe = data['symbol'].unique().tolist()
        self.strategy.initialize(universe, data)
        
        # Generate all bar events
        self._generate_bar_events(data)
        
        self.is_running = True
        event_count = 0
        
        # Main event loop
        while not self.events.empty() and self.is_running:
            try:
                event = self.events.get(block=False)
                event_count += 1
                
                # Route events to appropriate handlers
                if isinstance(event, BarEvent):
                    self._handle_bar_event(event)
                elif isinstance(event, SignalEvent):
                    self._handle_signal_event(event)
                elif isinstance(event, OrderEvent):
                    self._handle_order_event(event)
                elif isinstance(event, FillEvent):
                    self._handle_fill_event(event)
                
                # Record portfolio performance
                if isinstance(event, BarEvent):
                    self.performance_history.append({
                        'timestamp': event.timestamp,
                        'total_value': self.portfolio.get_total_value(),
                        'cash': self.portfolio.cash,
                        'positions_value': self.portfolio.get_positions_value(),
                        'unrealized_pnl': self.portfolio.get_unrealized_pnl(),
                        'realized_pnl': self.portfolio.get_realized_pnl(),
                    })
                
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
                continue
        
        self.is_running = False
        
        self.logger.info(
            f"Backtest completed. Processed {event_count} events, "
            f"{len(self.trade_history)} trades, {len(self.signal_history)} signals"
        )
        
        return self.get_results()

    def get_results(self) -> Dict:
        """Get backtest results.

        Returns:
            Dictionary containing backtest results
        """
        if not self.performance_history:
            return {}
        
        # Convert to DataFrames
        performance_df = pd.DataFrame(self.performance_history)
        trades_df = pd.DataFrame(self.trade_history) if self.trade_history else pd.DataFrame()
        signals_df = pd.DataFrame(self.signal_history) if self.signal_history else pd.DataFrame()
        
        # Calculate basic metrics
        final_value = performance_df['total_value'].iloc[-1]
        total_return = (final_value - self.initial_capital) / self.initial_capital
        
        # Calculate daily returns
        performance_df['daily_return'] = performance_df['total_value'].pct_change()
        daily_returns = performance_df['daily_return'].dropna()
        
        # Basic performance metrics
        results = {
            'initial_capital': self.initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'total_trades': len(trades_df),
            'total_signals': len(signals_df),
            'performance_df': performance_df,
            'trades_df': trades_df,
            'signals_df': signals_df,
            'strategy_name': self.strategy.name,
        }
        
        if len(daily_returns) > 0:
            results.update({
                'volatility': daily_returns.std() * (252 ** 0.5),  # Annualized
                'sharpe_ratio': daily_returns.mean() / daily_returns.std() * (252 ** 0.5) if daily_returns.std() > 0 else 0,
                'max_drawdown': self._calculate_max_drawdown(performance_df['total_value']),
            })
        
        return results

    def _calculate_max_drawdown(self, equity_curve: pd.Series) -> float:
        """Calculate maximum drawdown.

        Args:
            equity_curve: Portfolio value time series

        Returns:
            Maximum drawdown as decimal
        """
        peak = equity_curve.cummax()
        drawdown = (equity_curve - peak) / peak
        return drawdown.min()