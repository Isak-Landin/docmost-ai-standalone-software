# Dockerfile (backend; gunicorn entrypoint placeholder)
# Assumes you will later create an app module with an ASGI/WSGI callable named "app".
# Example target later: "api.app:app" or "app:app"

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps (keep minimal; add build-essential only if you need wheels compiled)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
  && rm -rf /var/lib/apt/lists/*

# Install python deps
# Expect a requirements.txt to exist later; this Dockerfile won't build until you add it.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app source
COPY . /app

# Expose backend port (internal)
ARG BACKEND_INTERNAL_PORT=3005
EXPOSE ${BACKEND_INTERNAL_PORT}

# Gunicorn (placeholder target; update once app exists)
# If you later use "api/app.py" with FastAPI, you'd usually do: uvicorn api.app:app ...
# For Flask: gunicorn -w 2 -b 0.0.0.0:3005 "api.app:app"
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:3005", "app:app"]
