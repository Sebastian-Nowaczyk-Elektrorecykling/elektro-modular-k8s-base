# Add applications and a second gateway

`idp-test`, `idp-staging` and `apps` are distinct namespaces with ingress denied by default. Choose hosts `NAME.test.internal`, `NAME.staging.internal` and `NAME.internal` respectively. Cluster namespaces have `gateway.internal/access=true`; attaching to the external Gateway requires a separate label.

Use the [inventory application](../apps/inventory/) as a bearer-token API example. It has a non-root container, resource requests/limits, health probes, a ClusterIP service, a Gateway HTTPRoute and an ingress policy allowing the Cilium gateway identity. Its CA and provider configuration are explicit Secrets. Copying the manifest alone does not configure another service's issuer/audience or OpenFGA permissions.

For an application with native OIDC, register a separate provider/client in authentik, use exact redirect URIs, bind a service-specific group, validate tokens for that service's issuer/audience and implement its authorization checks. Use separate clients for test, staging and production. Keep administrative client credentials in Secrets and disable grants the client does not use.

For a browser tool without OIDC, copy the Longhorn pattern in `platform/identity-config/platform.yaml`: create a new empty service group, ProxyProvider, Application and group binding, then add that provider to the embedded outpost. Set `external_host` to the intended hostname and `internal_host` to its ClusterIP service. Point the new HTTPRoute to `authentik-server`, not the unprotected backend. Add a policy allowing only authentik to reach the backend. Reconcile and confirm that an authenticated but ungranted user is denied.

The helper `identity-admin.py` intentionally knows only the included services. For new services, manage their group membership through authentik or extend the helper's allowed service list together with the manifests. Use OpenFGA's API/model for fine-grained resource permissions in custom applications.

Create a new Flux Kustomization in `clusters/lan/reconciliation.yaml` pointing to the application's directory. Depend on its actual controllers, storage and identity configuration. Include `postBuild.substituteFrom: cluster-settings` if using variables. Keep each application separate so a rollout failure does not block unrelated services.

## Existing external domain

The [external Gateway example](../examples/external-gateway/) is intentionally excluded from the active Flux root. It uses the separately reserved LAN address `EXTERNAL_GATEWAY_ADDRESS`, a separately supplied `external-domain-tls` Secret and an explicit hostname `EXTERNAL_DOMAIN`.

1. Set `external_domain` to the existing hostname and regenerate/commit site settings.
2. Provision a valid TLS certificate for that hostname in `networking/external-domain-tls`. Use your existing PKI or a site-specific cert-manager issuer. Public ACME DNS-01 needs your DNS provider credentials; HTTP-01 needs the appropriate public routing.
3. Add a Flux Kustomization for `./examples/external-gateway`, depending on `lan` and `namespaces`, with cluster-settings substitution.
4. Label only an intended namespace `gateway.external/access=true` and create an HTTPRoute referencing Gateway `external`, namespace `networking`, section `https`.
5. Point existing DNS/reverse-proxy infrastructure at this Gateway and verify external access independently.

The example hostname is exact. To support multiple subdomains, add a wildcard listener/certificate or individual listeners, and explicit application hostnames. Never reuse the `.internal` private wildcard certificate for a public hostname.

For LAN-only use of the preexisting domain, have your existing DNS return the external LAN VIP. For Internet access, an upstream NAT/reverse proxy/tunnel must already be able to reach it. This repository does not publish your services to the Internet or alter an existing public DNS zone. Keep administration routes attached only to the internal Gateway.
