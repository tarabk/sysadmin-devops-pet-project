FROM python:3.11-slim
WORKDIR /app
COPY requirements.lock.txt .
RUN python -m pip install -r requirements.lock.txt
RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin taskboard
COPY ./app /app/app
COPY alembic.ini .
COPY migrations/ /app/migrations/
USER taskboard
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]

