#!/usr/bin/env bash
set -euo pipefail

# Multi-arch build helper using Buildah/Podman for container registries.
#
# Requirements on the host/runner:
# - buildah, podman, skopeo
# - qemu-user-static and binfmt registrations for cross-arch (recommended)
#
# Env vars:
#   IMAGE_REPO      Target repo (e.g., ghcr.io/user/repo or quay.io/org/repo) [required]
#   REGISTRY_TYPE   Registry type: github, quay, or other (default: quay)
#   REGISTRY_USERNAME / REGISTRY_PASSWORD  Credentials for registry (optional)
#   QUAY_USERNAME / QUAY_PASSWORD          Back-compat for Quay (optional)
#   GITHUB_TOKEN    GitHub token for ghcr.io authentication (optional)
#
# Options:
#   -t, --tag <tag>             Image tag (default: git short SHA or timestamp)
#   -e, --expires <period>      Expiration label value (default: 90d)
#   --expires-label <key>       Expiration label key (default: quay.expires-after)
#   --push                      Push manifest to <repo>:<tag>
#   --push-main                 Also push/alias the manifest to :main
#   -f, --file <path>           Containerfile path (default: Containerfile)
#   -h, --help               Show help

show_help() {
  cat <<EOF
Usage: REGISTRY_USERNAME=... REGISTRY_PASSWORD=... IMAGE_REPO=ghcr.io/user/repo \
       $(basename "$0") [options]

Options:
  -t, --tag <tag>             Image tag (default: git short SHA or timestamp)
  -e, --expires <period>      Expiration label value (default: 90d)
      --expires-label <key>   Expiration label key (default: quay.expires-after)
      --push                  Push manifest to <repo>:<tag>
      --push-main             Also push manifest to :main
  -f, --file <path>           Containerfile path (default: Containerfile)
  -h, --help               Show this help

Environment:
  IMAGE_REPO           Target repository (required)
  REGISTRY_TYPE        Registry type: github, quay, or other (default: quay)
  
  For GitHub Container Registry (ghcr.io):
    GITHUB_TOKEN       GitHub token for authentication
    GITHUB_ACTOR       GitHub username (default: from token)
  
  For Quay.io or other registries:
    REGISTRY_USERNAME  Registry username
    REGISTRY_PASSWORD  Registry password
    
  Legacy support:
    QUAY_USERNAME, QUAY_PASSWORD (for backward compatibility)

Examples:
  # GitHub Container Registry
  REGISTRY_TYPE=github GITHUB_TOKEN=\$GITHUB_TOKEN IMAGE_REPO=ghcr.io/user/repo \\
    ./scripts/build_multiarch.sh --tag v1.0.0 --push
  
  # Quay.io
  REGISTRY_USERNAME=myuser REGISTRY_PASSWORD=\$TOKEN IMAGE_REPO=quay.io/org/repo \\
    ./scripts/build_multiarch.sh --tag v1.0.0 --push
EOF
}

TAG=""
EXPIRES="90d"
EXPIRES_LABEL="quay.expires-after"
PUSH=0
PUSH_MAIN=0
CONTAINERFILE="Containerfile"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -t|--tag)
      TAG="${2:-}"
      shift 2
      ;;
    -e|--expires)
      EXPIRES="${2:-}"
      shift 2
      ;;
    --expires-label)
      EXPIRES_LABEL="${2:-quay.expires-after}"
      shift 2
      ;;
    --push)
      PUSH=1
      shift 1
      ;;
    --push-main)
      PUSH_MAIN=1
      shift 1
      ;;
    -f|--file)
      CONTAINERFILE="${2:-Containerfile}"
      shift 2
      ;;
    -h|--help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      show_help
      exit 1
      ;;
  esac
done

# Default IMAGE_REPO only if not provided at all
if [[ -z "${IMAGE_REPO:-}" ]]; then
  IMAGE_REPO="localhost/domain-mcp-server"
  echo "INFO: Using default IMAGE_REPO: $IMAGE_REPO" >&2
fi
REGISTRY_HOST="${IMAGE_REPO%%/*}"

if [[ -z "$TAG" ]]; then
  if command -v git >/dev/null 2>&1; then
    TAG="$(git rev-parse --short HEAD 2>/dev/null || true)"
  fi
  TAG=${TAG:-"local-$(date +%Y%m%d%H%M%S)"}
fi

# Use a local manifest name to avoid collisions with existing image tags
REPO_NAME="${IMAGE_REPO##*/}"
LOCAL_MANIFEST_REF="localhost/${REPO_NAME}:manifest-${TAG}"
REMOTE_MANIFEST_REF="${IMAGE_REPO}:${TAG}"

# Best-effort binfmt enablement (requires privileges; safe to skip if preconfigured)
if command -v podman >/dev/null 2>&1; then
  if podman info >/dev/null 2>&1; then
    podman run --privileged --rm tonistiigi/binfmt --install all >/dev/null 2>&1 || true
  fi
