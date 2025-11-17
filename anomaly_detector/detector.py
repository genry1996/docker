import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Any, Optional

import pymysql

# ================== ЛОГИ ==================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# ================== НАСТРОЙКИ БАЗЫ ==================
MYSQL_HOST = os.getenv("MYSQL_HOST", "mysql_inforadar")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "root")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "ryban8991!")   # ← ТВОЙ ПАРОЛЬ
MYSQL_DB = os.getenv("MYSQL_DB", "inforadar")

# ================== НАСТРОЙКИ ОКОН И ПОРОГОВ ==================
WINDOW_MINUTES = int(os.getenv("ANOMALY_WINDOW_MINUTES", "30"))
WINDOW_SECONDS = WINDOW_MINUTES * 60

ODDS_JUMP_PCT = float(os.getenv("ODDS_JUMP_PCT", "15.0"))
ODDS_JUMP_ABS = float(os.getenv("ODDS_JUMP_ABS", "0.15"))

LIMIT_CUT_PCT = float(os.getenv("LIMIT_CUT_PCT", "40.0"))
LIMIT_CUT_ABS = float(os.getenv("LIMIT_CUT_ABS", "50.0"))

BOOKMAKER_OUTAGE_MINUTES = int(os.getenv("BOOKMAKER_OUTAGE_MINUTES", "20"))
SLEEP_SECONDS = int(os.getenv("ANOMALY_SLEEP_SECONDS", "60"))
SNAPSHOT_EPS_SECONDS = int(os.getenv("SNAPSHOT_EPS_SECONDS", "60"))


# ================== ПОДКЛЮЧЕНИЕ К БД ==================
def get_connection():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


# ================== ВСТАВКА АНОМАЛИИ ==================
def insert_anomaly(
    conn,
    match_id: int,
    bookmaker_id: Optional[int],
    anomaly_type: str,
    before_odd: Optional[float] = None,
    after_odd: Optional[float] = None,
    before_limit: Optional[float] = None,
    after_limit: Optional[float] = None,
    diff_pct: Optional[float] = None,
    comment: Optional[str] = None,
    window_seconds: int = WINDOW_SECONDS,
):
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
            comment
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                match_id,
                bookmaker_id,
                anomaly_type,
                before_odd,
                after_odd,
                before_limit,
                after_limit,
                diff_pct,
                window_seconds,
                comment,
            ),
        )
    logger.info(
        "⚠ anomaly: match=%s book=%s type=%s comment=%s",
        match_id, bookmaker_id, anomaly_type, comment
    )


# ================== ЗАГРУЗКА ДАННЫХ ИЗ odds_history ==================
def fetch_recent_odds(conn) -> List[Dict[str, Any]]:
    window_start = datetime.utcnow() - timedelta(minutes=WINDOW_MINUTES)

    sql = """
        SELECT
            match_id,
            bookmaker_id,
            market_type,
            line,
            odd,
            limit_value,
            captured_at
        FROM odds_history
        WHERE captured_at >= %s
    """

    with conn.cursor() as cur:
        cur.execute(sql, (window_start,))
        rows = cur.fetchall()

    logger.info("Загружено %s строк из odds_history", len(rows))
    return rows


# ================== ГРУППИРОВКИ ==================
def group_by_line(rows: List[Dict[str, Any]]):
    groups: Dict[Tuple[int, int, str, float], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (
            r["match_id"],
            r["bookmaker_id"],
            r["market_type"],
            float(r["line"]),
        )
        groups.setdefault(key, []).append(r)

    for key in groups:
        groups[key].sort(key=lambda x: x["captured_at"])

    return groups


def group_by_market(rows: List[Dict[str, Any]]):
    groups: Dict[Tuple[int, int, str], List[Dict[str, Any]]] = {}
    for r in rows:
        key = (
            r["match_id"],
            r["bookmaker_id"],
            r["market_type"],
        )
        groups.setdefault(key, []).append(r)

    for key in groups:
        groups[key].sort(key=lambda x: x["captured_at"])

    return groups


def group_by_bookmaker(rows: List[Dict[str, Any]]):
    groups: Dict[int, List[Dict[str, Any]]] = {}
    for r in rows:
        key = r["bookmaker_id"]
        groups.setdefault(key, []).append(r)

    for key in groups:
        groups[key].sort(key=lambda x: x["captured_at"])

    return groups


# ================== 1–2. ПАДЕНИЕ/РОСТ КОЭФФИЦИЕНТА ==================
def detect_odds_jumps(conn, rows: List[Dict[str, Any]]):
    groups = group_by_line(rows)

    for (match_id, bookmaker_id, market_type, line), g_rows in groups.items():
        first = g_rows[0]
        last = g_rows[-1]

        odd_before = float(first["odd"])
        odd_after = float(last["odd"])

        if odd_before <= 0:
            continue

        diff_abs = odd_after - odd_before
        diff_pct = diff_abs / odd_before * 100.0

        if diff_pct <= -ODDS_JUMP_PCT and abs(diff_abs) >= ODDS_JUMP_ABS:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "ODDS_DROP",
                before_odd=odd_before,
                after_odd=odd_after,
                diff_pct=diff_pct,
                comment=f"{market_type} {line}: {odd_before} → {odd_after} ({diff_pct:.1f}%)"
            )

        elif diff_pct >= ODDS_JUMP_PCT and abs(diff_abs) >= ODDS_JUMP_ABS:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "ODDS_RISE",
                before_odd=odd_before,
                after_odd=odd_after,
                diff_pct=diff_pct,
                comment=f"{market_type} {line}: {odd_before} → {odd_after} (+{diff_pct:.1f}%)"
            )


