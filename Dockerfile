# Build a lightweight image to run the PDF formatter with a simple HTTP API
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

# System packages needed for OCR (pytesseract)
RUN apt-get update && \
    apt-get install -y --no-install-recommends tesseract-ocr libtesseract-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Serve the Flask app
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
