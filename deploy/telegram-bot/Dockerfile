FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --chmod=0444 bot.py /app/bot.py
USER 65534:65534
CMD ["python", "/app/bot.py"]
