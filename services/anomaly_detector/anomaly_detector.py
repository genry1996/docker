import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

import pymysql
import requests

# ========= ЛОГИ ==========
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/anomaly_detector.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger("anomaly")

# ========= НАСТРОЙКИ БД =========
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql_inforadar")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ryban8991!")
MYSQL_DB = os.getenv("MYSQL_DB", "inforadar")

WINDOW_MINUTES = int(os.getenv("ANOMALY_WINDOW_MINUTES", "30"))

ODDS_JUMP_PCT = float(os.getenv("ODDS_JUMP_PCT", "15.0"))
ODDS_JUMP_ABS = float(os.getenv("ODDS_JUMP_ABS", "0.25"))

TG_TOKEN = os.getenv("TG_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")

def send_telegram_html(text: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            data={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=5
        )
    except Exception as e:
        logger.error(f"Ошибка Telegram: {e}")


def db():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def save_trend(cursor, match_id, bookmaker_id, market_type, line_value, outcome,
               old_value, new_value, change_pct):
    cursor.execute("""
        INSERT INTO odds_trends 
        (match_id, bookmaker, market_name, outcome_name, old_value, new_value, change_pct, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
    """, (match_id, bookmaker_id, market_type, outcome, old_value, new_value, change_pct))


def analyze_anomalies():
    logger.info("🚀 Старт анализа аномалий")

    connection = db()
    cursor = connection.cursor()

    time_limit = datetime.utcnow() - timedelta(minutes=WINDOW_MINUTES)

    # 🔥 ПРАВИЛЬНЫЙ SELECT под твою БД
    cursor.execute("""
        SELECT 
            o.value,
            o.outcome,
            o.market_id,
            m2.market_type,
            m2.line_value,
            m2.bookmaker_id,
            m.id AS match_id,
            m.sport,
            m.league,
            m.home_team,
            m.away_team,
            m.start_time,
            o.updated_at
        FROM odds o
        JOIN markets m2 ON m2.id = o.market_id
        JOIN matches m ON m.id = m2.match_id
        WHERE o.updated_at >= %s
        ORDER BY m.id, m2.bookmaker_id, m2.market_type, o.outcome, o.updated_at
    """, (time_limit,))

    rows = cursor.fetchall()
    logger.debug(f"Найдено строк: {len(rows)}")

    last_values: Dict[int, Dict[int, Dict[str, Dict[str, Any]]]] = {}

    for row in rows:
        match_id = row["match_id"]
        bookmaker_id = row["bookmaker_id"]
        market = row["market_type"]
        outcome = row["outcome"]
        value = float(row["value"])

        last_values.setdefault(match_id, {})
        last_values[match_id].setdefault(bookmaker_id, {})
        last_values[match_id][bookmaker_id].setdefault(market, {})
        last_values[match_id][bookmaker_id][market].setdefault(outcome, {"old": value, "new": value})

        last_values[match_id][bookmaker_id][market][outcome]["new"] = value

    anomalies_count = 0

    for match_id, bm_data in last_values.items():
        for bookmaker_id, markets in bm_data.items():
            for market, outs in markets.items():
                for outcome, data in outs.items():

                    old = data["old"]
                    new = data["new"]

                    if old == 0 or new == 0:
                        continue

                    change_abs = abs(new - old)
                    change_pct = ((new - old) / old) * 100

                    if change_abs >= ODDS_JUMP_ABS or abs(change_pct) >= ODDS_JUMP_PCT:

                        anomalies_count += 1

                        logger.warning(
                            f"АНОМАЛИЯ MATCH {match_id} | BM {bookmaker_id} | {market}:{outcome} {old} → {new}"
                        )

                        cursor.execute("""
                            INSERT INTO anomalies 
                            (match_id, bookmaker, market_name, outcome_name, 
                             old_value, new_value, change_pct, anomaly_type, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 'ODDS_JUMP', NOW())
                        """, (match_id, bookmaker_id, market, outcome, old, new, change_pct))

                        save_trend(cursor, match_id, bookmaker_id, market, None, outcome, old, new, change_pct)

                        send_telegram_html(
                            f"<b>⚠ Аномалия коэффициентов</b>\n"
                            f"<b>Матч #{match_id}</b>\n"
                            f"<b>БК:</b> {bookmaker_id}\n"
                            f"<b>Рынок:</b> {market}\n"
                            f"<b>Исход:</b> {outcome}\n"
                            f"<b>{old} → {new}</b> ({change_pct:.1f}%)"
                        )

    logger.info(f"Готово. Найдено аномалий: {anomalies_count}")


if __name__ == "__main__":
    while True:
        try:
            analyze_anomalies()
        except Exception as e:
            logger.error(f"Ошибка в анализе: {e}")
        time.sleep(15)
