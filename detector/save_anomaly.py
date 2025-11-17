import json
import pymysql
from datetime import datetime
import uuid


# === Настройки подключения к MySQL ===
MYSQL_HOST = "mysql_inforadar"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "ryban8991!"
MYSQL_DB = "inforadar"


def get_connection():
    """Создаёт подключение к MySQL."""
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )


def save_anomaly(anomaly: dict):
    """
    Сохраняет JSON-аномалию в таблицу anomalies.
    Формат JSON должен соответствовать anomaly_schema.json
    """

    # --- Генерация anomaly_id, если нет ---
    if "anomaly_id" not in anomaly:
        anomaly["anomaly_id"] = str(uuid.uuid4())

    # --- Дата обнаружения, если нет ---
    if "detected_at" not in anomaly:
        anomaly["detected_at"] = datetime.utcnow().isoformat()

    # --- Минимальная проверка обязательных полей ---
    required = ["match_id", "bookmaker", "type"]

    for field in required:
        if field not in anomaly:
            raise ValueError(f"Missing required field: {field}")

    # --- Приведение игнорируемых значений ---
    severity = anomaly.get("severity", "MEDIUM")
    bookmaker_id = anomaly.get("bookmaker_id", 1)

    # --- Приведение JSON к строке ---
    details_json = json.dumps(anomaly, ensure_ascii=False)

    # --- SQL вставка ---
    sql = """
        INSERT INTO anomalies (match_id, bookmaker_id, type, severity, details)
        VALUES (%s, %s, %s, %s, CAST(%s AS JSON))
    """

    values = (
        anomaly["match_id"],
        bookmaker_id,
        anomaly["type"],
        severity,
        details_json
    )

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, values)
    finally:
        conn.close()

    print(f"[OK] Аномалия сохранена: {anomaly['anomaly_id']}")