# ================== 3. ПОРЕЗКА ЛИМИТА ==================
def detect_limit_cuts(conn, rows: List[Dict[str, Any]]):
    groups = group_by_line(rows)

    for (match_id, bookmaker_id, market_type, line), g_rows in groups.items():
        first = g_rows[0]
        last = g_rows[-1]

        limit_before = float(first["limit_value"] or 0)
        limit_after = float(last["limit_value"] or 0)

        if limit_before <= 0:
            continue

        diff_abs = limit_after - limit_before
        diff_pct = diff_abs / limit_before * 100.0

        if diff_pct >= 0:
            continue

        if abs(diff_pct) >= LIMIT_CUT_PCT or abs(diff_abs) >= LIMIT_CUT_ABS:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "LIMIT_CUT",
                before_limit=limit_before,
                after_limit=limit_after,
                diff_pct=diff_pct,
                comment=f"{market_type} {line}: limit {limit_before} → {limit_after} ({diff_pct:.1f}%)"
            )


# ================== 6–8. ЛИНИИ: СУЖЕНИЕ / РАСШИРЕНИЕ / НОВЫЕ ==================
def detect_line_range_changes(conn, rows: List[Dict[str, Any]]):
    groups = group_by_market(rows)
    eps = timedelta(seconds=SNAPSHOT_EPS_SECONDS)

    for (match_id, bookmaker_id, market_type), g_rows in groups.items():
        first_ts = g_rows[0]["captured_at"]
        last_ts = g_rows[-1]["captured_at"]

        first_lines = {float(r["line"]) for r in g_rows if abs(r["captured_at"] - first_ts) <= eps}
        last_lines = {float(r["line"]) for r in g_rows if abs(r["captured_at"] - last_ts) <= eps}

        added = sorted(list(last_lines - first_lines))
        removed = sorted(list(first_lines - last_lines))

        if added:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "NEW_LINE",
                comment=f"{market_type}: added lines {added}"
            )

            # Расширение (если линия стала дальше, чем была)
            if first_lines:
                if max(added) > max(first_lines) or min(added) < min(first_lines):
                    insert_anomaly(
                        conn,
                        match_id,
                        bookmaker_id,
                        "LINE_EXPANSION",
                        comment=f"{market_type}: expansion {added}"
                    )

        if removed:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "LINE_NARROWING",
                comment=f"{market_type}: removed lines {removed}"
            )


# ================== 4–5. СНЯТИЕ РЫНКА / СНЯТИЕ МАТЧА ==================
def detect_market_and_match_removal(conn, rows: List[Dict[str, Any]]):
    eps = timedelta(seconds=SNAPSHOT_EPS_SECONDS)

    by_mb: Dict[Tuple[int, int], List[Dict[str, Any]]] = {}
    for r in rows:
        by_mb.setdefault((r["match_id"], r["bookmaker_id"]), []).append(r)

    for (match_id, bookmaker_id), g_rows in by_mb.items():
        g_rows.sort(key=lambda x: x["captured_at"])

        first_ts = g_rows[0]["captured_at"]
        last_ts = g_rows[-1]["captured_at"]

        first_m = {r["market_type"] for r in g_rows if abs(r["captured_at"] - first_ts) <= eps}
        last_m = {r["market_type"] for r in g_rows if abs(r["captured_at"] - last_ts) <= eps}

        removed = sorted(list(first_m - last_m))

        if removed:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "MARKET_REMOVED",
                comment=f"Removed markets: {removed}"
            )

        if first_m and not last_m:
            insert_anomaly(
                conn,
                match_id,
                bookmaker_id,
                "MATCH_REMOVED",
                comment=f"All markets removed for match"
            )


# ================== 9. ОТКЛЮЧЕНИЕ БУКМЕКЕРА ==================
def detect_bookmaker_outage(conn):
    outage_ts = datetime.utcnow() - timedelta(minutes=BOOKMAKER_OUTAGE_MINUTES)

    sql = """
        SELECT bookmaker_id, MAX(captured_at) AS last_ts
        FROM odds_history
        GROUP BY bookmaker_id
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    for r in rows:
        if r["last_ts"] and r["last_ts"] < outage_ts:
            insert_anomaly(
                conn,
                match_id=0,
                bookmaker_id=r["bookmaker_id"],
                anomaly_type="BOOKMAKER_OUTAGE",
                comment=f"No updates >{BOOKMAKER_OUTAGE_MINUTES} min"
            )


# ================== ОСНОВНОЙ ЦИКЛ ==================
def run_detector_once(conn):
    rows = fetch_recent_odds(conn)

    if not rows:
        logger.info("Нет данных в окне — пропуск.")
        return

    detect_odds_jumps(conn, rows)
    detect_limit_cuts(conn, rows)
    detect_line_range_changes(conn, rows)
    detect_market_and_match_removal(conn, rows)
    detect_bookmaker_outage(conn)


def main_loop():
    logger.info("🚀 Detector started")
    while True:
        try:
            conn = get_connection()
            run_detector_once(conn)
            conn.close()
        except Exception as e:
            logger.exception("Ошибка в детекторе: %s", e)

        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main_loop()
