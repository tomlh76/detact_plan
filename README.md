# Detect Plan Fabrication au sein d'un fichier PDF – Webservice (FastAPI)

## Endpoint
- `POST /detect_plan_fab`  
  Receives a PDF as **multipart/form-data** (field name: `pdf`) and returns JSON.

- `GET /health`

## Run locally (without Docker)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Test:
```bash
curl -s -X POST "http://localhost:8000/detect_plan_fab" \
  -F "pdf=@plan5.pdf" | jq .
```

## Fonctionne avec Docker
```bash
docker build -t detect-plan-fab:latest .
docker run --rm -p 8000:8000 detect-plan-fab:latest
```

## Deploy behind https://0.0.0.0/detect_plan_fab
You usually keep the container on an internal port (e.g. 8000) and configure your reverse proxy (Nginx/Traefik/Apache)
to forward **only** `/detect_plan_fab` to `http://127.0.0.1:8000/detect_plan_fab`.

### Nginx example
```nginx
location /detect_plan_fab {
    proxy_pass http://127.0.0.1:8000/detect_plan_fab;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    client_max_body_size 40m;
}
location /health {
    proxy_pass http://127.0.0.1:8000/health;
}
```

Then you can call:
```bash
curl -s -X POST "https://backpresto.fr/detect_plan_fab" -F "pdf=@plan5.pdf"
```

## Notes
- Tesseract is installed in the image with the French language pack (`tesseract-ocr-fra`).
- Tune scoring via env vars: `TOP_K`, `MIN_SCORE`, `MAX_PDF_MB`.
