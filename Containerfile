FROM docker.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY migrations/ migrations/
RUN pip install --no-cache-dir . && useradd --create-home prepa
USER prepa
CMD ["prepa-bot"]
