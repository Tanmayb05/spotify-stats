# Spotify Insights API
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build context is the repo root, so the committed fixture can be baked in.

# Dependencies first so edits to source do not invalidate the install layer.
COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
COPY apps/api/db ./db
COPY apps/api/migrations ./migrations
COPY apps/api/scripts ./scripts

# The synthetic fixture is committed and tiny, so bake it in: the stack must be
# able to seed itself without depending on a bind mount working. Compose still
# mounts the host ./data over this when you have a real export.
COPY data/fixtures ./data/fixtures

# Run as a non-root user.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser /app
USER appuser

EXPOSE 3011

# Compose overrides this to run migrations and seeding first.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3011"]
