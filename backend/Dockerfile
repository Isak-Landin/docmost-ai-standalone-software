FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir flask psycopg2-binary requests

COPY . /app/backend

# Run the backend HTTP server. Worker can be separate later if you split it.
CMD ["python", "-m", "backend.app"]
