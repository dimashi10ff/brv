"""
Connects to TradingView via Playwright, logs in, opens the BTC chart,
and reads LuxAlgo indicator values from the chart legend.
Returns actual values from the chart — nothing is calculated or estimated.
"""
import time
import re

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


TV_URL = "https://www.tradingview.com"
CHART_URL = "https://www.tradingview.com/chart/?symbol=BINANCE:BTCUSDT"


def _empty_result(reason: str = "") -> dict:
    if reason:
        print(f"[tradingview] {reason}")
    return {
        "found": False,
        "indicators": [],
        "raw_text": "0",
    }


def get_luxalgo_data(username: str, password: str) -> dict:
    """
    Logs in to TradingView and reads LuxAlgo indicator values from the BTC chart legend.

    Returns dict:
        found      — bool, whether LuxAlgo was found on chart
        indicators — list of dicts: [{name, values: [str, ...]}, ...]
        raw_text   — raw string of all LuxAlgo legend text (for display)
    """
    if not PLAYWRIGHT_AVAILABLE:
        return _empty_result("playwright not installed — run: pip install playwright && playwright install chromium")

    if not username or not password:
        return _empty_result("TradingView credentials not set")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            # Hide webdriver flag
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            page = context.new_page()

            result = _login_and_read(page, username, password)
            browser.close()
            return result

    except Exception as e:
        return _empty_result(f"Playwright error: {e}")


def _login_and_read(page, username: str, password: str) -> dict:
    # ── Step 1: open TradingView ──────────────────────────────────────────────
    try:
        page.goto(TV_URL, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(2)
    except Exception as e:
        return _empty_result(f"Cannot open TradingView: {e}")

    # ── Step 2: click "Sign in" ───────────────────────────────────────────────
    try:
        # Try header sign-in button first
        signin_selectors = [
            'button[data-name="header-user-menu-sign-in"]',
            '[data-name="sign-in-button"]',
            'button:has-text("Sign in")',
            'a:has-text("Sign in")',
        ]
        clicked = False
        for sel in signin_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=3_000):
                    btn.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            return _empty_result("Could not find 'Sign in' button")
        time.sleep(1)
    except Exception as e:
        return _empty_result(f"Sign-in button error: {e}")

    # ── Step 3: choose "Email" login tab if present ───────────────────────────
    try:
        email_tab_selectors = [
            '[name="Email"]',
            'button:has-text("Email")',
            '[data-name="Email"]',
        ]
        for sel in email_tab_selectors:
            try:
                tab = page.locator(sel).first
                if tab.is_visible(timeout=2_000):
                    tab.click()
                    time.sleep(0.5)
                    break
            except Exception:
                continue
    except Exception:
        pass  # Maybe not needed — already on email tab

    # ── Step 4: fill credentials ──────────────────────────────────────────────
    try:
        # username field
        user_selectors = [
            'input[name="username"]',
            'input[id="username"]',
            'input[autocomplete="username"]',
            'input[type="text"]',
        ]
        filled_user = False
        for sel in user_selectors:
            try:
                field = page.locator(sel).first
                if field.is_visible(timeout=2_000):
                    field.fill(username)
                    filled_user = True
                    break
            except Exception:
                continue
        if not filled_user:
            return _empty_result("Cannot find username input field")

        # password field
        pass_selectors = [
            'input[name="password"]',
            'input[id="password"]',
            'input[type="password"]',
        ]
        filled_pass = False
        for sel in pass_selectors:
            try:
                field = page.locator(sel).first
                if field.is_visible(timeout=2_000):
                    field.fill(password)
                    filled_pass = True
                    break
            except Exception:
                continue
        if not filled_pass:
            return _empty_result("Cannot find password input field")

    except Exception as e:
        return _empty_result(f"Fill credentials error: {e}")

    # ── Step 5: submit ────────────────────────────────────────────────────────
    try:
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Sign in")',
        ]
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=2_000):
                    btn.click()
                    break
            except Exception:
                continue
        time.sleep(5)
    except Exception as e:
        return _empty_result(f"Submit error: {e}")

    # Check if login failed (error message present)
    try:
        error_el = page.locator('[class*="error"]').first
        if error_el.is_visible(timeout=1_000):
            error_text = error_el.inner_text()
            return _empty_result(f"TradingView login failed: {error_text}")
    except Exception:
        pass

    # ── Step 6: navigate to BTC chart ────────────────────────────────────────
    try:
        page.goto(CHART_URL, wait_until="domcontentloaded", timeout=30_000)
        # Wait for chart canvas to appear
        page.wait_for_selector("canvas", timeout=30_000)
        time.sleep(12)  # allow indicators to fully load
    except Exception as e:
        return _empty_result(f"Cannot open BTC chart: {e}")

    # ── Step 7: read LuxAlgo from legend ─────────────────────────────────────
    return _extract_luxalgo(page)


def _extract_luxalgo(page) -> dict:
    """
    Searches the chart legend for any LuxAlgo indicator and extracts its values.
    TradingView renders legend items in elements whose class names contain 'legend'.
    """
    luxalgo_items = []

    # Collect all text from the legend area
    legend_selectors = [
        '[class*="legendItem"]',
        '[class*="legend-item"]',
        '[class*="pane-legend"]',
        '[data-name*="legend"]',
        '[class*="seriesTitle"]',
    ]

    all_legend_texts = []
    for sel in legend_selectors:
        try:
            elements = page.locator(sel).all()
            for el in elements:
                try:
                    txt = el.inner_text(timeout=2_000).strip()
                    if txt:
                        all_legend_texts.append(txt)
                except Exception:
                    pass
        except Exception:
            pass

    # Also try full page text search as fallback
    if not all_legend_texts:
        try:
            body_text = page.inner_text("body")
            # Only keep lines mentioning lux
            for line in body_text.splitlines():
                if "lux" in line.lower():
                    all_legend_texts.append(line.strip())
        except Exception:
            pass

    # Filter for LuxAlgo entries
    for text in all_legend_texts:
        if "lux" in text.lower():
            luxalgo_items.append(text)

    if not luxalgo_items:
        return _empty_result("LuxAlgo indicator not found on the chart — make sure it is added to your saved BTC layout on TradingView")

    # Parse indicator blocks
    indicators = []
    for raw in luxalgo_items:
        # Try to split name from values (TradingView format: "Name ▸ val1 val2")
        parts = re.split(r"[▸►:]\s*", raw, maxsplit=1)
        name = parts[0].strip() if parts else raw
        values_str = parts[1].strip() if len(parts) > 1 else ""
        values = [v.strip() for v in re.split(r"[\s,|]+", values_str) if v.strip()] if values_str else []
        indicators.append({"name": name, "values": values, "raw": raw})

    return {
        "found": True,
        "indicators": indicators,
        "raw_text": "\n".join(luxalgo_items),
    }
