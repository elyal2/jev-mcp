# Multi-stage: build con uv, runtime mínimo. Solo necesario para el modo HTTP.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS build
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --no-dev --frozen

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app
COPY --from=build /app /app
ENV PATH="/app/.venv/bin:$PATH" \
    JEV_TRANSPORT=streamable-http \
    JEV_HTTP_HOST=0.0.0.0 \
    JEV_HTTP_PORT=8787
EXPOSE 8787
CMD ["jev-mcp"]
