# Security checklist

Use the sections that match what the diff touches. Each unchecked item that applies is a finding.

## Threat model first
- [ ] List the trust boundaries the change crosses: users, files, networks, other services, model output.
- [ ] For each boundary, ask what an attacker controls and what they could reach.

## Secrets
- [ ] No keys, tokens, passwords or connection strings in code, tests, fixtures, logs or docs.
- [ ] Secrets come from a vault, managed identity or environment, never committed config.
- [ ] `.gitignore` covers new local secret files; no secrets in the diff history.

## Authentication and authorisation
- [ ] Every protected path checks authorisation on the server, not only in the UI.
- [ ] Users cannot reach other users' or tenants' resources by changing an ID.
- [ ] Sessions and tokens expire, are scoped, and cookies are `HttpOnly`, `Secure` and `SameSite`.
- [ ] Passwords use bcrypt, scrypt or argon2; sign-in and reset endpoints are rate limited.

## Input and output
- [ ] Untrusted input is validated at the boundary by type, length, range and format, using allowlists.
- [ ] Queries are parameterised; no string-built SQL, OData, KQL or LDAP filters.
- [ ] No untrusted input in shell commands, `Invoke-Expression`, `eval`, file paths or templates.
- [ ] HTML output is encoded; no raw `innerHTML` with untrusted data.
- [ ] Uploads are limited by size and type and stored outside the web root.
- [ ] Redirects and server-side fetches of user-supplied URLs use an allowlist (SSRF).

## Data protection
- [ ] Sensitive fields are excluded from responses, logs, telemetry and error messages.
- [ ] Data is encrypted in transit (TLS) and at rest where required.
- [ ] Personal data is limited to what is needed and handled under the applicable rules.

## Infrastructure and config
- [ ] Least privilege for identities, service principals, pipelines and role assignments.
- [ ] No public network exposure, open firewall rules or anonymous storage access unless intended.
- [ ] Security headers (CSP, HSTS, frame options) and CORS restricted to known origins.
- [ ] Errors shown to users are generic; details go to logs only.
- [ ] Pipeline variables and service connections holding secrets are marked secret and scoped.

## Dependencies and supply chain
- [ ] New dependencies are needed, maintained and pinned to exact versions.
- [ ] No known CVEs (`npm audit`, `dotnet list package --vulnerable`, `pip-audit` or equivalent).
- [ ] Check for typosquats, install scripts and unexpected download sources.

## AI and agent features
- [ ] Model output is untrusted: never passed to shell, SQL, `eval`, file paths or HTML unchecked.
- [ ] Permissions are enforced in code, not by the system prompt.
- [ ] No secrets or other tenants' data in the context window.
- [ ] Tool access is scoped, and destructive actions need confirmation.
- [ ] Token, rate and recursion limits are set.
