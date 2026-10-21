FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src

RUN useradd --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

ENTRYPOINT ["python", "-m", "m4b_tag_fixer"]
