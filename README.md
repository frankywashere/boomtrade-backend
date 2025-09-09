# BoomTrade Backend

IBKR trading backend using IBeam for gateway management.

## Deployment on Render

1. Push this backend folder to a GitHub repository
2. Connect your GitHub account to Render
3. Create a new Web Service on Render
4. Select your repository and configure:
   - Build Command: `docker build -t boomtrade-backend .`
   - Start Command: `python main.py`
   - Plan: Free (will spin down after 15 min)

## Environment Variables (Optional)

Set these in Render dashboard if needed:
- `IBKR_USERNAME` - Your IBKR username
- `IBKR_PASSWORD` - Your IBKR password (encrypted)
- `IBKR_ACCOUNT` - Your account ID

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python main.py
```

## API Endpoints

- `POST /gateway/start` - Start IBeam gateway with credentials
- `GET /account` - Get account info
- `GET /positions` - Get current positions
- `GET /marketdata/{symbol}` - Get market data for symbol
- `GET /options/search/{symbol}` - Search option chains
- `GET /options/chain/{symbol}/{expiry}` - Get specific option chain
- `POST /order/stock` - Place stock order
- `POST /order/option` - Place option order
- `WS /ws/marketdata` - WebSocket for real-time data

## Notes

- Gateway takes 60-90 seconds to start on cold boot
- 2FA is handled automatically by IBeam
- Server spins down after 15 min of inactivity on free tier
- Consider upgrading to Starter plan ($7/month) for always-on