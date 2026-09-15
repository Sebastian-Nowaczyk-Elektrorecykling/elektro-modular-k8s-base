write a FluxCD repository that uses k3s with Cilium and Longhorn in lieu of its bundled components
it should also include Cloud Native Postgres

cluster should expose DNS with configurable fallback that has following scheme:
- top domain is .internal
- administration tools are in .admin.internal
- IDP test deployments are in .test.internal
- IDP staging deployments are in .staging.internal
- user-facing applications including production versions of IDP applications are under .internal

cluster should be configured to have a gateway that talks to LAN the nodes are in with domain .internal
cluster should be ready to have another gateway that responds to a preexisting domain

cluster should include a solution to authn of users, autonomously operating agents and agents working on behalf of a user or another agent
cluster should preferably use OpenFGA as I want to later use it for custom authorization
do a broad survey of authn solutions to find alternatives to mainstream software that may fit better
configure authn so that each service can be independently granted to a user

include scripts that prepare and configure a computer with freshly installed Debian 13 (they are free to reconfigure destructively anything on the system):
- pure controller node that serves only as network gateway and k8s controller
- pure worker
- worker-controller hybrid (bootstrap and join versions)
- removal of a node from cluster (worker and controller/hybrid versions)
- administrator workstation
scripts for worker and hybrid nodes should also install prerequisites for running GPU workloads in the cluster
all vendors available in the repository should be taken into account and their software installed so that future GPU cluster software can start

document how to configure Windows and Linux machines to use the exposed DNS
ensure that a computer inside the LAN can reach the addresses advertised by DNS and it should get routed properly without extra configuration of the LAN
