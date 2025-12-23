# Build a lightweight image that can run the Cloud Function locally or in Cloud Run
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

# Expose the port Cloud Run/Functions expect
EXPOSE 8080

# Launch the function using the Functions Framework
CMD ["functions-framework", "--target", "main", "--port", "8080"]
