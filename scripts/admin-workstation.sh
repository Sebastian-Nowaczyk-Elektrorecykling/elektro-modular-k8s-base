#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/lib/common.sh"
root_required
debian_required
apt_prepare
apt-get install -y age dnsutils shellcheck make openssh-client python3-venv
# configure.py can now run on a fresh Debian workstation.
site=${1:-$REPO_ROOT/config/site.yaml}
python3 "$REPO_ROOT/scripts/configure.py" "$site"
load_site
arch=$(dpkg --print-architecture)
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
cd "$tmpdir"
helm_archive="helm-v${HELM_VERSION}-linux-${arch}.tar.gz"
download "https://get.helm.sh/$helm_archive" "$helm_archive"
download "https://get.helm.sh/$helm_archive.sha256sum" "$helm_archive.sha256sum"
sha256sum -c "$helm_archive.sha256sum"
tar -xzf "$helm_archive"
install -m 0755 "linux-$arch/helm" /usr/local/bin/helm
archive="flux_${FLUX_VERSION}_linux_${arch}.tar.gz"
download "https://github.com/fluxcd/flux2/releases/download/v$FLUX_VERSION/$archive" "$archive"
download "https://github.com/fluxcd/flux2/releases/download/v$FLUX_VERSION/flux_${FLUX_VERSION}_checksums.txt" flux-checksums.txt
awk -v f="$archive" '$2==f' flux-checksums.txt >selected.sha256
[[ -s selected.sha256 ]] || die 'Flux checksum missing.'
sha256sum -c selected.sha256
tar -xzf "$archive" flux
install -m 0755 flux /usr/local/bin/flux
kube_version=${K3S_VERSION%%+*}
download "https://dl.k8s.io/release/$kube_version/bin/linux/$arch/kubectl" kubectl
download "https://dl.k8s.io/release/$kube_version/bin/linux/$arch/kubectl.sha256" kubectl.sha256
printf '%s  kubectl\n' "$(cat kubectl.sha256)" >selected.sha256
sha256sum -c selected.sha256
install -m 0755 kubectl /usr/local/bin/kubectl
binary="sops-v${SOPS_VERSION}.linux.${arch}"
download "https://github.com/getsops/sops/releases/download/v$SOPS_VERSION/$binary" "$binary"
download "https://github.com/getsops/sops/releases/download/v$SOPS_VERSION/sops-v${SOPS_VERSION}.checksums.txt" sops-checksums.txt
awk -v f="$binary" '$2==f' sops-checksums.txt >selected.sha256
[[ -s selected.sha256 ]] || die 'SOPS checksum missing.'
sha256sum -c selected.sha256
install -m 0755 "$binary" /usr/local/bin/sops
archive="kustomize_v${KUSTOMIZE_VERSION}_linux_${arch}.tar.gz"
base="https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv$KUSTOMIZE_VERSION"
download "$base/$archive" "$archive"
download "$base/checksums.txt" kustomize-checksums.txt
awk -v f="$archive" '$2==f' kustomize-checksums.txt >selected.sha256
[[ -s selected.sha256 ]] || die 'Kustomize checksum missing.'
sha256sum -c selected.sha256
tar -xzf "$archive" kustomize
install -m 0755 kustomize /usr/local/bin/kustomize
log 'Administrator tools installed. Import the kubeconfig securely; see docs/bootstrap.md.'
