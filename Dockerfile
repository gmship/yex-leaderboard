FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 10001 yexboard \
    && useradd --uid 10001 --gid yexboard --no-create-home --shell /usr/sbin/nologin yexboard

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=yexboard:yexboard . .
RUN mkdir -p /data && chown yexboard:yexboard /data

USER yexboard

EXPOSE 8000

CMD ["gunicorn", "--workers", "2", "--threads", "2", "--timeout", "30", "--bind", "0.0.0.0:8000", "app:app"]
