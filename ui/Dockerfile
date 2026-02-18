FROM python:3.12-slim

WORKDIR /app

# UI server deps (adjust if you add more later)
RUN pip install --no-cache-dir flask requests

COPY app_ui.py /app/app_ui.py
COPY static /app/static

CMD ["python", "/app/app_ui.py"]
