"""
BTC Data Dashboard
==================
Collects and displays:
  1. Actual BTC price + % changes (1h / 4h / 24h) — from Binance
  2. LuxAlgo indicator values — from TradingView (requires login)
  3. BTC options data — from Derive.xyz (fallback: Deribit)

If any data source is unavailable, the corresponding cell shows 0.
No values are estimated or modelled — only actual exchange/chart data.
"""
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich import box
from rich.panel import Panel
from rich.text import Text

from collectors.btc_price import get_btc_price_data
from collectors.tradingview import get_luxalgo_data
from collectors.derive_options import get_derive_options_data


load_dotenv()
console = Console()


def fmt_pct(value: float) -> Text:
    """Format % change with colour: green positive, red negative."""
    sign = "+" if value > 0 else ""
    color = "green" if value > 0 else ("red" if value < 0 else "white")
    return Text(f"{sign}{value:.2f}%", style=color)


def fmt_price(value: float) -> str:
    return f"${value:,.2f}" if value else "0"


def build_price_table(btc: dict) -> Table:
    table = Table(
        title="BTC Цена (Binance BTCUSDT)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Цена", justify="right", style="bold yellow", min_width=14)
    table.add_column("% за 1 час", justify="right", min_width=12)
    table.add_column("% за 4 часа", justify="right", min_width=12)
    table.add_column("% за 24 часа", justify="right", min_width=12)

    table.add_row(
        fmt_price(btc["price"]),
        fmt_pct(btc["change_1h"]),
        fmt_pct(btc["change_4h"]),
        fmt_pct(btc["change_24h"]),
    )
    return table


def build_luxalgo_table(lux: dict) -> Table:
    table = Table(
        title="LuxAlgo — значения с графика TradingView (BTC)",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Индикатор", style="bold", min_width=30)
    table.add_column("Значения", min_width=40)

    if not lux.get("found"):
        # Show reason / note
        note = lux.get("raw_text") or "LuxAlgo не найден на графике"
        table.add_row("[red]Нет данных[/red]", f"[yellow]{note}[/yellow]")
    else:
        for ind in lux["indicators"]:
            name = ind["name"]
            values_str = "  |  ".join(ind["values"]) if ind["values"] else ind.get("raw", "—")
            table.add_row(name, values_str)

    return table


def build_options_table(options: list) -> Table:
    # Detect data source
    source = options[0].get("source", "?") if options else "?"
    source_label = {
        "derive.xyz": "Derive.xyz",
        "deribit": "Deribit (резерв, т.к. Derive.xyz недоступен)",
        "unavailable": "ДАННЫЕ НЕДОСТУПНЫ",
    }.get(source, source)

    table = Table(
        title=f"BTC Опционы — {source_label}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold green",
    )
    table.add_column("Дата экспирации", justify="center", min_width=16)
    table.add_column("Макс. боль ($)", justify="right", min_width=14)
    table.add_column("Пут/Колл", justify="right", min_width=10)
    table.add_column("OI Колл (BTC)", justify="right", min_width=14)
    table.add_column("OI Пут (BTC)", justify="right", min_width=14)

    for row in options:
        max_pain_str = f"${row['max_pain']:,.0f}" if row["max_pain"] else "0"
        pc_ratio = f"{row['put_call_ratio']:.3f}" if row["put_call_ratio"] else "0"
        call_oi = f"{row['call_oi']:,.2f}" if row["call_oi"] else "0"
        put_oi = f"{row['put_oi']:,.2f}" if row["put_oi"] else "0"

        table.add_row(
            row["expiry"],
            max_pain_str,
            pc_ratio,
            call_oi,
            put_oi,
        )
    return table


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    console.print(Panel(f"[bold]BTC Data Dashboard[/bold]  |  {now}", style="blue"))

    # ── 1. BTC Price ──────────────────────────────────────────────────────────
    console.print("\n[cyan]Загружаю цену BTC (Binance)...[/cyan]")
    btc_data = get_btc_price_data()
    console.print(build_price_table(btc_data))

    # ── 2. LuxAlgo via TradingView ────────────────────────────────────────────
    tv_user = os.getenv("TRADINGVIEW_USERNAME", "")
    tv_pass = os.getenv("TRADINGVIEW_PASSWORD", "")
    console.print("\n[magenta]Подключаюсь к TradingView и читаю LuxAlgo...[/magenta]")
    console.print("[dim](это может занять 20–40 секунд)[/dim]")
    lux_data = get_luxalgo_data(tv_user, tv_pass)
    console.print(build_luxalgo_table(lux_data))

    # ── 3. Options from Derive.xyz ────────────────────────────────────────────
    console.print("\n[green]Загружаю данные по BTC опционам (Derive.xyz)...[/green]")
    options_data = get_derive_options_data()
    console.print(build_options_table(options_data))

    console.print("\n[dim]Готово.[/dim]\n")


if __name__ == "__main__":
    main()
