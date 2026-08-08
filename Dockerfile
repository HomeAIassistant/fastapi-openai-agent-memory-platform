# ==============================================================================
# Hardened Agent Memory Platform runtime image.
#
# The base image is pinned to the multi-platform manifest digest resolved and
# recorded when this Dockerfile was authored. Update the tag and digest
# together through a reviewed pull request.
# ==============================================================================
FROM python:3.13-slim-bookworm@sha256:67a1e1f215ccda113cfc024e8639049257e88f273898f595b61476d128d387e8 AS runtime

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
