#!/usr/bin/env bash
set -euo pipefail

# Simple local two-container e2e using Podman
# Requirements: podman, network 'mcpnet' (created if missing)
# Note: Prefers a locally built RHIVOS PerfScale MCP image to ensure current changes are used.

NETWORK_NAME=${NETWORK_NAME:-mcpnet}
# Prefer locally built image unless DOMAIN_IMAGE is explicitly provided
DOMAIN_IMAGE=${DOMAIN_IMAGE:-}
HORREUM_IMAGE=${HORREUM_IMAGE:-quay.io/redhat-performance/horreum-mcp:main}
DOMAIN_NAME=${DOMAIN_NAME:-rhivos-perfscale-mcp}
HORREUM_NAME=${HORREUM_NAME:-horreum-mcp}
DOMAIN_PORT=${DOMAIN_PORT:-8080}
TOKEN=${DOMAIN_MCP_HTTP_TOKEN:-test-token}
HORREUM_BASE_URL=${HORREUM_BASE_URL:-}
HORREUM_TOKEN=${HORREUM_TOKEN:-}

WORKDIR=$(pwd)
TMPDIR=${TMPDIR:-/tmp}
CFG_PATH="${TMPDIR}/domain-mcp-server-config.json"

# Health wait configuration (overridable)
DOMAIN_HEALTH_TRIES=${DOMAIN_HEALTH_TRIES:-30}
DOMAIN_HEALTH_SLEEP=${DOMAIN_HEALTH_SLEEP:-1}
HORREUM_HEALTH_TRIES=${HORREUM_HEALTH_TRIES:-60}
HORREUM_HEALTH_SLEEP=${HORREUM_HEALTH_SLEEP:-1}

# Helper: wait for a health endpoint
health_wait() {
  local url="$1"
  local tries="${2:-30}"
  local pause="${3:-1}"
  for i in $(seq 1 "${tries}"); do
    if curl -4fsS "${url}" >/dev/null; then
      return 0
    fi
    sleep "${pause}"
  done
  return 1
}

# Cleanup containers and temp config on exit (unless KEEP_CONTAINERS=1)
cleanup() {
  podman stop "${DOMAIN_NAME}" "${HORREUM_NAME}" >/dev/null 2>&1 || true
}
if [[ "${KEEP_CONTAINERS:-0}" != "1" ]]; then
  trap cleanup EXIT
fi

# Resolve RHIVOS PerfScale MCP image: use provided, else local :local tag if present, else build
if [[ -z "${DOMAIN_IMAGE}" ]]; then
  if podman image exists localhost/rhivos-perfscale-mcp:local; then
    DOMAIN_IMAGE=localhost/rhivos-perfscale-mcp:local
  elif podman image exists rhivos-perfscale-mcp:local; then
    DOMAIN_IMAGE=rhivos-perfscale-mcp:local
  else
    echo "==> Building local RHIVOS PerfScale MCP image via scripts/build_multiarch.sh (--tag local)"
    ./scripts/build_multiarch.sh --tag local
    DOMAIN_IMAGE=localhost/rhivos-perfscale-mcp:local
  fi
fi

echo "==> Ensuring network ${NETWORK_NAME}"
podman network inspect "${NETWORK_NAME}" >/dev/null 2>&1 || podman network create "${NETWORK_NAME}"

# Optional cleanup: remove existing containers when CLEAN=1
if [[ "${CLEAN:-0}" == "1" ]]; then
  podman rm -f "${DOMAIN_NAME}" "${HORREUM_NAME}" >/dev/null 2>&1 || true
fi

