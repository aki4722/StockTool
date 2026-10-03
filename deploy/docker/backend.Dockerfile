# Python 3.9 matches the MacBook runtime the backend was developed on.
FROM python:3.9-slim

ENV TZ=Asia/Tokyo \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend

COPY backend/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*

COPY backend/backend/ .

EXPOSE 5001
# gunicorn instead of the Flask dev server: no Werkzeug debugger in production.
CMD ["gunicorn", "--bind", "0.0.0.0:5001", "--workers", "2", "--timeout", "120", \
     "--access-logfile", "-", "app:app"]