fi

# Registry authentication
if [[ "$PUSH" -eq 1 ]]; then
  REGISTRY_TYPE="${REGISTRY_TYPE:-quay}"
  
  if [[ "$REGISTRY_TYPE" == "github" ]]; then
    # GitHub Container Registry authentication
    if [[ -n "${GITHUB_TOKEN:-}" ]]; then
      USERNAME="${GITHUB_ACTOR:-$(echo "$GITHUB_TOKEN" | base64 -d 2>/dev/null | cut -d: -f1 || echo "token")}"
      PASSWORD="$GITHUB_TOKEN"
      echo "INFO: Authenticating to GitHub Container Registry as $USERNAME" >&2
    else
      echo "ERROR: GITHUB_TOKEN required for GitHub Container Registry" >&2
      exit 1
    fi
  else
    # Quay.io or other registry authentication
    USERNAME="${REGISTRY_USERNAME:-${QUAY_USERNAME:-}}"
    PASSWORD="${REGISTRY_PASSWORD:-${QUAY_PASSWORD:-}}"
    echo "INFO: Authenticating to $REGISTRY_HOST" >&2
  fi
  
  if [[ -n "$USERNAME" && -n "$PASSWORD" ]]; then
    if command -v podman >/dev/null 2>&1; then
      echo "$PASSWORD" | podman login -u "$USERNAME" --password-stdin "$REGISTRY_HOST"
    fi
    if command -v buildah >/dev/null 2>&1; then
      echo "$PASSWORD" | buildah login -u "$USERNAME" --password-stdin "$REGISTRY_HOST"
    fi
  else
    echo "INFO: No registry credentials provided; proceeding without login." >&2
  fi
fi

# Create manifest (local ref) and build per-arch images
buildah manifest rm "$LOCAL_MANIFEST_REF" >/dev/null 2>&1 || true
buildah manifest create "$LOCAL_MANIFEST_REF"

echo "Building amd64 image..."
buildah bud --override-arch amd64 --override-os linux \
  -f "$CONTAINERFILE" \
  --label "org.opencontainers.image.revision=${OCI_REVISION:-$TAG}" \
  --label "${EXPIRES_LABEL}=${EXPIRES}" \
  -t "${IMAGE_REPO}:${TAG}-amd64" .

echo "Building arm64 image..."
buildah bud --override-arch arm64 --override-os linux \
  -f "$CONTAINERFILE" \
  --label "org.opencontainers.image.revision=${OCI_REVISION:-$TAG}" \
  --label "${EXPIRES_LABEL}=${EXPIRES}" \
  -t "${IMAGE_REPO}:${TAG}-arm64" .

echo "Assembling manifest list..."
buildah manifest add "$LOCAL_MANIFEST_REF" "containers-storage:${IMAGE_REPO}:${TAG}-amd64"
buildah manifest add "$LOCAL_MANIFEST_REF" "containers-storage:${IMAGE_REPO}:${TAG}-arm64"
# Note: buildah manifest annotate doesn't work reliably for local manifests, skipping

# For local use, tag the current architecture image as the main tag
CURRENT_ARCH=$(uname -m)
case "$CURRENT_ARCH" in
  x86_64) LOCAL_ARCH_TAG="${IMAGE_REPO}:${TAG}-amd64" ;;
  aarch64|arm64) LOCAL_ARCH_TAG="${IMAGE_REPO}:${TAG}-arm64" ;;
  *) 
    echo "WARNING: Unknown architecture $CURRENT_ARCH, defaulting to amd64" >&2
    LOCAL_ARCH_TAG="${IMAGE_REPO}:${TAG}-amd64"
    ;;
esac

echo "Creating local runnable tag: ${IMAGE_REPO}:${TAG} -> ${LOCAL_ARCH_TAG}"
podman tag "$LOCAL_ARCH_TAG" "${IMAGE_REPO}:${TAG}"

if [[ "$PUSH" -eq 1 ]]; then
  echo "Pushing multi-arch manifest to ${REMOTE_MANIFEST_REF}..."
  buildah manifest push --all "$LOCAL_MANIFEST_REF" "docker://${IMAGE_REPO}:${TAG}"
  if [[ "$PUSH_MAIN" -eq 1 ]]; then
    echo "Also pushing manifest to :main..."
    buildah manifest push --all "$LOCAL_MANIFEST_REF" "docker://${IMAGE_REPO}:main"
  fi
else
  echo "Built multi-arch manifest locally: ${LOCAL_MANIFEST_REF} (not pushed)" >&2
  echo "Local runnable image available: ${IMAGE_REPO}:${TAG}" >&2
fi

echo "Done: ${IMAGE_REPO}:${TAG}" >&2

