FROM python:3.12-slim

WORKDIR /app
RUN pip install --no-cache-dir flask psycopg2-binary

COPY docmost_fetcher.py /app/docmost_fetcher.py

ENV LISTEN_HOST=0.0.0.0
ENV LISTEN_PORT=8099

CMD ["python", "/app/docmost_fetcher.py"]
