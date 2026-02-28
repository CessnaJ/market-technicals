# Technical Analysis Dashboard

A comprehensive technical analysis dashboard for Korean stock market data using KIS (Korea Investment Securities) API.

## Features

- **Basic Technical Indicators**: SMA, EMA, VWMA, MACD, RSI, Bollinger Bands
- **Custom Indicators**:
  - VPCI (Volume Price Confirmation Indicator) - False signal detection
  - Weinstein Stage Analysis - 4-stage market cycle analysis
  - Darvas Box - 3-day rule box theory
  - Fibonacci Retracement - Auto-detection with confluence zones
- **False Signal Detection**: VPCI divergence analysis
- **Data Visualization**: TradingView Lightweight Charts with log/linear scale
- **Financial Metrics**: PSR, PER, PBR, ROE, etc.
- **Watchlist Management**: Track stocks of interest

## Tech Stack

### Backend
- **Python 3.12** + **FastAPI** (async)
- **PostgreSQL 16** - Time-series data storage
- **Redis** - API response caching
- **SQLAlchemy 2.0** - Async ORM
- **Pandas/NumPy** - Indicator calculations

### Frontend
- **React** + **TypeScript**
- **TradingView Lightweight Charts** - Financial charting
- **Tailwind CSS** - Styling
- **Vite** - Build tool

### Infrastructure
- **Docker Compose** - Service orchestration

## Project Structure

```
market-technicals/
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py
│       ├── core/          # Config, DB, Redis
│       ├── models/         # SQLAlchemy ORM
│       ├── schemas/        # Pydantic schemas
│       ├── services/       # KIS API, data service
│       ├── indicators/     # Technical indicators
│       └── api/           # API endpoints
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── hooks/
│       └── api/
└── nginx/
    └── nginx.conf
```

## Quick Start

### Prerequisites
- Docker and Docker Compose
- KIS API credentials (app_key, app_secret, account_no)

### Setup

1. Clone the repository
```bash
cd market-technicals
```

2. Create environment file
```bash
cp .env.example .env
```

3. Edit `.env` with your KIS API credentials
```bash
KIS_APP_KEY=your_kis_app_key
KIS_APP_SECRET=your_kis_app_secret
KIS_ACCOUNT_NO=12345678-01
```

4. Start all services
```bash
docker-compose up -d
```

5. Access the application
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### Stopping Services
```bash
docker-compose down
```

## API Endpoints

### Watchlist
- `GET /api/v1/watchlist` - Get watchlist
- `POST /api/v1/watchlist` - Add stock to watchlist
- `DELETE /api/v1/watchlist/{ticker}` - Remove from watchlist

### Data Fetching
- `POST /api/v1/fetch/{ticker}` - Fetch data for specific stock
- `POST /api/v1/fetch/batch` - Batch fetch for watchlist

### Chart Data
- `GET /api/v1/chart/{ticker}` - Get chart data (OHLCV + indicators)
  - Query params: `timeframe`, `start_date`, `end_date`, `scale`

### Indicators
- `GET /api/v1/indicators/{ticker}/weinstein` - Weinstein Stage Analysis
- `GET /api/v1/indicators/{ticker}/vpci` - VPCI
- `GET /api/v1/indicators/{ticker}/darvas` - Darvas Boxes
- `GET /api/v1/indicators/{ticker}/fibonacci` - Fibonacci Levels

### Signals
- `GET /api/v1/signals/{ticker}` - Signal history
- `GET /api/v1/signals/{ticker}/latest` - Latest signals

### Financial Data
- `GET /api/v1/financial/{ticker}` - Financial metrics
- `GET /api/v1/financial/{ticker}/psr-history` - PSR history

## Development

### Backend Development
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

## Architecture Details

See [context.md](../context.md) for detailed architecture documentation.

## License

MIT
