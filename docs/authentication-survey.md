# Authentication survey and selection

Reviewed 2026-09-15 against primary project documentation/source. This is a requirements-fit survey, not an independent security audit or a claim that every project was deployed and benchmarked. “Needs validation” means the necessary semantics were not established by this review; it does not mean the project cannot support them.

The important distinction for this cluster is between an agent having its own identity, a service receiving delegated access, and a token preserving who is acting. OAuth client credentials alone address only the first case. OpenFGA is useful for service/resource permission checks after authentication, but cannot replace the identity provider.

| Candidate | Where it fits well | Agent/delegation assessment | Decision for this base |
| --- | --- | --- | --- |
| **authentik** | Flexible workforce SSO, proxy protection for tools without OIDC, configuration through blueprints | Current release has explicit Actors and actor-bearing token exchange; parent matching constrains delegated identities. Group and API policy integration are straightforward. | **Selected**, with OpenFGA checks and a pinned-version contract test. New delegation feature warrants the explicit test gate. |
| **ZITADEL** | API-oriented organizations/projects, human and machine identities, PostgreSQL-backed operation | Documents RFC 8693 actor/subject tokens and audience reduction. Its impersonation permissions are powerful and need careful scoping or a broker. | Strong alternative, particularly for a developer platform built around projects and organizational roles. |
| **Keycloak** | Large integration ecosystem, established federation and enterprise protocols | Standard token exchange has a documented support matrix; do not assume actor-token delegation or arbitrary chains from the feature name. | Conventional fallback; compare exact exchange semantics before substitution. |
| **Kanidm** | Compact directory, modern cryptography, passkeys, group-controlled OAuth scopes and host identity | Service accounts are available; actor-bearing delegated agent workflows need additional validation/design. | Attractive alternative when human/host identity and operational simplicity outweigh native delegation requirements. |
| **Rauthy** | Lightweight Rust OIDC/OAuth provider, passkey emphasis, headless/CLI use and optional PostgreSQL | Promising for smaller deployments; exact actor/parent/delegation semantics need validation. | Shortlist for a lighter identity tier; not assumed compatible with this repository's contracts. |
| **Pocket ID** | Small passkey-focused OIDC deployment and user experience | Strong human sign-in focus; the complete autonomous/delegated-agent model needs validation. | Good narrower alternative for a human-only cluster, not sufficient evidence for this request's agent requirements. |
| **Authelia** | Human authentication at a reverse proxy, MFA and declarative access rules | OIDC capabilities exist, but proxy SSO does not itself supply a complete agent delegation model. | Practical for protected LAN tools; would require a separate agent identity/delegation layer here. |
| **Logto** | Application/customer identity, machine applications and API resources | Documents service-to-service token exchange preserving the original user and calling client. Do not assume that it preserves a nested `act` chain or agent-parent ownership. | Strong application-focused alternative; validate the agent-to-agent case and self-hosted feature availability. |
| **Ory Kratos + Hydra** | Composable identity and OAuth services with custom login/consent experiences | Machine and delegated OAuth flows are part of the architecture; assembling user, consent and authorization integration remains the operator's work. | Flexible option for a team building a custom identity product; more integration surface for this base. |
| **Casdoor** | Broad protocol/provider integration and UI-led identity administration | Agent-oriented integration exists; exact bounded delegation and revocation behavior need a targeted proof of concept. | Worth considering for an integration-heavy environment; not selected without those contracts. |
| **Dex** | OIDC federation in front of existing identity systems; Kubernetes SSO | Primarily a federation layer. Machine authentication is documented, but it is not a replacement for the full user/agent lifecycle selected here. | Useful if an authoritative identity system already exists. |
| **SPIFFE/SPIRE** | Attested workload identity and short-lived credentials | Excellent complement for service/agent workload identity; it does not provide browser login or user consent/delegation policy by itself. | Add later for workload attestation; combine with the identity provider and OpenFGA. |

The chosen configuration uses authentik's built-in proxy for Longhorn/Hubble and a separate OpenFGA example for custom APIs. That avoids requiring every administration tool to implement OIDC and leaves a clear path to application-specific authorization. Groups remain independently assignable for each service; the graph does not contain an automatic “all authenticated users” grant.

Selection tradeoffs: authentik is heavier than the smaller Rust/passkey-focused options, and its Actor/OBO capability is new in the selected release line. The repository therefore checks actual user-to-agent and agent-to-agent exchange, parent mismatch denial, missing-actor denial and permission revocation. Testing found that 2026.8.2's audit serializer fails for parentless Actors; this base uses ordinary service accounts with expiring credentials for autonomous agents and parent-bound Actors for delegation (see the [implementation note](identity.md#autonomous-agents)). It does not advertise complete nested provenance. ZITADEL is the strongest alternate implementation if organizational/project modeling or a dedicated delegation broker becomes the primary requirement.

Primary references:

- [authentik OAuth provider](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/) and [token exchange](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/token_exchange/)
- [ZITADEL token exchange](https://zitadel.com/docs/guides/integrate/token-exchange) and [projects](https://zitadel.com/docs/guides/manage/console/projects-overview)
- [Keycloak token exchange support matrix](https://www.keycloak.org/securing-apps/token-exchange)
- [Kanidm OAuth configuration](https://kanidm.github.io/kanidm/stable/integrations/oauth2.html) and [service accounts](https://kanidm.github.io/kanidm/stable/accounts/service_accounts.html)
- [Rauthy project documentation](https://github.com/sebadob/rauthy)
- [Pocket ID project documentation](https://github.com/pocket-id/pocket-id)
- [Authelia overview](https://www.authelia.com/overview/prologue/introduction/) and [OIDC](https://www.authelia.com/integration/openid-connect/introduction/)
- [Logto service-to-service delegation](https://docs.logto.io/developers/service-to-service-delegation)
- [Ory Hydra](https://www.ory.sh/docs/hydra)
- [Casdoor overview](https://casdoor.org/docs/overview)
- [Dex documentation](https://dexidp.io/docs/)
- [SPIRE concepts](https://spiffe.io/docs/latest/spire-about/spire-concepts/)

Future evaluation should repeat the same concrete tests against another provider rather than treating a protocol checkbox as equivalent behavior: per-service denial, signed audience/issuer validation, independent machine identities, explicit immediate actors, wrong-parent denial, revocation, recovery, and auditable user/actor attribution.
