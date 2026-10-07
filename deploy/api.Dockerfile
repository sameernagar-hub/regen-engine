FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.142" "uvicorn>=0.54" "pydantic>=2.13" "psycopg[binary]>=3.3"
COPY engine/__init__.py engine/config.py engine/
COPY engine/live engine/live
COPY engine/memory engine/memory
COPY apps apps
ENV PYTHONUNBUFFERED=1
USER nobody
CMD ["python", "-m", "uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8787"]
