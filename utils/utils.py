from datetime import datetime
import openpyxl
import os
import sqlite3
import json
import time
import requests
import pandas as pd

def load_config(path="config.json"):
    with open(path, "r") as f:
        return json.load(f)

def fetch_initial_kline(symbol, interval, size=200, rest_code_map=None):
    if rest_code_map is None:
        raise ValueError("rest_code_map is required to convert timeframe")

    if interval not in rest_code_map:
        raise ValueError(f"Unknown interval '{interval}' for REST API")

    rest_interval = rest_code_map[interval]
    base_url = "https://api.lbank.info/v2/kline.do"
    print('INterval: ', interval)
    minutes = {
        "4h":int(4*60),
        "1h":int(1*60),
        "15min":int(15),
        "5min":int(5),
        "1min":int(1)
        }

    end_time = int(time.time())
    start_time = end_time - minutes[interval] * 60 * size # size * 60sec

    params = {
        "symbol": symbol,
        "size": size,
        "type": rest_interval,
        "time": str(start_time)
    }

    try:
        print(base_url, params)
        response = requests.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data["result"] is False or not data.get("data"):
            raise ValueError(f"No data returned for {symbol}-{interval}")
        df = pd.DataFrame(data["data"], columns=[
            "timestamp", "open", "high", "low", "close", "volume"
        ])
        df["timestamp"] = df["timestamp"].astype(int)
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df
    except Exception as e:
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
