# SettleSense backend service image.
# Context: repository root (see docker-compose.yml) so requirements + code
# copy in explicit layers. Runtime stays Python 3.12 per TECHNICAL_DESIGN.md.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SETTLESENSE_ENV=docker

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY scripts ./scripts
# Runtime fixture inputs only: ground_truth.csv is evaluation data and stays
# OUT of the service image (review L3); benchmarks run from the repo/CI.
COPY data/internal_ledger.csv data/settlements.csv data/bank_statement.csv data/manifest.json ./data/

# Non-root runtime user; no secrets baked into the image.
RUN useradd --create-home settlesense && chown -R settlesense /app
USER settlesense

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
