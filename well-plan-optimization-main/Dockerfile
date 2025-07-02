ARG version=3.12

FROM ghcr.io/astral-sh/uv:python$version-bookworm-slim AS builder


ENV UV_PYTHON="python$version" \
  UV_PYTHON_DOWNLOADS=never \
  UV_PROJECT_ENVIRONMENT=/app \
  UV_LINK_MODE=copy \
  UV_COMPILE_BYTECODE=1 \
  PYTHONOPTIMIZE=1


RUN --mount=type=cache,target=/root/.cache \
  --mount=type=bind,source=uv.lock,target=uv.lock \
  --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
  uv sync \
      --frozen \
      --no-dev \
      --no-install-project \
      --all-extras

COPY /src /app/src
COPY ./pyproject.toml ./uv.lock  /app/
WORKDIR /app
RUN --mount=type=cache,target=/root/.cache \
    uv sync \
        --frozen \
        --no-dev \
        --no-editable \
        --all-extras


FROM python:$version-slim-bookworm

COPY --from=builder --chown=app:app /app /app

ENV PATH=/app/bin:$PATH

WORKDIR /app

RUN <<EOT
python -V
python -Im site
python -Ic 'import wellplan'
EOT

CMD ["streamlit", "run", "src/wellplan/dashboard.py", "--server.port", "8080"]






