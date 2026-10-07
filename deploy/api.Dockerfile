FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.30" "psycopg[binary]>=3.2"
COPY engine/__init__.py engine/config.py engine/
COPY engine/live engine/live
COPY apps apps
ENV PYTHONUNBUFFERED=1
USER nobody
CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8787"]
