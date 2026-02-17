FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir flask psycopg2-binary

COPY docmost_fetcher.py /app/docmost_fetcher.py
COPY ui /app/ui


ENV LISTEN_HOST=0.0.0.0
ENV LISTEN_PORT=8099
ENV UI_LISTEN_PORT=8090

CMD ["bash", "-lc", "python /app/docmost_fetcher.py & python /app/ui/app_ui.py & wait -n"]

