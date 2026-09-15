# Validation and acceptance

`make validate test` runs offline: unique-key YAML parsing, pinned chart checks, Flux dependency/path validation, secret/exposure invariants, Bash syntax and 21 network/authorization tests. ShellCheck is required in CI; the local command reports when it is unavailable.

`make render` builds every Kustomize entry point and renders all pinned charts against Kubernetes 1.36.4. This catches chart retrieval/template/schema failures and Kustomize resource/reference errors. It does not contact a Kubernetes API or validate all admission policies.

The `identity-contract` workflow starts fresh PostgreSQL/authentik/OpenFGA containers. It applies the actual provider configuration and verifies autonomous identity, user→agent and agent→agent exchange, wrong-parent denial, missing-actor denial, OpenFGA grants and revocation. Those containers have isolated, generated test credentials. They do not use production credentials or connect to your cluster.

On real hardware, verify the following before putting the base into service:

1. `kubectl get nodes -o wide`: correct node IPs, roles and Ready states; applications/data replicas absent from pure controllers.
2. `flux get kustomizations -A` and `flux get helmreleases -A`: no stalled stages after completing identity/OpenFGA initialization.
3. `kubectl -n kube-system exec ds/cilium -- cilium-dbg status`: CNI, kube-proxy replacement and health; run Cilium connectivity tests with an appropriate CLI if installed.
4. From a separate LAN computer, test DNS over **both UDP and TCP**, upstream fallback, all three internal domain families, HTTPS trust and unauthorized-user rejection. Repeat from a pod for internal issuer resolution.
5. Inspect Gateway `Accepted`/`Programmed` conditions and HTTPRoute `Accepted`/`ResolvedRefs`. Confirm that service IPs equal the configured LAN addresses and public/example gateways remain absent.
6. Stop the current L2-announcing gateway node while the API remains available through a surviving endpoint. Observe ARP/VIP handover and successful DNS/HTTPS requests. Test API endpoint failover separately if an independent HA endpoint was configured.
7. Create a disposable PVC, write data, reschedule the consumer, verify data and then test a planned storage-node evacuation. Confirm Longhorn has the configured healthy replica count.
8. Verify both CNPG clusters have their intended number of healthy instances on distinct workload nodes. Exercise a planned primary switchover and an off-cluster backup/restore.
9. Grant one user Longhorn only; verify Hubble and inventory remain denied. Revoke access and verify the documented session/revocation behavior.
10. Exercise the identity guide with real users/actors. A missing subject grant, actor grant or delegation tuple must deny the API. Wrong audience/issuer and invalid/expired tokens must fail. Stop OpenFGA and verify that access fails closed.
11. On each GPU model, reboot and verify the active driver/device nodes. After selecting an operator/device plugin, run a real vendor compute workload and confirm advertised GPU resources.

Hardware, firewall, LAN/VLAN, actual GPU generation, public DNS and off-site backup behavior cannot be proven by manifest tests. Record these outcomes for each site. The repository is a configured base with explicit prerequisites, not a claim that an unseen production cluster has already been deployed or validated.
