# ==============================================================================
# Hardened Agent Memory Platform runtime image.
#
# The base image is pinned to the multi-platform manifest digest resolved and
# recorded when this Dockerfile was authored. Update the tag and digest
# together through a reviewed pull request.
# ==============================================================================
FROM python:3.14-slim-bookworm@sha256:23c59390fc717bf09f9336908199a0ae75d9c4264bf296123f94ad772fea3b52 AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

RUN groupadd --gid 10001 memory \
    && useradd --uid 10001 --gid memory --create-home --shell /usr/sbin/nologin memory

COPY requirements.txt ./
RUN python -m pip install --no-compile --requirement requirements.txt

COPY --chown=memory:memory app ./app
COPY --chown=memory:memory tests ./tests
COPY --chown=memory:memory pyproject.toml ./pyproject.toml

USER memory
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
