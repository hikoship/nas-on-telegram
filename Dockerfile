FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
WORKDIR /app/app

RUN chmod +x scripts/*.sh

CMD ["python", "main.py"]
