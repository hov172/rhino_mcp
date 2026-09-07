FROM python:3.13-slim

LABEL org.opencontainers.image.title="rhino-mcp" \
      org.opencontainers.image.version="0.18.0" \
      org.opencontainers.image.description="MCP server for Rhino 3D — 358 tools" \
      org.opencontainers.image.source="https://github.com/hov172/rhino_mcp"

# System libraries required by Python dependencies:
#   cairosvg  → libcairo2, libpango, libgdk-pixbuf2.0, shared-mime-info
#   pillow-heif → libheif1
#   pypdfium2 → bundled PDFium renderer (PDF parsing runs in isolated workers)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-xlib-2.0-0 \
        libffi8 \
        shared-mime-info \
        libheif1 \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first — layer cached until pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock README.md LICENSE THIRD_PARTY_NOTICES.md ./

# Install dependencies without the project itself (cache layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source and install the project (includes data/, report_templates/)
COPY src/ ./src/
COPY grasshopper/ ./grasshopper/

RUN uv sync --frozen --no-dev
COPY scripts/dependency-inventory.py /app/scripts/dependency-inventory.py
RUN /app/.venv/bin/python /app/scripts/dependency-inventory.py /app/third-party
COPY scripts/pdf-smoke.py /app/scripts/pdf-smoke.py
COPY tests/fixtures/pdf/smoke.pdf /app/pdf-smoke.pdf
RUN /app/.venv/bin/python /app/scripts/pdf-smoke.py /app/pdf-smoke.pdf

# Connect to the Rhino plugin running on the Docker host
ENV RHINO_MCP_HOST=host.docker.internal
ENV RHINO_MCP_PORT=1999
ENV RHINO_MCP_BACKEND=auto
ENV RHINO_MCP_ALLOW_REMOTE=1
ENV RHINO_MCP_PLUGIN_TLS=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD uv run python -m rhmcp.tools_helpers.healthcheck || exit 1

# HTTP transport — multiple AI clients can connect simultaneously.
# Mount certificates and set HTTP/plugin TLS variables per docs/secure-operation.md.
# Pass API keys at runtime:
#   docker run -e ANTHROPIC_API_KEY=... -e FAL_KEY=... -e DOCRAPTOR_API_KEY=... \
#              -p 8000:8000 rhino-mcp
CMD ["uv", "run", "python", "-m", "rhmcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
