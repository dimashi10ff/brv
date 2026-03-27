"""
Fetches real BTC price data from Binance public API.
Returns actual exchange values — no estimated/modeled data.
"""
import requests


BINANCE_BASE = "https://api.binance.com/api/v3"
SYMBOL = "BTCUSDT"
TIMEOUT = 10


def get_btc_price_data() -> dict:
    """
    Returns:
        price       — current BTC/USDT price
        change_1h   — % change over the last 1h (from open of current 1h candle)
        change_4h   — % change over the last 4h (from open of current 4h candle)
        change_24h  — % change over last 24h (Binance native field, not calculated)
    All values are 0 if data cannot be fetched.
    """
    result = {"price": 0, "change_1h": 0, "change_4h": 0, "change_24h": 0}

    try:
        # 24h ticker — Binance provides priceChangePercent directly
        resp_24h = requests.get(
            f"{BINANCE_BASE}/ticker/24hr",
            params={"symbol": SYMBOL},
            timeout=TIMEOUT,
        )
        resp_24h.raise_for_status()
        ticker = resp_24h.json()
        current_price = float(ticker["lastPrice"])
        change_24h = float(ticker["priceChangePercent"])
        result["price"] = round(current_price, 2)
        result["change_24h"] = round(change_24h, 2)
    except Exception as e:
        print(f"[btc_price] 24h ticker error: {e}")
        return result

    # 1h kline — open of the current ongoing 1h candle is the price 1h ago
    try:
        resp_1h = requests.get(
            f"{BINANCE_BASE}/klines",
            params={"symbol": SYMBOL, "interval": "1h", "limit": 2},
            timeout=TIMEOUT,
        )
        resp_1h.raise_for_status()
        klines_1h = resp_1h.json()
        # klines_1h[-1] is the current (open) candle; index 1 = open price
        open_1h = float(klines_1h[-1][1])
        change_1h = (current_price - open_1h) / open_1h * 100
        result["change_1h"] = round(change_1h, 2)
    except Exception as e:
        print(f"[btc_price] 1h kline error: {e}")

    # 4h kline — open of the current ongoing 4h candle is the price 4h ago
    try:
        resp_4h = requests.get(
            f"{BINANCE_BASE}/klines",
            params={"symbol": SYMBOL, "interval": "4h", "limit": 2},
            timeout=TIMEOUT,
        )
        resp_4h.raise_for_status()
        klines_4h = resp_4h.json()
        open_4h = float(klines_4h[-1][1])
        change_4h = (current_price - open_4h) / open_4h * 100
        result["change_4h"] = round(change_4h, 2)
    except Exception as e:
        print(f"[btc_price] 4h kline error: {e}")

    return result
