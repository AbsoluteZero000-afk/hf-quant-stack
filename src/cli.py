#!/usr/bin/env python3
"""Command line interface for the trading system."""

import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console

from src.backtest.engine import BacktestEngine
from src.config import config
from src.data.fetcher import SampleDataFetcher
from src.data.sample import create_default_sample_data
from src.data.universe import UniverseSelector
from src.db.session import init_db
from src.strategies.mean_reversion import MeanReversionStrategy
from src.strategies.momentum import MomentumStrategy
from src.strategies.risk_parity import RiskParityStrategy
from src.utils.logging import setup_logging

console = Console()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """Hedge Fund Quantitative Trading Stack CLI."""
    level = "DEBUG" if verbose else "INFO"
    setup_logging(level=level, console_output=True)


@cli.command()
def init() -> None:
    """Initialize the database and create sample data."""
    console.print("[bold blue]Initializing HF Quant Stack...[/bold blue]")

    try:
        console.print("Initializing database...")
        init_db()
        console.print("[green]✓ Database initialized[/green]")

        console.print("Creating sample data...")
        sample_file = create_default_sample_data()
        console.print(f"[green]✓ Sample data created: {sample_file}[/green]")

        console.print("[bold green]Initialization complete![/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--strategy",
    "-s",
    type=click.Choice(["momentum", "mean_reversion", "risk_parity"]),
    default="momentum",
    help="Strategy to backtest",
)
@click.option("--universe", "-u", default="sample", help="Universe to use")
def backtest(strategy: str, universe: str) -> None:
    """Run backtests for trading strategies."""
    console.print(f"[bold blue]Running {strategy} strategy backtest...[/bold blue]")

    try:
        # Setup data
        data_fetcher = SampleDataFetcher()
        universe_selector = UniverseSelector(data_fetcher)
        symbols = universe_selector.get_sample_universe(20)

        console.print(f"Universe: {len(symbols)} symbols")

        # Get data
        start_dt = datetime(2023, 1, 1)
        end_dt = datetime(2024, 1, 1)
        data = data_fetcher.get_bars(symbols, start_dt, end_dt)

        if data.empty:
            console.print("[red]No data available for backtest[/red]")
            return

        console.print(f"Data: {len(data)} bars")

        # Create strategy
        if strategy == "momentum":
            strategy_config = config.get_strategy_config("momentum")
            strategy_obj = MomentumStrategy(strategy_config)
        elif strategy == "mean_reversion":
            strategy_config = config.get_strategy_config("mean_reversion")
            strategy_obj = MeanReversionStrategy(strategy_config)
        else:  # risk_parity
            strategy_config = config.get_strategy_config("risk_parity")
            strategy_obj = RiskParityStrategy(strategy_config)

        # Run backtest
        engine = BacktestEngine(
            strategy=strategy_obj,
            initial_capital=100000.0,
            commission_per_share=0.0,
            slippage_bps=5.0,
        )

        results = engine.run_backtest(data)

        # Create reports directory
        Path("reports").mkdir(exist_ok=True)

        # Save results
        output_file = f"reports/{strategy}_pnl.csv"
        if "performance_df" in results:
            results["performance_df"].to_csv(output_file, index=False)
            console.print(f"[green]✓ Results saved to {output_file}[/green]")

        # Display summary
        console.print("\n[bold green]Backtest Results[/bold green]")
        console.print(f"Total Return: {results.get('total_return', 0):.2%}")
        console.print(f"Sharpe Ratio: {results.get('sharpe_ratio', 0):.2f}")
        console.print(f"Max Drawdown: {results.get('max_drawdown', 0):.2%}")
        console.print(f"Total Trades: {results.get('total_trades', 0)}")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        sys.exit(1)


def main() -> None:
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
