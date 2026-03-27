"""
Fetches BTC options data from Derive.xyz public REST API.
Collects: expiration dates, put/call OI ratio, max pain price.

Max pain is computed from actual open interest data (OI at each strike),
not estimated — it's the standard industry metric.
If data is unavailable, all values are returned as 0.
"""
import requests
from collections import defaultdict
from datetime import datetime


TIMEOUT = 15

# Derive.xyz API base (formerly Lyra Finance)
DERIVE_BASE = "https://api.derive.xyz"

# Fallback: Deribit public API (much higher BTC options liquidity)
DERIBIT_BASE = "https://www.deribit.com/api/v2"


# ── Derive.xyz ────────────────────────────────────────────────────────────────

def _fetch_derive_instruments() -> list:
    """Fetch all active BTC option instruments from Derive.xyz."""
    try:
        resp = requests.get(
            f"{DERIVE_BASE}/public/get_instruments",
            params={"currency": "BTC", "kind": "option", "expired": "false"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        # Derive API wraps result in {"result": [...]} or {"instruments": [...]}
        if isinstance(data, dict):
            return data.get("result", data.get("instruments", []))
        return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[derive] get_instruments error: {e}")
        return []


def _fetch_derive_ticker(instrument_name: str) -> dict:
    """Fetch ticker (including OI) for a single instrument."""
    try:
        resp = requests.get(
            f"{DERIVE_BASE}/public/get_ticker",
            params={"instrument_name": instrument_name},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            return data.get("result", data)
        return {}
    except Exception:
        return {}


def _parse_derive_instrument_name(name: str):
    """
    Parse Derive.xyz instrument name.
    Format: BTC-DDMMMYY-STRIKE-C/P  e.g. BTC-27DEC24-50000-C
    Returns (expiry_str, strike_float, option_type) or None on failure.
    """
    try:
        parts = name.split("-")
        if len(parts) != 4:
            return None
        _, expiry, strike, opt_type = parts
        return expiry, float(strike), opt_type.upper()
    except Exception:
        return None


def _get_derive_options_data() -> list | None:
    """
    Returns list of dicts per expiration:
    [{expiry, call_oi, put_oi, strikes: {strike: {call_oi, put_oi}}}]
    Returns None if API unreachable.
    """
    instruments = _fetch_derive_instruments()
    if not instruments:
        return None

    # Group by expiration
    expiry_data: dict[str, dict] = defaultdict(
        lambda: {"call_oi": 0.0, "put_oi": 0.0, "strikes": defaultdict(lambda: {"call_oi": 0.0, "put_oi": 0.0})}
    )

    for inst in instruments:
        name = inst.get("instrument_name", "")
        parsed = _parse_derive_instrument_name(name)
        if not parsed:
            continue
        expiry, strike, opt_type = parsed

        ticker = _fetch_derive_ticker(name)
        oi = float(ticker.get("open_interest", 0) or 0)

        if opt_type == "C":
            expiry_data[expiry]["call_oi"] += oi
            expiry_data[expiry]["strikes"][strike]["call_oi"] += oi
        elif opt_type == "P":
            expiry_data[expiry]["put_oi"] += oi
            expiry_data[expiry]["strikes"][strike]["put_oi"] += oi

    if not expiry_data:
        return None

    result = []
    for expiry, data in sorted(expiry_data.items()):
        result.append({
            "expiry": expiry,
            "call_oi": data["call_oi"],
            "put_oi": data["put_oi"],
            "strikes": dict(data["strikes"]),
        })
    return result


# ── Deribit fallback ──────────────────────────────────────────────────────────

def _fetch_deribit_instruments() -> list:
    """Fetch all active BTC option instruments from Deribit."""
    try:
        resp = requests.get(
            f"{DERIBIT_BASE}/public/get_instruments",
            params={"currency": "BTC", "kind": "option", "expired": "false"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])
    except Exception as e:
        print(f"[deribit] get_instruments error: {e}")
        return []


def _fetch_deribit_book_summary_by_currency() -> list:
    """
    Fetch all BTC option tickers at once via Deribit's bulk endpoint.
    Returns list of ticker dicts with open_interest.
    """
    try:
        resp = requests.get(
            f"{DERIBIT_BASE}/public/get_book_summary_by_currency",
            params={"currency": "BTC", "kind": "option"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", [])
    except Exception as e:
        print(f"[deribit] book_summary error: {e}")
        return []


def _parse_deribit_instrument_name(name: str):
    """
    Parse Deribit instrument name.
    Format: BTC-27DEC24-50000-C
    Returns (expiry_str, strike_float, option_type) or None.
    """
    try:
        parts = name.split("-")
        if len(parts) != 4:
            return None
        _, expiry, strike, opt_type = parts
        return expiry, float(strike), opt_type.upper()
    except Exception:
        return None


def _get_deribit_options_data() -> list | None:
    """
    Returns same structure as _get_derive_options_data but from Deribit.
    """
    summaries = _fetch_deribit_book_summary_by_currency()
    if not summaries:
        return None

    expiry_data: dict[str, dict] = defaultdict(
        lambda: {"call_oi": 0.0, "put_oi": 0.0, "strikes": defaultdict(lambda: {"call_oi": 0.0, "put_oi": 0.0})}
    )

    for item in summaries:
        name = item.get("instrument_name", "")
        parsed = _parse_deribit_instrument_name(name)
        if not parsed:
            continue
        expiry, strike, opt_type = parsed
        # Deribit OI is in BTC contracts; multiply by underlying price for USD OI
        oi = float(item.get("open_interest", 0) or 0)

        if opt_type == "C":
            expiry_data[expiry]["call_oi"] += oi
            expiry_data[expiry]["strikes"][strike]["call_oi"] += oi
        elif opt_type == "P":
            expiry_data[expiry]["put_oi"] += oi
            expiry_data[expiry]["strikes"][strike]["put_oi"] += oi

    if not expiry_data:
        return None

    result = []
    for expiry, data in sorted(expiry_data.items()):
        result.append({
            "expiry": expiry,
            "call_oi": data["call_oi"],
            "put_oi": data["put_oi"],
            "strikes": dict(data["strikes"]),
        })
    return result


# ── Max pain ──────────────────────────────────────────────────────────────────

def _compute_max_pain(strikes_data: dict) -> float:
    """
    Compute max pain strike from actual OI data.
    Max pain = strike where total payout to option BUYERS is minimized
    (i.e., where option SELLERS lose the least).

    For each candidate expiry price S:
      loss_calls = sum over strikes K < S  of (S - K) * call_OI[K]
      loss_puts  = sum over strikes K > S  of (K - S) * put_OI[K]
      total_loss = loss_calls + loss_puts
    Max pain = S that minimizes total_loss.
    Uses actual strike prices as candidates.
    """
    if not strikes_data:
        return 0.0

    all_strikes = sorted(strikes_data.keys())
    min_loss = float("inf")
    max_pain_strike = 0.0

    for candidate in all_strikes:
        loss = 0.0
        for strike, oi_data in strikes_data.items():
            call_oi = oi_data.get("call_oi", 0)
            put_oi = oi_data.get("put_oi", 0)
            if strike < candidate:
                loss += (candidate - strike) * call_oi
            elif strike > candidate:
                loss += (strike - candidate) * put_oi
        if loss < min_loss:
            min_loss = loss
            max_pain_strike = candidate

    return max_pain_strike


# ── Public interface ──────────────────────────────────────────────────────────

def get_derive_options_data() -> list:
    """
    Main entry point. Tries Derive.xyz first, falls back to Deribit.
    Returns list of dicts per expiration:
    [
        {
            "expiry": "27DEC24",
            "put_call_ratio": 0.85,
            "max_pain": 95000.0,
            "call_oi": 1234.5,
            "put_oi": 1050.0,
            "source": "derive.xyz" | "deribit" | "unavailable"
        },
        ...
    ]
    If no data available at all, returns single entry with zeros and source="unavailable".
    """
    source = "derive.xyz"
    data = _get_derive_options_data()

    if not data:
        print("[options] Derive.xyz unavailable or returned no data — trying Deribit...")
        source = "deribit"
        data = _get_deribit_options_data()

    if not data:
        print("[options] Both Derive.xyz and Deribit unavailable")
        return [
            {
                "expiry": "N/A",
                "put_call_ratio": 0,
                "max_pain": 0,
                "call_oi": 0,
                "put_oi": 0,
                "source": "unavailable",
            }
        ]

    result = []
    for entry in data:
        call_oi = entry["call_oi"]
        put_oi = entry["put_oi"]
        total_oi = call_oi + put_oi

        put_call_ratio = round(put_oi / call_oi, 3) if call_oi > 0 else 0
        max_pain = _compute_max_pain(entry["strikes"])

        result.append(
            {
                "expiry": entry["expiry"],
                "put_call_ratio": put_call_ratio,
                "max_pain": round(max_pain, 0),
                "call_oi": round(call_oi, 2),
                "put_oi": round(put_oi, 2),
                "source": source,
            }
        )

    return result
