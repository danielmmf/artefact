#!/usr/bin/env bash
# Qdrant Server do S2, versão e digest fixados. Dois servidores idênticos, um por estratégia (B denso, C híbrido),
# para medir RAM e disco de cada uma. Dados em var/s2/ (fora do versionamento). Uso: s2-servers.sh up|down|status
set -euo pipefail
IMAGE="qdrant/qdrant:v1.20.0@sha256:9bfc89f9914fc14876a88c05270685921a55b8877b254a98bcc1cc2f0a424cd2"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
declare -A PORTS=([dense]=16333 [hybrid]=16433)

up() {
  for name in dense hybrid; do
    mkdir -p "$ROOT/var/s2/qdrant-$name"
    if [ "$(docker ps -q -f name="^emporio-s2-qdrant-$name$")" ]; then continue; fi
    docker rm -f "emporio-s2-qdrant-$name" >/dev/null 2>&1 || true
    docker run -d --name "emporio-s2-qdrant-$name" --user "$(id -u):$(id -g)" -p "127.0.0.1:${PORTS[$name]}:6333" \
      -v "$ROOT/var/s2/qdrant-$name:/qdrant/storage" -e QDRANT__TELEMETRY_DISABLED=true -e QDRANT__STORAGE__STORAGE_PATH=/qdrant/storage/data -w /qdrant/storage -e QDRANT__SERVICE__STATIC_CONTENT_DIR=/qdrant/static --entrypoint /qdrant/qdrant "$IMAGE" --config-path /qdrant/config/production.yaml >/dev/null
  done
  for name in dense hybrid; do
    for _ in $(seq 1 60); do curl -sf "http://127.0.0.1:${PORTS[$name]}/readyz" >/dev/null && break; sleep 1; done
    curl -sf "http://127.0.0.1:${PORTS[$name]}/readyz" >/dev/null || { echo "Qdrant $name não ficou pronto" >&2; exit 1; }
  done
}
down() { docker rm -f emporio-s2-qdrant-dense emporio-s2-qdrant-hybrid >/dev/null 2>&1 || true; }
status() { docker ps -f name=emporio-s2-qdrant --format '{{.Names}} {{.Image}} {{.Status}}'; }
"${1:-status}"
