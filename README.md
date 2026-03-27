# BTC Data Dashboard

Собирает актуальные данные по BTC и выводит таблицу:
- **Цена + % изменения** (1ч / 4ч / 24ч) — Binance
- **Показатели LuxAlgo** — с вашего графика TradingView
- **Опционы BTC** (макс. боль, экспирация, пут/колл) — Derive.xyz

---

## Требования

- Python 3.10 или выше
- Git (для клонирования)
- Интернет-доступ без прокси-блокировок

---

## Установка

### 1. Клонировать репозиторий

```bash
git clone https://github.com/dimashi10ff/brv.git
cd brv
git checkout claude/btc-data-tradingview-m6rEk
```

### 2. Создать виртуальное окружение (рекомендуется)

```bash
python -m venv venv

# Linux / macOS:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Установить браузер для Playwright

```bash
playwright install chromium
```

### 5. Создать файл с credentials

Создайте файл `.env` в папке проекта:

```bash
cp .env.example .env
```

Откройте `.env` и заполните:

```
TRADINGVIEW_USERNAME=89165754941@protonmail.com
TRADINGVIEW_PASSWORD=KirCrypto123@
```

---

## Запуск

```bash
python main.py
```

Сервис выведет три таблицы:

```
BTC Цена (Binance BTCUSDT)
┌────────────────┬──────────────┬──────────────┬──────────────┐
│ Цена           │ % за 1 час   │ % за 4 часа  │ % за 24 часа │
├────────────────┼──────────────┼──────────────┼──────────────┤
│ $87,500.00     │ +0.45%       │ -1.20%       │ +2.15%       │
└────────────────┴──────────────┴──────────────┴──────────────┘

LuxAlgo — значения с графика TradingView (BTC)
...

BTC Опционы — Derive.xyz
...
```

---

## Важно про LuxAlgo

Сервис **заходит под вашим аккаунтом** в TradingView, открывает график `BINANCE:BTCUSDT` и читает значения LuxAlgo из легенды графика.

**Чтобы данные считывались:**
1. Войдите в TradingView вручную
2. Откройте график BTC (BINANCE:BTCUSDT или BTCUSDT)
3. Добавьте индикатор LuxAlgo на график
4. **Сохраните layout** (Ctrl+S)

Если LuxAlgo не будет найден на графике, в таблице отобразится `0` и пояснение.

---

## Если данные не собираются

| Проблема | Что появится в таблице | Решение |
|---|---|---|
| Binance недоступен | `0` во всех ценах | Проверить интернет / VPN |
| TradingView заблокировал бота | `0` в LuxAlgo | Запустить с другого IP |
| LuxAlgo не на графике | `0` + сообщение | Добавить и сохранить indikator |
| Derive.xyz недоступен | переключится на Deribit | Автоматически |
| Deribit тоже недоступен | `0` во всех опционах | Проверить интернет |

---

## Автозапуск (опционально)

Для запуска каждые N минут через cron (Linux/macOS):

```bash
crontab -e
```

Добавить строку (запуск каждые 30 минут, вывод в лог):

```
*/30 * * * * cd /path/to/brv && /path/to/venv/bin/python main.py >> /tmp/btc_dashboard.log 2>&1
```
