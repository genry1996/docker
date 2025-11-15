import time, pymysql, os

host = os.getenv("MYSQL_HOST", "mysql_inforadar")
user = os.getenv("MYSQL_USER", "root")
password = os.getenv("MYSQL_PASSWORD", "ryban8991!")
database = os.getenv("MYSQL_DB", "inforadar")

for i in range(60):
    try:
        conn = pymysql.connect(host=host, user=user, password=password, database=database)
        print("✅ MySQL готов, запускаем парсер")
        conn.close()
        break
    except Exception as e:
        print("⏳ Ожидание MySQL...", e)
        time.sleep(5)
else:
    print("❌ Не удалось подключиться к MySQL после 5 минут ожидания")
    exit(1)
