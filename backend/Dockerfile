FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
RUN useradd -m -u 10001 app
COPY --chown=app:app . .
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

