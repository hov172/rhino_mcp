FROM python:3.13-slim

LABEL org.opencontainers.image.title="rhino-mcp" \
      org.opencontainers.image.version="0.13.0" \
      org.opencontainers.image.description="MCP server for Rhino 3D — 360 tools" \
      org.opencontainers.image.source="https://github.com/hov172/rhino_mcp"

# System libraries required by Python dependencies:
#   cairosvg  → libcairo2, libpango, libgdk-pixbuf2.0, shared-mime-info
#   pillow-heif → libheif1
#   pymupdf   → libmupdf (bundled wheel — no extra system dep needed)
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
COPY pyproject.toml uv.lock ./

# Install dependencies without the project itself (cache layer)
RUN uv sync --frozen --no-install-project

# Copy source and install the project (includes data/, report_templates/)
COPY src/ ./src/

RUN uv sync --frozen

# Connect to the Rhino plugin running on the Docker host
ENV RHINO_MCP_HOST=host.docker.internal
ENV RHINO_MCP_PORT=1999
ENV RHINO_MCP_BACKEND=auto

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# HTTP transport — multiple AI clients can connect simultaneously.
# Pass API keys at runtime:
#   docker run -e ANTHROPIC_API_KEY=... -e FAL_KEY=... -e DOCRAPTOR_API_KEY=... \
#              -p 8000:8000 rhino-mcp
CMD ["uv", "run", "python", "-m", "rhmcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
