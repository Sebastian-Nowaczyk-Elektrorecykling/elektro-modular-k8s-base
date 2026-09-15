# Elektro modular Kubernetes base

A Flux-managed Debian 13 / k3s foundation for a LAN-based internal developer platform. Cilium replaces Flannel, kube-proxy, ServiceLB and Traefik; Longhorn replaces local-path storage. CloudNativePG runs the identity and authorization databases.

The checked-in network addresses are examples. Configure your site before running any provisioning script. This repository creates a cluster foundation; it does not deploy itself to hardware.

| Capability | Implementation |
| --- | --- |
| Kubernetes | k3s with embedded etcd; bootstrap and join scripts for dedicated controllers, workers and hybrids |
| Networking | Cilium VXLAN, WireGuard between nodes, Gateway API, LAN L2 announcements |
| Storage | Longhorn default class; separate single-replica volumes beneath replicated PostgreSQL |
| PostgreSQL | CloudNativePG, separate authentik and OpenFGA clusters |
| LAN DNS | Separate CoreDNS resolver, TCP and UDP port 53, configurable upstreams |
| Private TLS | A locally generated CA and cert-manager certificates |
| Human sign-in | authentik; independent grants for each dashboard and API |
| Agents | Expiring authentik Actors, autonomous credentials, explicit on-behalf-of token exchange |
| Authorization | OpenFGA service/delegation model, check-only application endpoint, working API example |
| Future public domain | Separate opt-in Gateway and certificate, restricted namespace attachment |

| Domain | Purpose | Included example |
| --- | --- | --- |
| `*.admin.internal` | Administration | `auth.admin.internal`, `longhorn.admin.internal`, `hubble.admin.internal` |
| `*.test.internal` | IDP test applications | Namespace `idp-test` |
| `*.staging.internal` | IDP staging applications | Namespace `idp-staging` |
| `*.internal` | User-facing and production IDP applications | `inventory.internal` |

Start with [the bootstrap runbook](docs/bootstrap.md). It covers site settings, CA/secrets, node preparation, the Cilium-to-Flux handoff, and initial access grants.

- [Architecture and design decisions](docs/architecture.md)
- [LAN networking and Windows/Linux DNS setup](docs/networking.md)
- [Identity, service grants and agent delegation](docs/identity.md)
- [Authentication survey: 12 candidates and complements](docs/authentication-survey.md)
- [GPU prerequisites and hardware limitations](docs/gpu.md)
- [Node removal, backups, recovery and upgrades](docs/operations.md)
- [Adding applications and the external gateway](docs/applications.md)
- [Validation and physical acceptance checks](docs/validation.md)
- [Original request](docs/requirements.md)

Recommended capacity is three controller-capable nodes and three storage/workload-capable nodes; three hybrids can fulfill both roles. Budget at least 4 CPU cores and 8 GiB RAM per hybrid for the base and leave capacity for applications. Dedicated controllers can be smaller. A single hybrid works with all replica settings set to `1`, with no availability guarantee.

Versions are pinned in manifests and [config/versions.yaml](config/versions.yaml). Update both together. Gateway API is pinned to the version supported by the selected Cilium release. Debian packages deliberately follow signed Debian 13 security updates.

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
make validate test
# With Helm, Kustomize, and access to upstream repositories:
make render
```

GitHub Actions also exercises actual authentik token exchange and the OpenFGA model. A real cluster must pass the hardware acceptance steps before production use. Remote backups and public-domain publication need site-specific configuration.
