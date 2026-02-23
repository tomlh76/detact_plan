FROM python:3.11-slim

# System deps for OpenCV + Tesseract (French) + PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    libglib2.0-0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /srv/requirements.txt

COPY detect_plan.py /srv/detect_plan.py
COPY app /srv/app

ENV PYTHONUNBUFFERED=1 \
    PORT=8000

EXPOSE 8000

# Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
