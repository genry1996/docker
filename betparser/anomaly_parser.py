import os
import time
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import pymysql
import requests

# ===========================
# ЛОГИ
# ===========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ===========================
# НАСТРОЙКИ БАЗЫ
# ===========================
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql_inforadar")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ryban8991!")
MYSQL_DB = os.getenv("MYSQL_DB", "inforadar")

# ===========================
# ПОРОГИ АНАЛИЗА
# ===========================
WINDOW_MINUTES = 30

ODDS_JUMP_PCT = 15.0
ODDS_JUMP_MIN_ABS = 0.30

ODDS_REDUCTION_PCT = 8.0     # порезка коэффициентов (ухудшение)
LIMIT_DROP_PCT = 40.0        # порезка лимитов
BLOCK_ODD_THRESHOLD = 1.02   # блокировка
BOOKMAKER_DIFF_PCT = 12.0    # разница между БК (Fortede Scanner)

# ===========================
# TELEGRAM (опционально)
# ===========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send_telegram(msg: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg},
            timeout=3
        )
    except:
        pass

# ===========================
# MySQL
# ===========================
def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        port=MYSQL_PORT,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )

# ===========================
# ЗАГРУЗКА odds_history
# ===========================
def fetch_history(conn):
    sql = f"""
        SELECT
            oh.id,
            oh.match_id,
            oh.bookmaker_id,
            oh.market,
            oh.outcome,
            oh.odd,
            oh.limit_value,
            oh.is_live,
            oh.created_at,
            m.sport,
            m.league,
            m.home_team,
            m.away_team,
            b.name AS bookmaker_name
        FROM odds_history oh
        JOIN matches m ON m.id = oh.match_id
        JOIN bookmakers b ON b.id = oh.bookmaker_id
        WHERE oh.created_at >= NOW() - INTERVAL %s MINUTE
        ORDER BY oh.match_id, oh.outcome, oh.bookmaker_id, oh.created_at;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (WINDOW_MINUTES,))
        return cur.fetchall()

# ===========================
# ГРУППИРОВКА ДАННЫХ
# ===========================
# ключ = (match_id, outcome, bookmaker_id)
Key = Tuple[int, str, int]

def group_history(rows):
    groups = {}
    latest_by_outcome = {}

    for row in rows:
        key: Key = (row["match_id"], row["outcome"], row["bookmaker_id"])

        if key not in groups:
            groups[key] = {"first": row, "last": row}
        else:
            if row["created_at"] < groups[key]["first"]["created_at"]:
                groups[key]["first"] = row
            if row["created_at"] > groups[key]["last"]["created_at"]:
                groups[key]["last"] = row

        # сбор последнего состояния по исходу (для сравнения между БК)
        o_key = (row["match_id"], row["outcome"])
        latest_by_outcome.setdefault(o_key, []).append(row)

    return groups, latest_by_outcome

# ===========================
# ПРОВЕРКА ДУБЛИРОВАНИЯ АНОМАЛИЙ
# ===========================
def anomaly_exists(
    conn,
    match_id: int,
    bookmaker_id: Optional[int],
    anomaly_type: str,
    comment: str,
    minutes: int = 60,
) -> bool:
    sql = """
        SELECT id FROM anomalies
        WHERE match_id = %s
          AND (bookmaker_id = %s OR (%s IS NULL AND bookmaker_id IS NULL))
          AND anomaly_type = %s
          AND comment = %s
          AND occurred_at >= NOW() - INTERVAL %s MINUTE
        LIMIT 1;
    """
    with conn.cursor() as cur:
        cur.execute(sql, (match_id, bookmaker_id, bookmaker_id,
                          anomaly_type, comment, minutes))
        return cur.fetchone() is not None

# ===========================
# ВСТАВКА АНОМАЛИИ
# ===========================
def insert_anomaly(
    conn,
    match_id: int,
    bookmaker_id: Optional[int],
    anomaly_type: str,
    before_odd: Optional[float],
    after_odd: Optional[float],
    before_limit: Optional[int],
    after_limit: Optional[int],
    diff_pct: Optional[float],
    window_seconds: Optional[int],
    is_live: int,
    comment: str
):
    if anomaly_exists(conn, match_id, bookmaker_id, anomaly_type, comment):
        return

    sql = """
        INSERT INTO anomalies (
            match_id,
            bookmaker_id,
            anomaly_type,
            before_odd,
            after_odd,
            before_limit,
            after_limit,
            diff_pct,
            window_seconds,
            is_live,
            comment,
            occurred_at
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW());
    """
    with conn.cursor() as cur:
        cur.execute(sql, (
            match_id,
            bookmaker_id,
            anomaly_type,
            before_odd,
            after_odd,
            before_limit,
            after_limit,
            diff_pct,
            window_seconds,
            is_live,
            comment
        ))
    conn.commit()

# ===========================
# АНАЛИЗ ВНУТРИ ОДНОЙ БК
# ===========================
def analyze_one_bookmaker(conn, groups):
    logger.info("🔎 Анализ внутри одной БК...")

    for key, grp in groups.items():
        match_id, outcome, bookmaker_id = key
        before = grp["first"]
        after = grp["last"]

        dt = (after["created_at"] - before["created_at"]).total_seconds()
        if dt <= 0:
            continue

        before_odd = float(before["odd"])
        after_odd = float(after["odd"])

        diff_pct = ((after_odd - before_odd) / before_odd * 100.0) if before_odd > 0 else None

        before_limit = before["limit_value"]
        after_limit = after["limit_value"]
        is_live = after["is_live"]

        # 🔴 Изменение коэффициента
        if diff_pct is not None and abs(diff_pct) >= ODDS_JUMP_PCT and abs(after_odd - before_odd) >= ODDS_JUMP_MIN_ABS:
            comment = f"изменение коэффициента: {before_odd} → {after_odd} ({diff_pct:+.1f}%)"
            insert_anomaly(
                conn, match_id, bookmaker_id, "odds_jump",
                before_odd, after_odd,
                before_limit, after_limit,
                diff_pct, int(dt), is_live, comment
            )

        # ⚫ Порезка коэффициентов
        if diff_pct is not None and diff_pct <= -ODDS_REDUCTION_PCT:
            comment = f"порезка коэффициента: {before_odd} → {after_odd} ({diff_pct:+.1f}%)"
            insert_anomaly(
                conn, match_id, bookmaker_id, "limit_odd_reduction",
                before_odd, after_odd,
                before_limit, after_limit,
                diff_pct, int(dt), is_live, comment
            )

        # 🟡 Порезка лимитов
        if before_limit and after_limit and after_limit < before_limit:
            lpct = (after_limit - before_limit) / before_limit * 100.0
            if lpct <= -LIMIT_DROP_PCT:
                comment = f"порезка лимита: {before_limit} → {after_limit} ({lpct:+.1f}%)"
                insert_anomaly(
                    conn, match_id, bookmaker_id, "limit_drop",
                    before_odd, after_odd,
                    before_limit, after_limit,
                    lpct, int(dt), is_live, comment
                )

        # ⚪ Блокировка ставки
        if after_odd <= BLOCK_ODD_THRESHOLD or (after_limit == 0):
            comment = f"блокировка ставки (odd={after_odd}, limit={after_limit})"
            insert_anomaly(
                conn, match_id, bookmaker_id, "limit_flag_on",
                before_odd, after_odd,
                before_limit, after_limit,
                diff_pct, int(dt), is_live, comment
            )

        # 🟤 Снятие матча (если после стало odd=0 или NULL)
        if after_odd == 0:
            comment = "матч снят с линии"
            insert_anomaly(
                conn, match_id, bookmaker_id, "match_removed",
                before_odd, after_odd,
                before_limit, after_limit,
                diff_pct, int(dt), is_live, comment
            )

# ===========================
# АНАЛИЗ МЕЖДУ БУКМЕКЕРАМИ (ForTede Style)
# ===========================
def analyze_between_books(conn, latest_by_outcome):
    logger.info("🔎 Анализ между букмекерами...")

    for (match_id, outcome), rows in latest_by_outcome.items():

        values = []
        for r in rows:
            try:
                v = float(r["odd"])
                if v > 1.01:
                    values.append({
                        "bookmaker_id": r["bookmaker_id"],
                        "bookmaker_name": r["bookmaker_name"],
                        "odd": v,
                        "is_live": r["is_live"]
                    })
            except:
                pass

        if len(values) < 2:
            continue

        values_sorted = sorted(values, key=lambda x: x["odd"])
        min_v = values_sorted[0]
        max_v = values_sorted[-1]

        diff_pct = (max_v["odd"] - min_v["odd"]) / min_v["odd"] * 100.0

        if diff_pct >= BOOKMAKER_DIFF_PCT:
            comment = (
                f"разница между БК: {min_v['bookmaker_name']}={min_v['odd']} "
                f"vs {max_v['bookmaker_name']}={max_v['odd']} ({diff_pct:.1f}%)"
            )
            insert_anomaly(
                conn,
                match_id,
                max_v["bookmaker_id"],
                "bookmaker_diff",
                min_v["odd"],
                max_v["odd"],
                None,
                None,
                diff_pct,
                None,
                max_v["is_live"],
                comment
            )

# ===========================
# MAIN
# ===========================
def main():
    logger.info("🚀 Запуск anomaly_parser v4 PRO...")

    try:
        conn = get_conn()
    except Exception as e:
        logger.error("❌ Ошибка подключения к MySQL: %s", e)
        return

    rows = fetch_history(conn)

    if not rows:
        logger.info("нет данных в odds_history — выход")
        return

    groups, latest = group_history(rows)

    analyze_one_bookmaker(conn, groups)
    analyze_between_books(conn, latest)

    logger.info("✅ Аномалии обработаны")

    try:
        conn.close()
    except:
        pass


if __name__ == "__main__":
    main()
