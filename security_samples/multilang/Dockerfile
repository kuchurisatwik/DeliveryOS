# INTENTIONALLY INSECURE — Dockerfile fixture (Checkov + Trivy misconfig).
FROM ubuntu:latest

# Checkov CKV_DOCKER_3: no USER (runs as root)
# Checkov CKV_DOCKER_2: no HEALTHCHECK
RUN apt-get update && apt-get install -y curl

# Insecure: hardcoded token baked into the image
ENV APP_TOKEN="bake-token-into-image-bad-idea"

# Insecure: curl | sh remote code execution during build
RUN curl http://example.com/setup.sh | sh

EXPOSE 22
CMD ["/bin/sh"]

