FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ /app/app/
COPY migrations/ /app/migrations/

CMD ["sh", "-c", "uvicorn app.main:app --host ${LISTEN_HOST:-0.0.0.0} --port ${LISTEN_PORT:-8099}"]
