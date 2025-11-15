# database.py — синхронное подключение (правильно для anomaly_parser)
import pymysql

def get_db_connection():
    return pymysql.connect(
        host="mysql_inforadar",
        user="root",
        password="ryban8991!",
        database="inforadar",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True
    )
