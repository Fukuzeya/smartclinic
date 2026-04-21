# ADR-0011 — Keycloak OIDC for authentication and RBAC

- Status: Accepted
- Date: 2026-04-14
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: security, identity, rbac

## Context and Problem Statement

Clinical data is sensitive. Access to every endpoint must be
authenticated and authorised, and a user's clinical role
(receptionist, doctor, pharmacist, accounts, lab technician) must
drive what operations they can perform. We need:

- A login flow a human can exercise (for the demo and for the
  Angular SPA).
- Standard tokens services can validate without hitting the IdP on
  every request.
- A place to add MFA later without ripping out the model.
- No home-grown password storage.

## Decision Drivers

- Standards-based (OIDC + OAuth 2.1) so any future front-end or
  integration fits.
- Low operational overhead for a student-laptop stack.
- Teach/demo the reality of federated identity, not a toy
  hand-rolled `/login`.

## Considered Options

1. **Keycloak 25** — realm-per-tenant OIDC server.
2. **Auth0 / Okta / Cognito** — hosted.
3. **Ory Kratos + Hydra** — modern, headless.
4. **Custom** — FastAPI + `passlib` + JWT.

## Decision Outcome

Chosen option: **Option 1 — Keycloak 25 self-hosted**.

Topology:
- Realm `smartclinic`.
- Confidential client `smartclinic-api` for the FastAPI services
  (service accounts, direct access grants for the demo).
- Public client `smartclinic-web` with PKCE for the Angular SPA.
- Realm roles: `receptionist`, `doctor`, `pharmacist`, `accounts`,
  `lab_technician`.
- Role → route mapping enforced per service via shared helpers
  `require_role` / `require_any_role` (FastAPI dependency).

Services validate tokens **offline** against the JWKS endpoint,
cached with a TTL. The `KeycloakJwtValidator` in the shared kernel
checks `iss`, `aud`, `exp`, and extracts realm roles (from
`realm_access.roles`) and resource roles (from
`resource_access[client_id].roles`).

### Positive Consequences
- Standards-based; any Angular library, Postman, or `curl` can
  authenticate.
- MFA, social login, user federation, password policy — all
  configurable without code changes.
- The realm is declarative (`ops/keycloak/smartclinic-realm.json`)
  and checked into the repo.

### Negative Consequences
- Keycloak's startup is slow (~20–30 s); compose healthchecks make
  this visible, not fatal.
- Realm JSON is intricate; we keep ours minimal and document it.
- Adds a container.

## Pros and Cons of the Options

### Keycloak
- Good, because standard, open, configurable, stateful in Postgres.
- Bad, because startup cost.

### Hosted IdP
- Good, because zero ops.
- Bad, because inappropriate for a student-local demo and needs real
  credentials / tenants.

### Ory
- Good, because modern.
- Bad, because two separate services (Kratos + Hydra) to run.

### Custom
- Bad. Security anti-pattern in 2026. Hard no.

## Links
- ADR-0002, ADR-0010.
- OpenID Connect Core 1.0.
- Keycloak 25 release notes.
