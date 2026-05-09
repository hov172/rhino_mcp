FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Copy dependency files first — layer cached until pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock ./

# Install dependencies without the project itself (cache layer)
RUN uv sync --frozen --no-install-project

# Copy source and install the project
COPY src/ ./src/
RUN uv sync --frozen

# Default: connect to Rhino plugin running on the Docker host
ENV RHINO_MCP_HOST=host.docker.internal
ENV RHINO_MCP_PORT=1999

EXPOSE 8000

# HTTP transport so multiple AI clients can connect simultaneously.
# Pass API keys at runtime: docker run -e ANTHROPIC_API_KEY=... -e FAL_KEY=...
CMD ["uv", "run", "python", "-m", "rhmcp", "--transport", "http", "--host", "0.0.0.0", "--port", "8000"]
