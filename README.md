# HF Quant Stack

**Hedge Fund-Style Automated Trading System**

A comprehensive automated trading system with backtesting, portfolio management, risk controls, and live execution adapters. Built for MacBook M1 with production-ready features.

## 🚀 Quick Start

### Prerequisites

- macOS with Apple Silicon (M1/M2) or Intel
- Python 3.11+
- Docker Desktop for Mac
- PostgreSQL (via Docker)

### Installation

1. **Clone the repository:**
```bash
git clone https://github.com/AbsoluteZero000-afk/hf-quant-stack.git
cd hf-quant-stack
```

2. **Set up environment:**
```bash
# Option 1: Using Poetry (recommended)
curl -sSL https://install.python-poetry.org | python3 -
poetry install
poetry shell

# Option 2: Using pip and venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your API keys:
# ALPACA_API_KEY=your_api_key_here
# ALPACA_SECRET_KEY=your_secret_key_here
```

4. **Start services:**
```bash
# Start PostgreSQL and services
docker-compose up -d
```

5. **Initialize system:**
```bash
# Initialize database and create sample data
python -m src.cli init
```

6. **Run your first backtest:**
```bash
# Run momentum strategy backtest
python -m src.cli backtest --strategy momentum --universe sample
```

## 📊 Features

### ✅ **Implemented Strategies**
- **Momentum Strategy**: Daily rebalancing based on price momentum
- **Mean Reversion Strategy**: Pairs trading with cointegration
- **Risk Parity Strategy**: Volatility-weighted portfolio allocation

### ✅ **Backtesting Engine**
- Event-driven architecture
- Transaction costs and slippage modeling
- Portfolio tracking and P&L calculation
- Performance metrics (Sharpe, Sortino, Calmar ratios)

### ✅ **Risk Management**
- Maximum drawdown limits
- Daily loss limits
- Position concentration checks
- Kelly criterion and fractional sizing

### ✅ **Data Management**
- Alpaca API integration
- Sample data generator
- Data normalization and cleaning
- Universe selection (S&P 500, liquid stocks)

### ✅ **Infrastructure**
- PostgreSQL database with SQLAlchemy ORM
- Docker containerization (ARM64 compatible)
- Comprehensive logging with Loguru
- Configuration management

## 🔧 Usage

### Command Line Interface

```bash
# Initialize system
python -m src.cli init

# Run backtests
python -m src.cli backtest --strategy momentum --universe sample
python -m src.cli backtest --strategy mean_reversion --universe sample
python -m src.cli backtest --strategy risk_parity --universe sample

# Check system status
python -m src.cli status
```

### Backtest Example

```python
from src.backtest.engine import BacktestEngine
from src.strategies.momentum import MomentumStrategy
from src.data.fetcher import SampleDataFetcher
from datetime import datetime

# Setup data
data_fetcher = SampleDataFetcher()
symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']
data = data_fetcher.get_bars(symbols, datetime(2023, 1, 1), datetime(2024, 1, 1))

# Create strategy
strategy = MomentumStrategy({
    'lookback_days': 21,
    'top_n_stocks': 10,
    'rebalance_frequency': 'daily'
})

# Run backtest
engine = BacktestEngine(strategy, initial_capital=100000)
results = engine.run_backtest(data)

print(f"Total Return: {results['total_return']:.2%}")
print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
```

## 📁 Project Structure

```
hf-quant-stack/
├── src/
│   ├── backtest/          # Event-driven backtesting engine
│   ├── data/             # Data fetching and processing
│   ├── db/               # Database models and session management
│   ├── execution/        # Order execution handlers (Alpaca)
│   ├── risk/             # Risk management and position sizing
│   ├── strategies/       # Trading strategy implementations
│   ├── utils/            # Utilities (logging, timing)
│   ├── cli.py            # Command-line interface
│   └── config.py         # Configuration management
├── tests/                # Unit and integration tests
├── notebooks/            # Jupyter analysis notebooks
├── reports/              # Generated reports and results
├── data/                 # Sample and historical data
├── alembic/              # Database migrations
├── docker-compose.yml    # Docker services configuration
├── Dockerfile            # Container definition (ARM64 compatible)
├── pyproject.toml        # Poetry dependencies
├── requirements.txt      # Pip dependencies
└── config.yml            # System configuration
```

## 🔒 Security & API Keys

**Required API Keys:**

1. **Alpaca Trading API** (Paper Trading):
   - Sign up at [alpaca.markets](https://alpaca.markets)
   - Get API key and secret from dashboard
   - Add to `.env` file

```bash
# .env file
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
```

**Note**: The system defaults to paper trading for safety. Never commit API keys to git.

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_strategies.py
```

## 📈 Performance Monitoring

The system generates comprehensive performance reports:

- **CSV Reports**: Detailed P&L and position data
- **Performance Metrics**: Sharpe, Sortino, Calmar ratios
- **Risk Analytics**: Drawdown analysis, VaR calculations
- **Trade Analysis**: Win rate, profit factor, trade distribution

## 🐛 Troubleshooting

### Common Issues

1. **Import Errors**:
   ```bash
   # Ensure you're in the project root and environment is activated
   export PYTHONPATH=$PWD:$PYTHONPATH
   ```

2. **Database Connection**:
   ```bash
   # Check PostgreSQL is running
   docker-compose ps
   # Restart if needed
   docker-compose restart postgres
   ```

3. **Permission Errors**:
   ```bash
   # Fix Docker permissions on macOS
   sudo chown -R $(whoami) .
   ```

4. **M1 Mac Compatibility**:
   - All dependencies are ARM64 compatible
   - Use `--platform linux/arm64` for Docker builds
   - Avoid TA-Lib (use pandas/numpy implementations)

## ⚠️ Disclaimer

This software is for educational and research purposes only. Trading involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. Always consult with a qualified financial advisor before making investment decisions.

---

**Built with ❤️ for quantitative trading**