FROM python:3.10-slim

WORKDIR /app

# Установка зависимостей системы
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gcc \
        libssl-dev \
        libffi-dev \
        && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY betparser/requirements.txt /app/requirements.txt

# Устанавливаем зависимости Python
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем всё приложение
COPY betparser/ /app/

CMD ["python", "-u", "/app/anomaly_parser.py"]
