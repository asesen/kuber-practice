#!/usr/bin/env bash
set -euo pipefail

NS="kuber-practice"
IMAGE="custom-app:local"
ISTIO_VERSION="1.31.5"
ISTIOCTL_PATH="./istio-${ISTIO_VERSION}/bin/istioctl"

require() {
  if ! command -v "$1" >/dev/null; then
    echo "missing dependency: $1" >&2
    exit 1
  fi
}

require kubectl
require docker
require kind
require curl
require tar

ensure_kind_cluster() {
  if kind get clusters | grep -q '^lab$'; then
    echo "Kind cluster 'lab' already exists"
  else
    echo "Creating kind cluster 'lab'..."
    kind create cluster --name lab
  fi
}

install_istioctl() {
  if command -v istioctl >/dev/null; then
    ISTIOCTL_PATH="$(command -v istioctl)"
    return
  fi

  if [ ! -x "${ISTIOCTL_PATH}" ]; then
    echo "Downloading istioctl ${ISTIO_VERSION}..."
    curl -L https://istio.io/downloadIstio | ISTIO_VERSION="${ISTIO_VERSION}" sh -
    chmod +x "${ISTIOCTL_PATH}"
  fi
}

install_istio() {
  if kubectl get ns istio-system >/dev/null; then
    echo "Istio mesh already installed"
    return
  fi

  install_istioctl
  echo "Installing Istio control plane..."
  "${ISTIOCTL_PATH}" install --set profile=demo -y
  echo "Waiting for Istio control plane..."
  kubectl -n istio-system rollout status deployment/istiod --timeout=180s
  kubectl -n istio-system rollout status deployment/istio-ingressgateway --timeout=180s
}

echo "Ensuring kind cluster..."
ensure_kind_cluster

echo "Installing Istio mesh..."
install_istio

echo "Building image: ${IMAGE}"
docker build -t "${IMAGE}" ./app

if kind get clusters | grep -q '^lab$'; then
  echo "Loading image into kind..."
  kind load docker-image --name lab "${IMAGE}"
fi

echo "Applying Kubernetes manifests..."
kubectl apply -f ./k8s

echo "Applying Istio manifests..."
kubectl apply -f ./istio

echo "Restarting workloads (sidecars / mesh)..."
kubectl -n "${NS}" rollout restart deploy/custom-app || true
kubectl -n "${NS}" rollout restart ds/log-agent || true
kubectl -n "${NS}" rollout restart sts/archive-store || true

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
