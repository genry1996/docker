from flask import Flask, render_template, jsonify, request
import pymysql

app = Flask(__name__)

# === Настройки подключения к MySQL ===
DB_HOST = "mysql_inforadar"   # имя контейнера MySQL
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "ryban8991!"
DB_NAME = "inforadar"


def get_connection():
    """Создаёт подключение к базе данных MySQL"""
    try:
        conn = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            port=DB_PORT,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5,
        )
        return conn
    except Exception as e:
        # Это сообщение будет видно в docker logs inforadar_ui
        print(f"❌ Ошибка подключения к MySQL: {e}")
        return None


# === Главная страница ===
@app.route("/")
def index():
    conn = get_connection()
    if conn is None:
        return "<b>Ошибка подключения к MySQL</b>"
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM matches ORDER BY id DESC LIMIT 50;")
            matches = cursor.fetchall()
        conn.close()
        return render_template("index.html", matches=matches)
    except Exception as e:
        return f"<b>Ошибка при получении данных:</b> {e}"


# === API matches с фильтрами по спорту и лиге ===
@app.route("/api/anomalies")
def api_anomalies():
    minutes = int(request.args.get("minutes", 30))
    type_filter = request.args.get("type", "")
    bookmaker = request.args.get("bookmaker", "")
    min_diff = request.args.get("min_diff", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT 
            DATE_FORMAT(time, '%d.%m %H:%i') AS time,
            match,
            league,
            bookmaker,
            type,
            details,
            diff
        FROM anomalies
        WHERE time >= NOW() - INTERVAL %s MINUTE
    """
    params = [minutes]

    if type_filter:
        query += " AND type = %s"
        params.append(type_filter)

    if bookmaker:
        query += " AND bookmaker = %s"
        params.append(bookmaker)

    if min_diff:
        query += " AND diff >= %s"
        params.append(float(min_diff))

    query += " ORDER BY time DESC"

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # Приведение типа к красивому виду + цвета бейджей
    type_labels = {
        "odds_jump": ("Изменение коэффициента", "#fff3cd"),
        "limit_drop": ("Порезка лимита", "#ffe0e0"),
        "limit_odd_reduction": ("Порезка коэффициентов", "#d4edda"),
        "limit_flag_on": ("Блокировка ставки", "#e2e3ff"),
        "match_removed": ("Матч снят с линии", "#f8d7da"),
    }

    for row in rows:
        label, color = type_labels.get(row["type"], ("Другое", "#eeeeee"))
        row["type_label"] = label
        row["badge_color"] = color

    return jsonify(rows)


# === LIVE ===
@app.route("/live")
def live_page():
    return render_template("live.html")


# === MATCHES ===
@app.route("/matches")
def matches_page():
    return render_template("matches_tabs.html")


# === ESPORTS ===
@app.route("/esports")
def esports_page():
    return render_template("esports.html")


# === PREMATCH ===
@app.route("/prematch")
def prematch_page():
    conn = get_connection()
    if conn is None:
        return "<b>Ошибка подключения к MySQL</b>"

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM matches WHERE start_time > NOW() ORDER BY start_time ASC;"
            )
            matches = cursor.fetchall()
        conn.close()
        return render_template("prematch.html", matches=matches)
    except Exception as e:
        return f"<b>Ошибка при получении данных:</b> {e}"


# === Проверка API ===
@app.route("/api/test")
def api_test():
    return jsonify({"status": "ok", "message": "API OddlyOdds работает"})


# ============================================================
# ✅ HTML-страница /anomalies
# ============================================================
@app.route("/anomalies")
def anomalies_page():
    conn = get_connection()
    if conn is None:
        return "<b>Ошибка подключения к MySQL</b>"

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
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
                """
            )
            anomalies = cur.fetchall()
        conn.close()

        return render_template("anomalies.html", anomalies=anomalies)

    except Exception as e:
        return f"<b>Ошибка при получении данных:</b> {e}"


# ============================================================
# ✅ API /api/anomalies (для JS/фильтров)
# ============================================================
@app.route("/api/anomalies")
@app.route("/api/anomalies")
def anomalies_api():
    minutes = int(request.args.get("minutes", 30))
    type_filter = request.args.get("type", "")
    bookmaker = request.args.get("bookmaker", "")
    min_diff = request.args.get("min_diff", "").strip()

    conn = get_connection()
    if conn is None:
        return jsonify({"error": "MySQL connection failed"}), 500

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
                WHERE a.occurred_at >= NOW() - INTERVAL %s MINUTE
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
                except ValueError:
                    pass  # игнорируем кривой ввод, просто не фильтруем

            query += " ORDER BY a.occurred_at DESC"
            cur.execute(query, params)
            rows = cur.fetchall()

        conn.close()

        def map_type(t: str):
            # тип → (русское название, цвет бейджа)
            mapping = {
                "odds_jump":          ("Изменение коэффициента", "#ffdee6"),  # розовый
                "limit_drop":         ("Порезка лимита",          "#fff7c2"),  # жёлтый
                "limit_flag_on":      ("Блокировка ставки",       "#d9d9d9"),  # светло-серый
                "limit_odd_reduction":("Порезка коэффициентов",   "#e6e6e6"),  # тёмно-серый
                "match_removed":      ("Матч снят с линии",       "#d8b4a6"),  # коричнево-красный
            }
            return mapping.get(t, (t, "#eeeeee"))

        result = []
        for r in rows:
            type_code = r["anomaly_type"]
            type_label, badge_color = map_type(type_code)

            # базовые поля
            time_str = r["occurred_at"].strftime("%Y-%m-%d %H:%M:%S") if r["occurred_at"] else ""
            match_name = f"{r['home_team']} – {r['away_team']}"
            league = r["league"]
            book = r["bookmaker"] or ""

            # детальное описание
            before_odd = r["before_odd"]
            after_odd = r["after_odd"]
            before_limit = r["before_limit"]
            after_limit = r["after_limit"]
            diff_pct = r["diff_pct"]
            window_seconds = r["window_seconds"]
            comment = r["comment"] or ""

            details_parts = []

            # Изменение коэффициента / порезка коэффициентов
            if type_code in ("odds_jump", "limit_odd_reduction") and before_odd is not None and after_odd is not None:
                if diff_pct is not None:
                    details_parts.append(
                        f"{before_odd:.3f} → {after_odd:.3f} ({diff_pct:+.1f}%)"
                    )
                else:
                    details_parts.append(f"{before_odd:.3f} → {after_odd:.3f}")
                if window_seconds:
                    details_parts.append(f"за {window_seconds} сек")

            # Порезка лимита
            if type_code == "limit_drop" and before_limit is not None and after_limit is not None:
                if diff_pct is not None:
                    details_parts.append(
                        f"Лимит: {before_limit} → {after_limit} ({diff_pct:+.1f}%)"
                    )
                else:
                    details_parts.append(f"Лимит: {before_limit} → {after_limit}")

            # Блокировка
            if type_code == "limit_flag_on":
                details_parts.append("Ставка заблокирована букмекером")

            # Снятие матча
            if type_code == "match_removed":
                details_parts.append("Матч снят из линии букмекера")

            if comment:
                details_parts.append(comment)

            details = " | ".join(details_parts) if details_parts else ""

            result.append({
                "time": time_str,
                "match": match_name,
                "league": league,
                "bookmaker": book,
                "type_code": type_code,
                "type_label": type_label,
                "badge_color": badge_color,
                "details": details,
            })

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === Точка входа ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
