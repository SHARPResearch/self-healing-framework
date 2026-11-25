# ml-backend image: the CADAL lifecycle and the anomaly detector, serving live telemetry.
#
# Build from the repository root, because the backend runs ml-pipeline's code from source
# (app/core/pipeline_path.py) and applies infrastructure/local/init.sql on startup:
#   docker build -f services/ml-backend/Dockerfile -t sharp/ml-backend:dev .
# The image keeps the monorepo layout under /srv/sharp so those relative paths still resolve.
# Services/ml-backend/Dockerfile.dockerignore keeps the context small (no venvs, data, outputs).

FROM ghcr.io/astral-sh/uv:0.11.24 AS uv

FROM python:3.11-slim-bookworm
COPY --from=uv /uv /bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /srv/sharp/services/ml-backend

# Dependencies first, so code changes do not reinstall them.
COPY services/ml-backend/pyproject.toml services/ml-backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY ml-pipeline/src /srv/sharp/ml-pipeline/src
COPY datasets/smd/preprocess.py /srv/sharp/datasets/smd/preprocess.py
COPY infrastructure/local/init.sql /srv/sharp/infrastructure/local/init.sql
COPY services/ml-backend/app ./app
COPY services/ml-backend/scripts ./scripts

# In a cluster the backend scores live Prometheus telemetry; the SMD replay is a laptop demo.
# There is no Docker socket in a pod, so the container-log follower is off.
ENV PATH=/srv/sharp/services/ml-backend/.venv/bin:$PATH \
    TELEMETRY_MODE=prometheus \
    FOLLOW_CONTAINER_LOGS=false

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sharp
USER 10001

EXPOSE 8002
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
