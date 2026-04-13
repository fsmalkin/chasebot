FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY containers/telegram-runtime/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY telegram_wait_bridge ./telegram_wait_bridge

RUN useradd --create-home appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app

USER appuser

CMD ["python", "-m", "telegram_wait_bridge.wait_daemon"]
