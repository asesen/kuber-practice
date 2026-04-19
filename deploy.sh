#!/usr/bin/env bash
set -euo pipefail

NS="kuber-practice"
IMAGE="custom-app:local"

require() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing dependency: $1" >&2; exit 1; }
}

require kubectl
require docker

echo "Building image: ${IMAGE}"
docker build -t "${IMAGE}" ./app

if command -v kind >/dev/null 2>&1; then
  if kind get clusters >/dev/null 2>&1; then
    echo "Loading image into kind..."
    kind load docker-image --name lab "${IMAGE}" >/dev/null 2>&1
  fi
fi

echo "Applying Kubernetes manifests..."
kubectl apply -f ./k8s

echo "Applying Istio manifests..."
kubectl apply -f ./istio

echo "Restarting workloads (sidecars / mesh)..."
kubectl -n "${NS}" rollout restart deploy/custom-app 2>/dev/null || true
kubectl -n "${NS}" rollout restart ds/log-agent 2>/dev/null || true
kubectl -n "${NS}" rollout restart sts/archive-store 2>/dev/null || true

echo "Waiting for readiness..."
kubectl -n "${NS}" rollout status deploy/custom-app --timeout=180s
kubectl -n "${NS}" rollout status ds/log-agent --timeout=180s
kubectl -n "${NS}" rollout status sts/archive-store --timeout=180s

echo "Done."
echo
echo "Useful checks:"
echo "  kubectl -n ${NS} port-forward svc/custom-app 8080:80"
echo "  kubectl -n istio-system port-forward svc/istio-ingressgateway 8080:80"
echo "  curl http://127.0.0.1:8080/"
echo "  curl http://127.0.0.1:8080/status"
echo "  curl -X POST http://127.0.0.1:8080/log -H 'Content-Type: application/json' -d '{\"message\":\"test\"}'"
echo "  curl http://127.0.0.1:8080/logs"
