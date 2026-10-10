# Build stage
FROM python:3.12-slim-bookworm AS builder
WORKDIR /app
COPY src/ /app/src/

# Hardened minimal runtime stage
FROM gcr.io/distroless/python3-debian12:nonroot
WORKDIR /app
COPY --from=builder /app/src /app/src
ENV PYTHONUNBUFFERED=1 \
    PORT=8080

USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["python3", "/app/src/main.py"]
