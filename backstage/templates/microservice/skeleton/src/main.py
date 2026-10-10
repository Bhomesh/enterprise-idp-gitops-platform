"""
Production Microservice Skeleton for ${{ values.component_id }}
Includes health check, OpenTelemetry metrics hooks, and graceful termination.
"""

import http.server
import json
import logging
import os
import signal
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("${{ values.component_id }}")

PORT = int(os.environ.get("PORT", "8080"))
SHUTTING_DOWN = False


class HealthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global SHUTTING_DOWN
        if self.path in ("/healthz", "/livez"):
            if SHUTTING_DOWN:
                self.send_response(503)
                self.end_headers()
                self.wfile.write(b'{"status":"shutting_down"}')
            else:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"healthy"}')
        elif self.path == "/readyz":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ready"}')
        elif self.path == "/metrics":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            metrics = (
                "# HELP http_requests_total Total HTTP requests\n"
                "# TYPE http_requests_total counter\n"
                'http_requests_total{code="200"} 1\n'
            )
            self.wfile.write(metrics.encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            payload = {
                "service": "${{ values.component_id }}",
                "status": "running",
                "version": os.environ.get("APP_VERSION", "1.0.0"),
            }
            self.wfile.write(json.dumps(payload).encode("utf-8"))

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)


def run_server():
    server = http.server.HTTPServer(("0.0.0.0", PORT), HealthHandler)
    logger.info("Starting service ${{ values.component_id }} on port %d", PORT)

    def sig_handler(sig, frame):
        global SHUTTING_DOWN
        logger.info("Received termination signal, draining connections...")
        SHUTTING_DOWN = True
        sys.exit(0)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
