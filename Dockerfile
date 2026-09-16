FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# libpq for psycopg. build-essential is only needed while installing, and is
# removed afterwards so it isn't part of the shipped image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

# Nothing here needs root, and a container escape costs less when the
# process doesn't own its own filesystem.
RUN useradd --create-home --uid 10001 petrolead && chown -R petrolead:petrolead /app
USER petrolead

EXPOSE 8000

# Managed platforms inject $PORT; 8000 is the default for a local `docker run`.
# With more than one worker, RUN_MIGRATIONS_ON_STARTUP must be false — run
# `alembic upgrade head` once per release instead (see docs/DEPLOY.md), or
# concurrent workers race to migrate the same database.
CMD ["sh", "-c", "gunicorn app.main:app \
  --worker-class uvicorn.workers.UvicornWorker \
  --workers ${WEB_CONCURRENCY:-2} \
  --bind 0.0.0.0:${PORT:-8000} \
  --timeout ${WEB_TIMEOUT:-120} \
  --access-logfile - --error-logfile -"]
