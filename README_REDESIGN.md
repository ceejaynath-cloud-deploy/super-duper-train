# KimiBot Redesigned (HTF Edition)

Based on original SMC/ICT/CRT/MSNR Bot v3.0 with the following changes:

## Changes Made

| Feature | Original | Redesign |
|---------|----------|----------|
| Required layers | 5 of 6 (H4→M1) | **Only H4 + H1 + M15** |
| Sessions | London + NY | London + NY (**Asia removed**) |
| Execution TF | Mixed down to M1 | **15m** |
| Stop Loss | CRT swing ± 2 pips | **1 × ATR(14)** of the pair |
| Take Profit | 1.5R / 2.5R | **5 × ATR(14)** |
| Trailing stop | Fixed 8 pips | **Every +15% of Entry→TP distance** |
| AI narrative | Groq enabled | **Removed** (saves cost) |
| Scan interval | 60 seconds | **900 seconds (15 min)** – GitHub Actions friendly |

## How to run

1. Copy `.env.example` → `.env` and fill in:
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `TWELVE_DATA_API_KEY` (you already have this)
   - Optional: Polygon / Alpha Vantage

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run locally:
   ```bash
   python main.py
   ```

## GitHub Actions (free tier ~2000 min/month)

Because scanning is now every 15 minutes and only during London+NY sessions, the monthly runtime stays well under the free quota.

A sample workflow file is included: `.github/workflows/scan.yml`

## Pairs

Edit `DEFAULT_PAIRS` in `config.py`. Current default:
- XAUUSD, EURUSD, GBPUSD, USDJPY, AUDUSD

## Important notes

- The original lower-timeframe files (M30, M5, M1) are still present but are no longer required for a signal.
- Trailing stop logic is step-based (15% increments). It is intended for use after a signal is taken (you can call it from a monitoring script or broker).
- This is a **signal bot**, not an auto-execution bot. You still place the trades yourself (or connect it to a broker API later).
