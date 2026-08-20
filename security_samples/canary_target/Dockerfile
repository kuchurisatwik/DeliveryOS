# syntax=docker/dockerfile:1
#
# Deliberately-vulnerable staging target for DAST pipeline validation.
# NOT production code — never deploy this anywhere reachable.
#
# It publishes no OpenAPI spec of its own (so ZAP must be seeded from the spec our
# endpoint engine synthesises from app.py) and exposes /canary/xss so ZAP's canary
# trust gate can pass.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

EXPOSE 5000

# Flask's dev server is fine here: this is a throwaway test target, not production.
CMD ["python", "app.py"]
