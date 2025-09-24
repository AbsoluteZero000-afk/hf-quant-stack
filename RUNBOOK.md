# HF Quant Stack Runbook

**Complete Step-by-Step Guide for Setup and Operation**

## 🚀 First-Time Setup

### Prerequisites

1. **System Requirements:**
   - macOS (M1/M2 recommended) or Linux
   - Python 3.11 or higher
   - Docker Desktop
   - Git

2. **Account Setup:**
   - [Alpaca Markets Account](https://alpaca.markets) (Free)
   - GitHub account (for repository access)

### Step 1: Clone Repository

```bash
# Clone the repository
git clone https://github.com/AbsoluteZero000-afk/hf-quant-stack.git
cd hf-quant-stack

# Verify you're on the main branch
git branch
git status
```

### Step 2: Environment Setup

**Option A: Poetry (Recommended)**
```bash
# Install Poetry if not already installed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

**Option B: Virtual Environment + pip**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### Step 3: API Keys Configuration

1. **Get Alpaca API Keys:**
   - Sign up at [alpaca.markets](https://alpaca.markets)
   - Go to Dashboard → API Keys
   - Generate Paper Trading keys (recommended for development)

2. **Configure Environment:**
```bash
# Copy environment template
cp .env.example .env

# Edit .env file with your actual keys
nano .env  # or use your preferred editor
```

3. **Required .env Configuration:**
```bash
# Database
DATABASE_URL=postgresql://trader:secure_password@localhost:5432/trading_db

# Alpaca API (Paper Trading)
ALPACA_API_KEY=YOUR_ALPACA_API_KEY
ALPACA_SECRET_KEY=YOUR_ALPACA_SECRET_KEY
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Environment
ENVIRONMENT=development
LOG_LEVEL=INFO
```

### Step 4: Database Setup

```bash
# Start PostgreSQL with Docker
docker-compose up -d postgres

# Wait for database to be ready (check health)
docker-compose ps

# Initialize database and create sample data
python -m src.cli init
```

### Step 5: Verify Installation

```bash
# Check system status
python -m src.cli status

# Expected output:
# ✓ Database connection OK
# ✓ Sample data available
```

## 📈 Running Backtests

### Basic Backtest Commands

```bash
# Run momentum strategy backtest
python -m src.cli backtest --strategy momentum --universe sample

# Run mean reversion strategy
python -m src.cli backtest --strategy mean_reversion --universe sample

# Run risk parity strategy
python -m src.cli backtest --strategy risk_parity --universe sample
```

### Advanced Backtest Options

```bash
# Custom date range and capital
python -m src.cli backtest \
    --strategy momentum \
    --universe sample \
    --start-date 2023-01-01 \
    --end-date 2024-01-01 \
    --initial-capital 250000 \
    --output-dir custom_reports

# Run all strategies
python -m src.cli backtest --strategy all --universe sample
```

### Understanding Results

After running a backtest, check the `reports/` directory:

```bash
# View generated reports
ls -la reports/

# Example files:
# momentum_backtest.csv      # Detailed P&L data
# momentum_trades.csv        # Individual trades
# momentum_signals.csv       # Strategy signals
```

**Key Metrics to Monitor:**
- **Total Return**: Overall strategy performance
- **Sharpe Ratio**: Risk-adjusted return (>1.0 is good, >2.0 is excellent)
- **Max Drawdown**: Worst peak-to-trough decline (<10% target)
- **Win Rate**: Percentage of profitable trades

## 📊 Paper Trading

### Prerequisites
- Valid Alpaca API keys in `.env`
- Paper trading account funded (virtual money)
- Market hours: 9:30 AM - 4:00 PM ET

### Starting Paper Trading

```bash
# Start paper trading (dry run first)
python -m src.cli paper --strategy momentum --universe sample --dry-run

# Start actual paper trading
python -m src.cli paper --strategy momentum --universe sample
```

### Monitoring Paper Trading

```bash
# Check account status
python -c "
from src.execution.paper_alpaca import PaperAlpacaExecutionHandler
handler = PaperAlpacaExecutionHandler()
print(handler.get_account_info())
print(handler.get_positions())
"

# View logs
tail -f logs/trading.log
```

## 🧪 Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_strategies.py -v

# Run integration tests only
pytest tests/test_integration.py
```

### Test Categories

- **Unit Tests**: Individual component testing
- **Integration Tests**: End-to-end system testing
- **Smoke Tests**: Basic functionality verification
- **Performance Tests**: Backtesting engine validation

## 🔧 Development Workflow

### Code Quality

```bash
# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/ tests/
mypy src/

# Run pre-commit hooks
pre-commit install
pre-commit run --all-files
```

### Database Management

```bash
# Reset database (WARNING: Deletes all data)
python -c "from src.db.session import reset_database; reset_database()"

# Create new migration
# (after modifying models in src/db/models.py)
alembic revision --autogenerate -m "Add new model"

# Apply migrations
alembic upgrade head
```

### Adding New Strategies

1. **Create Strategy Class:**
```python
# src/strategies/my_strategy.py
from src.strategies.base import BaseStrategy, Signal

class MyStrategy(BaseStrategy):
    def __init__(self, config: dict):
        super().__init__("MyStrategy", config)
        
    def generate_signals(self, data, timestamp):
        # Implement your signal logic
        return []
        
    def calculate_position_sizes(self, signals, portfolio_value, positions):
        # Implement your position sizing
        return {}
```

2. **Add to CLI:**
   - Edit `src/cli.py`
   - Add import and choice option
   - Add strategy configuration to `config.yml`

3. **Add Tests:**
   - Create `tests/test_my_strategy.py`
   - Test initialization and signal generation

## 🐳 Docker Deployment

### Local Development

```bash
# Start full stack
docker-compose up -d

# View logs
docker-compose logs -f app

# Access Jupyter (development profile)
docker-compose --profile dev up -d jupyter
# Navigate to http://localhost:8888

# Access Streamlit dashboard (when implemented)
docker-compose --profile dashboard up -d streamlit
# Navigate to http://localhost:8501
```

### Production Deployment

```bash
# Build production image
docker build -t hf-quant-stack:latest .

# Run with production settings
docker run -d \
  --name hf-trading \
  --env-file .env \
  -v $(pwd)/data:/home/trader/data \
  -v $(pwd)/reports:/home/trader/reports \
  hf-quant-stack:latest
```

## 🚨 Troubleshooting

### Common Issues

**1. Import Errors**
```bash
# Ensure PYTHONPATH is set
export PYTHONPATH=$PWD:$PYTHONPATH

# Or run from project root
cd /path/to/hf-quant-stack
python -m src.cli --help
```

**2. Database Connection Issues**
```bash
# Check PostgreSQL status
docker-compose ps postgres

# Restart PostgreSQL
docker-compose restart postgres

# Check database logs
docker-compose logs postgres
```

**3. API Connection Issues**
```bash
# Test Alpaca connection
python -c "
from src.data.fetcher import AlpacaDataFetcher
fetcher = AlpacaDataFetcher()
print('Connection successful')
"
```

**4. Permissions on macOS**
```bash
# Fix Docker permissions
sudo chown -R $(whoami) .

# Reset Docker if needed
docker system prune -a
```

### Log Analysis

```bash
# View application logs
tail -f logs/trading.log

# Filter for errors only
grep ERROR logs/trading.log

# View Docker container logs
docker-compose logs -f app
```

## 📱 Monitoring & Alerts

### Health Checks

```bash
# System health check
python -m src.cli status

# Database health
psql $DATABASE_URL -c "SELECT 1;"

# Check running processes
ps aux | grep python
```

### Performance Monitoring

```bash
# View recent performance
tail -20 reports/momentum_backtest.csv

# Check portfolio status
python -c "
from src.db.session import get_session
from src.db.models import Portfolio
with get_session() as session:
    portfolios = session.query(Portfolio).all()
    for p in portfolios:
        print(f'{p.name}: ${p.current_capital:.2f}')
"
```

## 🔒 Security Best Practices

1. **Never commit API keys:**
   ```bash
   # Check for accidentally committed secrets
   git log --all --grep="API_KEY\|SECRET\|PASSWORD" --oneline
   ```

2. **Use paper trading:**
   - Always start with paper trading
   - Verify strategies before live trading
   - Monitor for several weeks minimum

3. **Regular backups:**
   ```bash
   # Backup database
   docker exec -t hf-postgres pg_dump -U trader trading_db > backup_$(date +%Y%m%d).sql
   ```

4. **Monitor logs:**
   ```bash
   # Set up log rotation
   # Logs are automatically rotated by loguru
   # Check disk space regularly
   df -h
   ```

## 📞 Getting Help

1. **Check logs first:**
   ```bash
   tail -50 logs/trading.log
   ```

2. **Run diagnostics:**
   ```bash
   python -m src.cli status
   ```

3. **Test individual components:**
   ```bash
   pytest tests/test_strategies.py -v
   ```

4. **GitHub Issues:**
   - Check existing issues
   - Provide full error messages
   - Include system information

---

**Remember: This system uses paper trading by default for safety. Always test thoroughly before considering live trading.**