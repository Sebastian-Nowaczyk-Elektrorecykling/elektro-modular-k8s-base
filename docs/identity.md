# Users, agents and service authorization

authentik handles authentication; OpenFGA supplies the extensible authorization graph. The default dashboards use one authentik group per service. The inventory example additionally checks OpenFGA on each API request. This separates account existence from permission to use any particular service.

| Service | Host | Access gate |
| --- | --- | --- |
| Identity administration | `auth.admin.internal` | authentik administrator roles; bootstrap recovery account initially |
| Longhorn | `longhorn.admin.internal` | `service-longhorn` group; embedded authentik proxy |
| Hubble | `hubble.admin.internal` | `service-hubble` group; embedded authentik proxy |
| Inventory API and its CLI | `inventory.internal` | `service-inventory` for token issuance, plus OpenFGA `service:inventory` |
| OpenFGA administration | ClusterIP only | Administrator Kubernetes access plus API credential |
| Kubernetes/CNPG administration | Kubernetes API | Kubernetes RBAC; independent of application sign-in |

No dashboard group or OpenFGA access tuple is populated automatically. Platform authentication endpoints remain reachable so users can sign in. Administrative RBAC inside authentik still governs its console; granting Longhorn does not grant identity administration.

## Grant and revoke access

Create named users in the authentik console. Use immutable UUIDs for OpenFGA; usernames can change.

```bash
python3 scripts/identity-admin.py users
python3 scripts/identity-admin.py grant alice longhorn
python3 scripts/identity-admin.py grant alice inventory
python3 scripts/fga.py grant ALICE_UUID inventory
```

A dashboard grant does not imply access to other dashboards. To revoke inventory access immediately, delete its graph grant, then remove the token-issuance group:

```bash
python3 scripts/fga.py revoke ALICE_UUID inventory
python3 scripts/identity-admin.py revoke alice inventory
```

Longhorn/Hubble proxy access is session-based. Group revocation may be delayed by an existing session/token (configured access-token lifetime: five minutes); terminate the user's sessions for urgent revocation. OpenFGA checks use higher consistency and do not cache grants in the example API.

The inventory service demonstrates authorization decisions; it has no business data and exposes only `/` plus `/healthz`. Each protected request validates the exact access token through authentik introspection, then checks issuer, audience, expiry, required scope and immutable subject. Opaque refresh tokens are rejected. Invalid claims fail closed; an unavailable identity/authorization backend produces a service error, never access.

For human API access, on a workstation with browser access and trusted internal CA:

```bash
python3 scripts/user-token.py --output .local/alice.access
python3 scripts/call-api.py .local/alice.access
```

The public CLI uses authorization code plus S256 PKCE, state validation and an exact localhost callback. It receives no confidential client secret.

## Autonomous agents

Create a service account with an expiring credential, then independently grant it the service:

```bash
python3 scripts/identity-admin.py actor indexer --days 30
python3 scripts/identity-admin.py grant indexer inventory
python3 scripts/fga.py grant INDEXER_UUID inventory
python3 scripts/agent-token.py .local/actor-indexer.json --output .local/indexer.access
python3 scripts/call-api.py .local/indexer.access
```

Each agent gets its own app-password credential; access tokens last five minutes. The credential is written to a private local JSON file. Move it into the agent's secret store, never a container image, source repository or command-line argument. Rotate/revoke that credential in authentik and remove its FGA grants when retiring the agent. Credential expiration does not delete the service account or old FGA tuples; clean those up too.

The `actor` command without `--parent` deliberately creates a standard service account. Live testing exposed an authentik 2026.8.2 audit-serialization error for parentless Actor objects: [the pinned event serializer](https://github.com/goauthentik/authentik/blob/version/2026.8.2/authentik/events/utils.py) dereferences their missing parent. Parent-bound Actors implement delegation; ordinary service accounts implement autonomous operation. Both have unusable interactive passwords, individually expiring app-password credentials, and independent service grants. An autonomous service account can be the parent of a delegated Actor.

## An agent acting for a user

```bash
python3 scripts/identity-admin.py actor assistant-alice --parent alice --days 30
python3 scripts/identity-admin.py grant assistant-alice inventory
python3 scripts/fga.py grant ASSISTANT_UUID inventory
python3 scripts/fga.py delegate ASSISTANT_UUID ALICE_UUID inventory
python3 scripts/agent-token.py .local/actor-assistant-alice.json \
  --subject-token-file .local/alice.access --output .local/delegated.access
python3 scripts/call-api.py .local/delegated.access
```

The operator exchange example reads the confidential inventory client credential from `.local/identity-clients.json`. Keep it with a trusted backend/operator, not a browser or arbitrary third-party agent. A production agent service should have its own confidential client and a narrowly reviewed provider trust relationship. Application policies reject token exchange without explicit actor parameters; possession of the provider secret is not permission to impersonate silently.

The resulting token has the user in `sub` and the acting Actor in `act.sub`. The API requires all three conditions:

1. The subject has `can_access` on the service.
2. The actor has `can_access` on the same service.
3. The actor has `can_act` on `delegation:SERVICE/SUBJECT_UUID`.

The delegation object's `target` relation binds it to that service. Revoking any necessary tuple denies subsequent requests. A delegation never creates new service rights. A user or agent must already possess legitimate subject/actor tokens; adding graph tuples cannot mint identity tokens.

## An agent acting for another agent

Create a child Actor with the existing agent as parent, grant the child the service, and add a delegation tuple whose subject is the parent agent's UUID. Obtain the parent's **own** access token, then pass that as `--subject-token-file` with the child's credential file. The CI contract tests exercise this exact parent-agent/child-agent exchange.

The selected authentik version records the immediate actor and subject. It does not promise an arbitrarily deep, cryptographically preserved actor history. In particular, do not pass an already delegated user token to a child bound to its parent agent and assume a full human→agent→agent chain will be preserved. Use explicit immediate delegations and correlate audit events, or add a separately designed delegation broker when end-to-end chain provenance is required. The API rejects nested `act` structures rather than silently discarding history.

## Extend authorization

The [JSON model](../platform/openfga/model.json) is directly accepted by OpenFGA; [the DSL](../platform/openfga/model.fga) makes it easier to review. Extend it with resource types and relations in new immutable authorization models. Update the check proxy's model ID deliberately and test both grants and denials. Workloads only reach `/check`; its store/model and write-capable credential are held in the identity namespace.

Add an equivalent check after validated authentication in each custom application. OpenFGA does not enforce anything merely because it is installed. Never accept user-supplied `X-User`, `sub` or `act` headers as identity. The dashboard backends have ingress policies allowing only authentik, and their Gateway routes point to the authenticated proxy.

Sources: [authentik token exchange](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/token_exchange/), [machine authentication](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/machine_to_machine/), and [the pinned Actor model](https://github.com/goauthentik/authentik/blob/version/2026.8.2/authentik/core/models.py). The integration code is deliberately tied to authentik 2026.8.2; run the container contract test before changing that version.
