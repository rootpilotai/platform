#!/usr/bin/env bash
set -euo pipefail

DEMO_DIR="${1:-$(cd "$(dirname "$0")/../../opentelemetry-demo" && pwd)}"
ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"

# 1. Clone the OTEL demo repo if not present
if [ ! -d "$DEMO_DIR" ]; then
  echo "Cloning OpenTelemetry Demo..."
  git clone --depth 1 https://github.com/open-telemetry/opentelemetry-demo.git "$DEMO_DIR"
  git -C "$DEMO_DIR" fetch --depth 1 origin refs/tags/2.2.0:refs/tags/2.2.0
  git -C "$DEMO_DIR" checkout 2.2.0
  echo "Cloned to: $DEMO_DIR"
fi

# 2. Copy extras config to add otlphttp/rootpilot exporter
cp "$ROOT_DIR/infrastructure/monitoring/otel/demo-export.yml" \
   "$DEMO_DIR/src/otel-collector/otelcol-config-extras.yml"
echo "Copied extras config"

# 3. Create docker-compose override to join rootpilot-net
cat > "$DEMO_DIR/compose.rootpilot.yaml" << 'OVERRIDE'
# Connects the OTEL Demo to RootPilot's network and collector.
# Avoids host port conflicts with RootPilot's own collector by not exposing
# OTLP ports on the host (internal container communication is unaffected).

services:
  otel-collector:
    networks:
      - rootpilot-net
    ports: []

networks:
  rootpilot-net:
    external: true
OVERRIDE
echo "Created network override"

echo ""
echo "Setup complete. Run:"
echo "  docker compose -f compose.yaml -f compose.rootpilot.yaml up -d"
echo "  (from $DEMO_DIR)"
