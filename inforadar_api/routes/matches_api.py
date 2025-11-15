from flask import Blueprint, jsonify, request
from database import get_db_connection

matches_api = Blueprint("matches_api", __name__)

@matches_api.route("/api/matches")
def get_matches():
    """
    Возвращает список матчей с коэффициентами, статусами и фильтрацией.
    Поддерживаются параметры:
      - min_block: минимальный процент блокировок
      - min_limit: минимальный процент лимитов
      - anomalies: true/false — только аномальные падения
    Пример запроса:
      /api/matches?min_block=20&min_limit=10&anomalies=true
    """
    # Получаем параметры фильтра из запроса
    min_block = request.args.get("min_block", type=float)
    min_limit = request.args.get("min_limit", type=float)
    only_anomalies = request.args.get("anomalies", default=False, type=lambda v: v.lower() == "true")

    # Формируем базовый SQL-запрос
    query = """
        SELECT
            id,
            sport,
            league,
            home_team,
            away_team,
            score_home,
            score_away,
            start_time,
            odds_home,
            odds_away,
            status,
            blocked_percent,
            limited_percent,
            anomaly_flag
        FROM matches
        WHERE 1=1
    """

    # Добавляем фильтры, если указаны
    if min_block is not None:
        query += f" AND blocked_percent >= {min_block}"
    if min_limit is not None:
        query += f" AND limited_percent >= {min_limit}"
    if only_anomalies:
        query += " AND anomaly_flag = TRUE"

    query += " ORDER BY start_time DESC LIMIT 100;"

    # Подключаемся к базе и выполняем запрос
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(query)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    return jsonify(rows)
