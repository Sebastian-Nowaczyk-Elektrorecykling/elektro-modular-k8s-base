#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
cd "$REPO_ROOT"
python3 scripts/configure.py config/site.example.yaml
load_site
mkdir -p .local/bin .local/downloads
cd .local/downloads
archive="helm-v${HELM_VERSION}-linux-amd64.tar.gz"
download "https://get.helm.sh/$archive" "$archive"
download "https://get.helm.sh/$archive.sha256sum" "$archive.sha256sum"
sha256sum -c "$archive.sha256sum"
tar -xzf "$archive"
install -m 0755 linux-amd64/helm ../bin/helm
archive="kustomize_v${KUSTOMIZE_VERSION}_linux_amd64.tar.gz"
base="https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv$KUSTOMIZE_VERSION"
download "$base/$archive" "$archive"
download "$base/checksums.txt" checksums.txt
awk -v f="$archive" '$2==f' checksums.txt >selected.sha256
test -s selected.sha256
sha256sum -c selected.sha256
tar -xzf "$archive" kustomize
install -m 0755 kustomize ../bin/kustomize