if [[ -n "${HORREUM_BASE_URL}" ]]; then
  echo "==> Starting Horreum MCP (${HORREUM_IMAGE}) on ${NETWORK_NAME}"
  if podman container exists "${HORREUM_NAME}"; then
    EXISTING_ENV=$(podman inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${HORREUM_NAME}" 2>/dev/null | grep -E '^HORREUM_BASE_URL=' || true)
    EXISTING_TOKEN=$(podman inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${HORREUM_NAME}" 2>/dev/null | grep -E '^HORREUM_TOKEN=' || true)
    if [[ -z "${EXISTING_ENV}" ]] || { [[ -n "${HORREUM_TOKEN}" ]] && [[ -z "${EXISTING_TOKEN}" ]]; }; then
      echo "Recreating ${HORREUM_NAME} with HORREUM_BASE_URL configured"
      podman rm -f "${HORREUM_NAME}" >/dev/null 2>&1 || true
      if [[ -n "${HORREUM_TOKEN}" ]]; then HTOK_ARG=( -e HORREUM_TOKEN="${HORREUM_TOKEN}" ); else HTOK_ARG=(); fi
      podman run -d --name "${HORREUM_NAME}" --network "${NETWORK_NAME}" "${HTOK_ARG[@]}" \
        -e HORREUM_BASE_URL="${HORREUM_BASE_URL}" \
        -e HTTP_MODE_ENABLED=true \
        -e HTTP_PORT=3001 \
        -p 127.0.0.1:3001:3001 "${HORREUM_IMAGE}"
    else
      podman start "${HORREUM_NAME}" >/dev/null || true
    fi
  else
    if [[ -n "${HORREUM_TOKEN}" ]]; then HTOK_ARG=( -e HORREUM_TOKEN="${HORREUM_TOKEN}" ); else HTOK_ARG=(); fi
    podman run -d --name "${HORREUM_NAME}" --network "${NETWORK_NAME}" "${HTOK_ARG[@]}" \
      -e HORREUM_BASE_URL="${HORREUM_BASE_URL}" \
      -e HTTP_MODE_ENABLED=true \
      -e HTTP_PORT=3001 \
      -p 127.0.0.1:3001:3001 "${HORREUM_IMAGE}"
  fi
  HORREUM_RUNNING=$(podman inspect -f '{{.State.Running}}' "${HORREUM_NAME}" 2>/dev/null || echo false)
  if [[ "${HORREUM_RUNNING}" != "true" ]]; then
    echo "Horreum MCP failed to start; dumping logs and exiting" >&2
    podman logs "${HORREUM_NAME}" | cat || true
    exit 1
  fi
else
  echo "==> HORREUM_BASE_URL not set; skipping Horreum MCP container"
fi

echo "==> Writing RHIVOS PerfScale MCP config"
if [[ -n "${HORREUM_BASE_URL}" ]]; then
  cat >"${CFG_PATH}" <<EOF
{
  "sources": {
    "horreum-http": {
      "endpoint": "http://horreum-mcp:3000",
      "type": "http",
      "timeout_seconds": 30,
      "max_retries": 1,
      "backoff_initial_ms": 200,
      "backoff_multiplier": 2.0
    }
  },
  "enabled_plugins": {"boot-time-verbose": true}
}
EOF
else
  cat >"${CFG_PATH}" <<EOF
{
  "sources": {},
  "enabled_plugins": {"boot-time-verbose": true}
}
EOF
fi

echo "==> Starting RHIVOS PerfScale MCP (${DOMAIN_IMAGE}) on ${NETWORK_NAME}"
if podman container exists "${DOMAIN_NAME}"; then
  podman start "${DOMAIN_NAME}" >/dev/null
else
  podman run -d --name "${DOMAIN_NAME}" --network "${NETWORK_NAME}" \
    -p 127.0.0.1:${DOMAIN_PORT}:8080 \
    -e DOMAIN_MCP_HTTP_TOKEN="${TOKEN}" \
    -e DOMAIN_MCP_CONFIG=/config/config.json \
    -v "${CFG_PATH}":/config/config.json:ro,Z "${DOMAIN_IMAGE}"
fi

echo "==> Waiting for RHIVOS PerfScale MCP health"
health_wait "http://127.0.0.1:${DOMAIN_PORT}/health" "${DOMAIN_HEALTH_TRIES}" "${DOMAIN_HEALTH_SLEEP}" || true
curl -fsS "http://127.0.0.1:${DOMAIN_PORT}/health" | cat

echo "==> Probing Horreum MCP health (optional)"
HORREUM_READY=0
if [[ -n "${HORREUM_BASE_URL}" ]]; then
  HORREUM_RUNNING=$(podman inspect -f '{{.State.Running}}' "${HORREUM_NAME}" 2>/dev/null || echo false)
  if [[ "${HORREUM_RUNNING}" != "true" ]]; then
    echo "Horreum MCP container not running; skipping health probe"
  else
    if health_wait "http://127.0.0.1:3001/health" "${HORREUM_HEALTH_TRIES}" "${HORREUM_HEALTH_SLEEP}"; then
      HORREUM_READY=1
    fi
  fi
else
  echo "HORREUM_BASE_URL not set; skipping Horreum MCP health probe"
fi

echo "==> Running e2e health checks"
export ENABLE_CONTAINER_E2E=1
export DOMAIN_MCP_URL="http://127.0.0.1:${DOMAIN_PORT}"
export DOMAIN_MCP_TOKEN="${TOKEN}"

# Ensure previous env does not leak into this run
unset HORREUM_MCP_URL E2E_SOURCE_ID E2E_TEST_ID E2E_LIMIT

# Only set Horreum URL if reachable; do not export source-driven vars by default
if [[ "${HORREUM_READY}" == "1" ]]; then
  export HORREUM_MCP_URL="http://127.0.0.1:3001"
else
  echo "Horreum MCP not reachable on 127.0.0.1:3001; skipping Horreum URL export"
fi

pytest -q tests/test_container_e2e_scaffold.py -q || true

echo "==> Done. Containers running: ${DOMAIN_NAME}, ${HORREUM_NAME}."
echo "    Stop with: podman stop ${DOMAIN_NAME} ${HORREUM_NAME}"


