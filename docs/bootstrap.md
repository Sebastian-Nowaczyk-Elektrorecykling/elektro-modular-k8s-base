# Bootstrap a site

Run host scripts only on the intended fresh Debian 13 computers. They disable swap, configure kernel settings, install software and create k3s services. The network helper replaces the active network manager for its interface; use the local console when running it. Node removal uninstalls k3s after evacuation.

## 1. Choose addresses and capacity

Clone the repository on the workstation and each node. Use a local, unprivileged repository checkout and elevate only host scripts.

```bash
cp config/site.example.yaml config/site.yaml
# Edit config/site.yaml for your LAN, node records, resolvers, API address and replica counts.
sudo bash scripts/admin-workstation.sh config/site.yaml
python3 scripts/configure.py config/site.yaml
git diff
```

Commit the generated settings, DNS node records and bootstrap source. `config/site.yaml` and `.local/` are ignored; keep the private site input in your own backup. Copy the same site configuration to each node and run `configure.py` there (Debian packages `python3` and `python3-yaml` are required). The generated `site.env` and `versions.env` are consumed by the host scripts.

Choose DNS/internal/external gateway addresses in the same LAN subnet, outside DHCP's allocation range and outside addresses used by devices. This is necessary even though the router needs no new routes. On a LAN-connected Linux computer, before the service addresses have been deployed, use `sudo arping -D -I enp1s0 ADDRESS` to look for conflicts. ARP cannot detect an offline device or guarantee that a DHCP server will never lease an address; use your address inventory.

Defaults require three workload/storage nodes for PostgreSQL anti-affinity and storage redundancy. For a one-node trial, set `longhorn_replicas`, `postgres_instances` and `platform_replicas` to `1`. Pure controllers alone cannot run the application platform.

## 2. Prepare static node networking when needed

If Debian already has the desired stable node address, keep it. Otherwise, from the console:

```bash
sudo bash scripts/configure-network.sh enp1s0 192.168.10.11 192.168.10.1
```

The interface and router are site-specific. Nodes keep real upstream resolvers; do not point their boot-time resolver at the cluster they are trying to start.

## 3. Bootstrap the first controller or hybrid

```bash
# Choose one:
sudo bash scripts/controller-bootstrap.sh control-1 192.168.10.11
sudo bash scripts/hybrid-bootstrap.sh hybrid-1 192.168.10.11
```

For every worker/hybrid, review GPU package results and reboot after preparation. A pure controller needs no GPU setup. Rebooting a single bootstrap server temporarily stops its API; the service returns on boot.

Copy `/etc/rancher/k3s/k3s.yaml` securely to the administrator's `~/.kube/config`, mode `0600`, and change only its `server:` URL from `127.0.0.1` to the configured API address. Do not paste kubeconfig contents or cluster join tokens into Git or a chat.

Copy `/var/lib/rancher/k3s/server/token` securely into a root-readable file on joining servers. Use `/var/lib/rancher/k3s/server/agent-token` for workers; it is commonly linked to the server token unless an independent agent token is configured. Use the full secure token beginning `K10`, which binds joining nodes to the cluster CA.

```bash
sudo bash scripts/controller-join.sh control-2 192.168.10.12 /root/k3s-token
sudo bash scripts/worker-join.sh worker-1 192.168.10.21 /root/k3s-agent-token
sudo bash scripts/hybrid-join.sh hybrid-2 192.168.10.12 /root/k3s-token
```

Use different names/addresses for each node. The examples illustrate choices, not a list to run on the same machine. Server critical flags are generated identically. Until the CNI is installed, nodes/pods may remain NotReady/Pending.

Longhorn initially uses `/var/lib/longhorn` on the existing filesystem. If a dedicated data disk is desired, format and mount the correct disk there **before** starting storage, then record a persistent mount in `/etc/fstab`. No script guesses which disk is disposable.

## 4. Generate secrets and start reconciliation

On the workstation:

```bash
python3 scripts/generate-secrets.py
# Back up .local/bootstrap-secrets.yaml and .local/internal-ca.key securely now.
bash scripts/bootstrap-cluster.sh
flux get kustomizations -A
flux get helmreleases -A
```

The bootstrap script checks API access, installs the CNI, seeds namespaces/secrets, installs pinned Flux controllers on workload nodes and points Flux at Git. Bootstrap secrets are applied imperatively to break dependency cycles. Re-running `generate-secrets.py` refuses to replace credentials or the CA.

The initial installation uses the public repository read-only. If making the repository private, create a narrowly scoped Git credential Secret in `flux-system`, set `bootstrap/source.yaml`'s `spec.secretRef`, and reapply it. Flux does not need write access to this repository.

For encrypted Git-managed secrets:

```bash
age-keygen -o .local/flux.agekey
age-keygen -y .local/flux.agekey
# Supply the printed public recipient:
bash scripts/encrypt-secrets.sh age1YOUR_PUBLIC_RECIPIENT
kubectl -n flux-system create secret generic sops-age --from-file=age.agekey=.local/flux.agekey
# Review and commit clusters/lan/secrets/ and secrets-sync.yaml plus the root kustomization change.
```

The age key is installed after Flux creates its namespace. Keep an offline copy of it. This optional step never commits a plaintext Secret. Credential rotation is a separate operation and must update the actual database credentials as well as Secrets.

## 5. Set up identity and access

Configure client DNS and install the public CA certificate using [the networking guide](networking.md). Wait for `databases`, `authentik`, `dns`, and `gateways` to become ready. The `openfga-check` and `inventory` stages initially wait for the following configuration:

```bash
bash scripts/configure-identity.sh
python3 scripts/fga.py init
flux reconcile kustomization openfga-check
flux reconcile kustomization inventory
python3 scripts/identity-admin.py users
```

Sign in at `https://auth.admin.internal` as `akadmin`, using the bootstrap password stored in `.local/bootstrap-secrets.yaml`. Create a named administrator, register MFA/passkeys, and rotate/remove the bootstrap API token and password once recovery access is verified. No SMTP server is assumed; configure email before using email recovery/invitation flows.

Use [the identity guide](identity.md) to give specific users dashboard/API access and create expiring agents. The generated provider secrets and OpenFGA IDs under `.local/` need secure backup. Save encrypted copies of the resulting `inventory-oidc` and `openfga-check-config` Secrets if you want them restored through GitOps too.

The final readiness checklist is in [validation](validation.md). A green Flux tree alone does not prove LAN reachability, GPU support, restore capability or node failure tolerance.
