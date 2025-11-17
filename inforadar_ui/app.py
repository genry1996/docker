from flask import Flask, render_template, jsonify, request
import pymysql

app = Flask(__name__)

# === Настройки подключения к MySQL ===
DB_HOST = "mysql_inforadar"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "ryban8991!"
DB_NAME = "inforadar"


# === Подключение к БД ===
def get_connection():
    try:
        return pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True
        )
    except Exception as e:
        print("❌ Ошибка подключения:", e)
        return None


# === Главная ===
@app.route("/")
def index():
    conn = get_connection()
    if not conn:
        return "Ошибка подключения к MySQL"

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM matches ORDER BY id DESC LIMIT 50;")
            matches = cur.fetchall()
        return render_template("index.html", matches=matches)
    except Exception as e:
        return f"Ошибка: {e}"


# === HTML /anomalies ===
@app.route("/anomalies")
def anomalies_page():
    conn = get_connection()
    if not conn:
        return "Ошибка подключения MySQL"

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    a.id,
                    a.anomaly_type,
                    a.before_odd,
                    a.after_odd,
                    a.before_limit,
                    a.after_limit,
                    a.diff_pct,
                    a.window_seconds,
                    a.comment,
                    a.occurred_at,
                    m.sport,
                    m.league,
                    m.home_team,
                    m.away_team,
                    b.name AS bookmaker
                FROM anomalies a
                JOIN matches m ON m.id = a.match_id
                LEFT JOIN bookmakers b ON b.id = a.bookmaker_id
                ORDER BY a.occurred_at DESC
                LIMIT 300
            """)
            anomalies = cur.fetchall()

        return render_template("anomalies.html", anomalies=anomalies)

    except Exception as e:
        return f"Ошибка: {e}"


# === API /api/anomalies (совместимо с JS) ===
@app.route("/api/anomalies")
def anomalies_api():
    minutes = int(request.args.get("minutes", 30))
    type_filter = request.args.get("type", "")
    bookmaker = request.args.get("bookmaker", "")
    min_diff = request.args.get("min_diff", "").strip()

    conn = get_connection()
    if not conn:
        return jsonify({"error": "connection_failed"}), 500

    try:
        with conn.cursor() as cur:
            query = """
                SELECT 
                    a.id,
                    a.occurred_at,
                    a.anomaly_type,
                    a.before_odd,
                    a.after_odd,
                    a.before_limit,
                    a.after_limit,
                    a.diff_pct,
                    a.window_seconds,
                    a.comment,
                    m.home_team,
                    m.away_team,
                    m.league,
                    b.name AS bookmaker
                FROM anomalies a
                JOIN matches m ON m.id = a.match_id
                LEFT JOIN bookmakers b ON b.id = a.bookmaker_id
                WHERE occurred_at >= (UTC_TIMESTAMP() + INTERVAL 3 HOUR) - INTERVAL %s MINUTE
            """
            params = [minutes]

            if type_filter:
                query += " AND a.anomaly_type = %s"
                params.append(type_filter)

            if bookmaker:
                query += " AND b.name = %s"
                params.append(bookmaker)

            if min_diff:
                try:
                    md = float(min_diff)
                    query += " AND a.diff_pct IS NOT NULL AND ABS(a.diff_pct) >= %s"
                    params.append(md)
                except:
                    pass

            query += " ORDER BY a.occurred_at DESC"
            cur.execute(query, params)
            rows = cur.fetchall()

        # === Маппинг типов ===
        def map_type(t):
            mapping = {
                "odds_jump": ("Изменение коэффициента", "#ffdee6"),
                "limit_drop": ("Порезка лимита", "#fff7c2"),
                "limit_flag_on": ("Блокировка ставки", "#d9d9d9"),
                "limit_odd_reduction": ("Порезка коэффициентов", "#e6e6e6"),
                "match_removed": ("Матч снят", "#d8b4a6"),
            }
            return mapping.get(t, (t, "#eeeeee"))

        # === Формирование ответа ===
        result = []
        for r in rows:
            type_label, badge_color = map_type(r["anomaly_type"])

            details_parts = []

            if r["before_odd"] is not None and r["after_odd"] is not None:
                details_parts.append(
                    f"{r['before_odd']:.3f} → {r['after_odd']:.3f} ({r['diff_pct']:+.1f}%)"
                )

            if r["before_limit"] is not None and r["after_limit"] is not None:
                details_parts.append(
                    f"Лимит {r['before_limit']} → {r['after_limit']}"
                )

            if r["comment"]:
                details_parts.append(r["comment"])

            result.append({
                "time": r["occurred_at"].strftime("%Y-%m-%d %H:%M:%S"),
                "match": f"{r['home_team']} – {r['away_team']}",
                "league": r["league"],
                "bookmaker": r["bookmaker"] or "",
                "type_label": type_label,
                "badge_color": badge_color,
                "details": " | ".join(details_parts)
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# === Точка входа ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
