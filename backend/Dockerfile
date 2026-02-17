FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask psycopg2-binary requests

COPY backend /app/backend

ENV PYTHONUNBUFFERED=1

CMD ["bash", "-lc", "python -m backend.worker.run_worker & python -m backend.app & wait -n"]
