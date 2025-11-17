FROM python:3.10

WORKDIR /app

COPY detector.py /app/detector.py
COPY requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "detector.py"]
