#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CACHE_BASE="${ROOT_DIR}/.cache/meera/llama-cpp/b8672"

echo "Cleaning llama.cpp caches under: ${CACHE_BASE}"

if [ -d "${CACHE_BASE}" ]; then
  # Remove extracted Ubuntu bundle directories (CPU + Vulkan).
  rm -rf "${CACHE_BASE}"/ubuntu-*

  # Remove downloaded Ubuntu archives and partial downloads.
  rm -f "${CACHE_BASE}"/llama-b8672-bin-ubuntu*.tar.gz
  rm -f "${CACHE_BASE}"/llama-b8672-bin-ubuntu*.tar.gz.part
else
  echo "No cache directory found for b8672."
fi

echo "Stopping local llama-server processes on ports 8080/8081 (if any)..."
pkill -f 'llama-server.*--port 8080' 2>/dev/null || true
pkill -f 'llama-server.*--port 8081' 2>/dev/null || true

echo "Done. Next run will re-download required llama.cpp Ubuntu bundles."
