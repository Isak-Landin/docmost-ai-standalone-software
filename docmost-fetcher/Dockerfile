FROM python:3.12-slim

WORKDIR /app

# Minimal runtime deps for fetcher
RUN pip install --no-cache-dir flask psycopg2-binary

COPY docmost_fetcher.py /app/docmost_fetcher.py
COPY ./api/* /app/

# docmost-fetcher is the only process in this container
CMD ["python", "/app/docmost_fetcher.py"]
