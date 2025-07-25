from datetime import datetime
import openpyxl
import os
import sqlite3
import json
import time
import requests
import pandas as pd
import logging
from typing import Optional, Dict, Any
import urllib.parse

"""
utils/utils.py
--------------
Utility helpers. Includes a safe REST kline fetcher that never hard-crashes
when timeframe maps are missing.
"""

def fetch_initial_kline(
    symbol: str,
    interval: str,
    size: int = 200,
    rest_code_map: Optional[Dict[str, str]] = None,
    config: Optional[Dict[str, Any]] = None,
    logger: Optional[logging.Logger] = None,
) -> pd.DataFrame:
    """
    Fetch initial OHLCV rows from LBank REST API safely.

    - Resolves `rest_code_map` from argument, config, or environment.
    - Returns an empty DataFrame (with a warning) instead of raising.
    - Compatible with Python < 3.10 (uses Optional[...] not `|`).
    """
    # 1) Resolve map if not provided
    if rest_code_map is None:
        if config is not None:
            rest_code_map = (
                config.get("rest_code_map")
                or config.get("REST_TIMEFRAME_CODES")
                or {}
            )
        if not rest_code_map:
            # Last resort: build from env
            rest_code_map = {
                k.replace("REST_TIMEFRAME_CODES_", "").lower(): v
                for k, v in os.environ.items()
                if k.startswith("REST_TIMEFRAME_CODES_")
            }

    if not rest_code_map:
        if logger:
            logger.warning("No rest_code_map / REST_TIMEFRAME_CODES; returning empty DataFrame.")
        return pd.DataFrame()

    # If someone passed the REST code instead of canonical (minute1 instead of 1m), map back
    # after resolving rest_code_map

    if interval not in rest_code_map:
        reverse = {v: k for k, v in rest_code_map.items()}
        interval = reverse.get(interval, interval)

    if interval not in rest_code_map:
        if logger:
            logger.error("Unknown interval '%s' for REST API", interval)
        return pd.DataFrame()

    rest_interval = rest_code_map[interval]

    base_url = "https://api.lbank.info/v2/kline.do"
    minutes = {
        "1m": 1,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "4h": 240,
        "8h": 480,
        "12h": 720,
        "1d": 1440,
        "1w": 10080,
        "1mth": 43200,
    }

    end_time = int(time.time())
    start_time = end_time - minutes.get(interval, 1) * 60 * size

    params = {
        "symbol": symbol,
        "size": size,
        "type": rest_interval,
        "time": str(start_time),
    }

    # log complete REST URL
    full_url = f"{base_url}?symbol={symbol}&size={size}&type={rest_interval}&time={start_time}"
    if logger:
        logger.info("⏩ REST GET → %s", full_url)

    try:
        resp = requests.get(base_url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        if not data.get("result") or not data.get("data"):
            raise ValueError(f"No data returned for {symbol}-{interval}")

        df = pd.DataFrame(
            data["data"],
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        ).astype(
            {
                "timestamp": int,
                "open": float,
                "high": float,
                "low": float,
                "close": float,
                "volume": float,
            }
        )
        return df

    except Exception as e:
        if logger:
            logger.error("fetch_initial_kline failed for %s-%s: %s", symbol, interval, e)
        else:
            print(f"[ERROR] fetch_initial_kline failed for {symbol}-{interval}: {e}")
        return pd.DataFrame()


def log_signal(msg, file=None):
    """
    ثبت پیام در فایل log با فرمت log_YYYY_MM_DD.txt
    """
    if file is None:
        file = f"log_{datetime.utcnow().strftime('%Y_%m_%d')}.txt"
    with open(file, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def save_signal_to_excel(file_path, data):
    """
    ذخیره سیگنال در فایل اکسل
    data: dict with keys: symbol, interval, timestamp, price, signal
    """
    if os.path.exists(file_path):
        wb = openpyxl.load_workbook(file_path)
        ws = wb.active
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Symbol", "Interval", "Timestamp", "Price", "Signal"])

    ws.append([
        data.get("symbol"),
        data.get("interval"),
        data.get("timestamp"),
        data.get("price"),
        data.get("signal")
    ])
    wb.save(file_path)


def update_dashboard(html_path="dashboard.html", signal_data=None):
    """
    به‌روزرسانی داشبورد HTML با آخرین سیگنال‌ها از دیتابیس یا لیست
    signal_data: list of tuples like (id, symbol, interval, timestamp, price, signal)
    """
    html_template = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>📊 Crypto Signal Dashboard</title>
        <style>
            body { font-family: sans-serif; background: #111; color: #eee; padding: 20px; }
            h1 { color: #4fc3f7; }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border: 1px solid #555; padding: 8px; text-align: center; }
            th { background-color: #333; }
            tr:nth-child(even) { background-color: #1e1e1e; }
        </style>
    </head>
    <body>
        <h1>📈 Live Crypto Signals</h1>
        <table>
            <thead>
                <tr>
                    <th>#</th><th>Symbol</th><th>Interval</th><th>Time</th><th>Price</th><th>Signal</th>
                </tr>
            </thead>
            <tbody>
                {{SIGNALS}}
            </tbody>
        </table>
    </body>
    </html>
    """

    if not signal_data:
        try:
            conn = sqlite3.connect("signals.db")
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM signals ORDER BY timestamp DESC LIMIT 50")
            signal_data = cursor.fetchall()
            conn.close()
        except:
            signal_data = []

    html_signals = ""
    for row in signal_data[::-1]:  # latest last
        html_signals += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td><td>{row[3]}</td><td>{row[4]}</td><td>{row[5]}</td></tr>\n"

    final_html = html_template.replace("{{SIGNALS}}", html_signals)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(final_html)
