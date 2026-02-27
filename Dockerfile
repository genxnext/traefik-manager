FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install uv using pip (no curl needed)
RUN pip install --no-cache-dir uv

# Copy dependency files first (better caching)
COPY pyproject.toml uv.lock* ./
# Install dependencies
RUN uv sync --frozen

COPY . .

EXPOSE 8090

CMD ["uv", "run", "gunicorn", "--bind", "0.0.0.0:8090", "--workers", "2", "--threads", "4", "--timeout", "60", "webui:app"]
