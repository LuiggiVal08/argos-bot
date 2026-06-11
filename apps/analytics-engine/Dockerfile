FROM python:3.11-slim AS builder
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml requirements.txt* ./
RUN pip install --no-cache-dir --prefix /install .

FROM python:3.11-slim AS runner
WORKDIR /app
RUN addgroup --system argos && adduser --system --ingroup argos argos && \
    mkdir -p /var/lib/argos /app/data && chown -R argos:argos /var/lib/argos /app/data
COPY --from=builder /install/bin /usr/local/bin
COPY --from=builder /install/lib /usr/local/lib
COPY app/ app/
USER argos
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
