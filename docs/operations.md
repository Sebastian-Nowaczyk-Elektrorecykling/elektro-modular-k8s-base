# Operation and recovery

## Add and remove nodes

Use the relevant join wrapper with the same generated site configuration. A worker has no etcd membership; a controller/hybrid does. Keep an odd number of healthy controller-capable nodes for normal operation, typically three. Adding a second server alone does not create failure tolerance.

Removal runs on the administrator workstation with `kubectl` access and SSH/sudo access to the target:

```bash
bash scripts/remove-worker.sh worker-2 admin@192.168.10.22
bash scripts/remove-server.sh control-3 admin@192.168.10.13
# Hybrids use remove-server.sh.
```

The scripts verify the role and API endpoint, check surviving controller readiness/quorum for server removal, create an etcd snapshot on a departing server, cordon the node, request Longhorn replica eviction, wait for replicas to move, drain respecting disruption budgets, stop k3s, delete the Node and uninstall k3s. Draining intentionally deletes ephemeral `emptyDir` data. They do not force deletion of pods blocked by a disruption budget or format retained disks.

Longhorn evacuation needs enough eligible nodes and free capacity to create replacement replicas. A single-node trial cannot safely evacuate its only storage node; add capacity or export/restore its data as a deliberate teardown. If eviction/drain stops, the node stays cordoned. Diagnose storage/PodDisruptionBudget conditions, then retry. To cancel evacuation, reset Longhorn's `evictionRequested` and `allowScheduling` after checking state, then uncordon.

Deleting a k3s server Node permits k3s to remove its etcd membership. Verify the remaining server/member state after removal. Failed/unreachable node recovery is different from normal removal: do not bypass quorum and volume ownership checks with forced uninstall commands. [k3s server CLI and snapshots](https://docs.k3s.io/cli/etcd-snapshot).

Before removing the node behind `API_ADDRESS`, move that endpoint to a surviving server or independent API VIP. Update generated settings, every server/client URL and TLS SANs as needed, reconcile Cilium's direct API setting and confirm access through the new address. The provided example API endpoint does not fail over automatically.

## Backups

Replicas protect availability, not history. The base enables k3s etcd snapshots every six hours with fourteen local copies. Those are not off-node backups and do not contain application volumes. Preserve the server token with the snapshots: it is required for restoring encrypted bootstrap data.

Back up separately:

- k3s etcd snapshots and the server token, to encrypted off-node storage.
- PostgreSQL data with a tested CloudNativePG/Barman object-store configuration or another database-aware backup method, including WAL when point-in-time recovery is required.
- Longhorn application volumes using an independently hosted backup target.
- The internal CA key/certificate, age key, authentik secret key, identity bootstrap/provider credentials and OpenFGA store/model IDs.
- Git repository and your private site configuration.

No object-store endpoint or credential was provided, so remote backups are not enabled. Configure them before keeping important data. Do not set Longhorn's only backup target inside the same cluster and call that disaster recovery. [Longhorn backups](https://longhorn.io/docs/1.12.1/snapshots-and-backups/backup-and-restore/) and [CloudNativePG documentation](https://cloudnative-pg.io/documentation/current/).

For a one-off logical PostgreSQL export, discover the primary for each CNPG cluster and use its local `pg_dump` as the PostgreSQL user. Send the result directly into encrypted off-node storage; do not commit a dump. Practice a clean restore before relying on the procedure.

## Rebuild and restore

Restore control-plane state following the pinned k3s snapshot procedure, using the original server token. Restore CA/age/authentik keys before restoring dependent components. Then allow Flux to reconcile the pinned infrastructure, restore PostgreSQL/Longhorn data from their own backups, and reapply `inventory-oidc` / `openfga-check-config` from secure backup. Reuse the existing OpenFGA store and model IDs; `fga.py init` stops instead of silently creating a new store if a previous one is found.

Keep recovery access independent of authentik: a protected administrator kubeconfig and SSH path are necessary if the identity service or its database is unavailable. Application SSO grants do not grant Kubernetes cluster-admin rights.

## Upgrades and rotations

Create and verify backups, review upstream compatibility/release notes, then update pinned versions in both `config/versions.yaml` and the relevant manifests/scripts. Run local validation, chart rendering and the identity container contract. Upgrade a test cluster before the production site.

Upgrade k3s one server at a time, preserving quorum, then workers. The fresh-node installer intentionally refuses existing cluster data; use the official pinned-version k3s upgrade procedure. The Flux CLI/controller installation is managed by `bootstrap-cluster.sh`; ordinary application reconciliation does not upgrade Flux itself.

Gateway API/Cilium compatibility is an explicit pair. Update Cilium Helm values used during bootstrap together with its Flux values. For an OpenFGA upgrade, add a new versioned migration Job, point the server at the same version and retain the migration-before-server dependency. Do not re-use an immutable completed Job name to imply a new migration ran.

SOPS encryption does not rotate a database password. Rotate passwords in PostgreSQL/CNPG and consuming Secrets through a staged plan, then refresh encrypted copies. Do not re-run secret generation against a live cluster. Changing authentik's main secret key can invalidate encrypted/session state; consult upstream migration guidance. A CA rotation needs an overlap period in client trust stores.

The inventory check proxy is bound to a specific model ID. Publish a new model, validate its tuples/denials, then update `openfga-check-config` and restart that deployment. Existing runtime Secrets injected as environment variables need a pod restart after changes. ConfigMap code updates use Kustomize-generated names to roll deployments automatically.
