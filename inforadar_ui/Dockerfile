# === БАЗОВЫЙ ОБРАЗ ===
FROM python:3.10-slim

# === УСТАНОВКА УТИЛИТ ===
RUN apt-get update && apt-get install -y \
    default-mysql-client \
    iputils-ping \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# === РАБОЧАЯ ДИРЕКТОРИЯ ===
WORKDIR /app

# === КОПИРУЕМ ЗАВИСИМОСТИ ===
COPY requirements.txt /app/requirements.txt

# === УСТАНАВЛИВАЕМ ЗАВИСИМОСТИ PYTHON ===
RUN pip install --no-cache-dir -r requirements.txt

# === КОПИРУЕМ ВСЁ ПРИЛОЖЕНИЕ ===
COPY . /app

# === ОТКРЫВАЕМ ПОРТ ===
EXPOSE 5000

# === КОМАНДА СТАРТА ===
CMD ["python", "app.py"]
