FROM docker.io/library/python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
    texlive-xetex texlive-lang-cyrillic texlive-pictures texlive-latex-extra fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src/ src/
COPY migrations/ migrations/
RUN pip install --no-cache-dir . && useradd --create-home prepa
RUN mkdir -p /app/output && chown prepa:prepa /app/output
USER prepa
CMD ["prepa-bot"]
