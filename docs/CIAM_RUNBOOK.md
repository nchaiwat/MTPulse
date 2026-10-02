# CIAM Mode B — setup and acceptance

Production application activated on 2026-10-02 at c916ff3 with trusted local HTTPS and Local Admin. CIAM SSO and AD Login remain disabled until real credentials are entered and accepted.
CA/AD CS installation is a separate IT task. Do not enable production authentication
until trusted HTTPS/DNS and the registered CIAM client are ready. Do not paste the
client secret, local password, encryption key or certificate private key into Git/chat.

## Agreed behavior

- Callback: `https://wa-mtpulse.wa.net/auth/callback`.
- Mode B, no inbound directory or status webhooks. New accounts are Viewer.
- Local Admin is independent of AD and remains available via the small emergency link.
- Sessions have an absolute lifetime, initially 480 minutes (5–1440 configurable).
  Changing TTL affects new sessions. No refresh token or rolling renewal.
- SSO authorization requests fresh authentication (`prompt=login`, `max_age=0`), to
  avoid extending access indefinitely through an old provider session. Actual CIAM
  handling of these parameters must be verified during live acceptance.
- Local role/status changes revoke the affected user's sessions. CIAM-only offboarding
  is not immediate; existing sessions may last until expiry. Logout clears the local
  session and returns SSO users to the CIAM portal without globally logging out CIAM.
- User identity is `(issuer, subject)`, never email linking. Roles are local and are
  not elevated by CIAM claims. Active status is checked on every API request.
- Emergency access uses PBKDF2-SHA256 hashes, per-account/per-client throttling and audit.
- All business APIs require a session in `ciam` mode. Unknown API areas require Admin.
  Viewer: reports/downloads. Operator: individual uploads, mapping, corrective imports,
  DH prices and import logs. Folder uploads, UNC operations, monitoring, shared report
  preferences, system settings and scheduled operations retain Admin restrictions.

## Isolated staging setup

1. Use a separate database and containers. Never use the production DB for testing.
   Back up and verify path, byte size and SHA-256 before any production migration.
2. Install locked backend dependencies with `uv sync --frozen --group dev` and frontend
   dependencies with `npm ci`. New dependency: PyJWT 2.15.1 in uv.lock.
3. Configure infrastructure `MTPULSE_SETTINGS_ENCRYPTION_KEY` securely. Reuse the
   existing key on an upgraded deployment so existing FileShare/Telegram secrets work.
4. Run Alembic on staging: `python -m alembic upgrade head`. Expected head is
   `9da415c6d7e8`; the four auth tables and nullable unique AD binding are additive and no business rows are changed.
5. Create the first emergency admin from an interactive server console:
   `python -m app.bootstrap_admin <username>`. Password is entered twice via getpass,
   never a command argument. `--reset-password` explicitly resets a local admin and
   revokes that account's sessions. There is no public first-user/bootstrap API.
6. Set `MTPULSE_AUTH_MODE=ciam` on staging. The default legacy development mode bypasses
   auth for existing development workflows; it must never be used for CIAM rollout.
7. Serve the registered hostname via HTTPS with a certificate the browser trusts.
   `compose.ciam.yaml` is an opt-in overlay that sets `ciam` mode and mounts
   `deploy/nginx.ciam.conf` plus `certificates/fullchain.pem` and `privkey.pem` read-only.
   Certificate material is ignored by Git. The overlay requires those files; none are
   created or installed by this feature. It redirects HTTP to the fixed HTTPS hostname.
   Use with `compose.server.yaml`; do not activate on production without approval.
8. Log in with Local Admin. Settings → Global → Central IAM SSO: enter Client ID,
   Client Secret, provider base URL and callback; save. Empty secret retains existing
   ciphertext. No endpoint reveals the stored plaintext. New defaults keep SSO off.
9. Test connection checks discovery issuer/S256/endpoints and JWKS availability only;
   it does not establish validity of the client secret. Enable SSO once configured.
10. Complete a real CIAM login, assign operator/admin roles through Settings, and run
    the acceptance checks below before requesting production deployment.

All CIAM connection/runtime settings are in `system_settings`; each request reads
current values, avoiding stale multi-process memory caches. Encryption key and the
authentication deployment mode are infrastructure values, not provider credentials.
Settings saves invalidate pending login attempts. Discovery endpoints must remain
HTTPS and on the configured provider origin. Secure cookies are intentionally not
weakened for HTTP testing: use the automated HTTPS TestClient fixtures or TLS staging.

## Acceptance checks

- Anonymous requests cannot read reports, files, settings or import data; health stays public.
- Local Admin login, wrong-password throttling, password rotation, logout and reset.
- Real CIAM code flow: callback path, S256, nonce, signing key/issuer/audience checks,
  Viewer provisioning, denied/inactive user, expired/consumed/browser-mismatched state.
- Check provider key rotation and fresh-authentication behavior with the CIAM team.
- Viewer cannot mutate flags/mapping or read secrets; Operator can use mapping/single
  upload/corrective and cannot access Admin features. Test both fetch and XHR uploads.
- Settings secret rotation and SSO/break-glass toggles take effect across API processes.
- Absolute expiry, server-side revocation after role/status/password changes, logout
  returns to portal/local login appropriately, no token in localStorage or URLs.
- Seven-MT report totals/import behavior remain unchanged. Check GH partial coverage,
  HH sales versus stock, unmatched settings, mapping export/import and scheduled Worker.
- Keyboard and responsive layouts at 375/768/1024/1440; confirm shell does not overflow.
- AuditEvent `ciam_security` records login/provision/logout/settings/user/password and
  emergency actions. No passwords, provider tokens, authorization codes or secrets.
- Nginx suppresses callback access logging and sets no-referrer to avoid logging/leaking codes.

## Deployment and rollback

Deploy only from a reviewed commit after explicit production authorization. Record a
fresh DB backup (path/size/checksum), existing images/revision and schema head. Build
compatible API/Worker/Web, migrate once, bootstrap the local account before exposing
login, activate HTTPS overlay, and verify unauthenticated 401 and authenticated critical
APIs. Stop if the auth mode still reports development. Keep internal-only network access.

Prefer emergency Local Admin/break-glass for provider outages. Application rollback
point before this feature is main `a242b52` (deployed application `95b56ac`), but that
version has no authentication: reverting requires explicit review of the resulting
access exposure. Keep additive auth tables during rollback; do not automatically run
the destructive Alembic downgrade or restore an old production backup.

## Verification limits

Automated tests use an isolated SQLite database and locally generated RSA provider
fixtures; they do not prove that the registered CIAM client/secret works. PostgreSQL
concurrency and actual TLS/provider/browser acceptance must be checked on staging.
No production migrations, configuration changes, imports or deployments are part of
this development task. Browser automation currently fails with the existing Windows
`helper_unknown_error`; visual acceptance is pending unless separately recorded.

OIDC reference: https://openid.net/specs/openid-connect-core-1_0.html
JWT verification reference: https://pyjwt.readthedocs.io/en/stable/usage.html


## AD Gateway emergency extension — 2026-10-02

This supersedes the earlier Local-Admin-only scope. Owner approved LAN HTTP to
`http://192.168.12.11:3100/api/v2/login` (there is no v3), app ID `MTPULSE`.
The example secret ABCDE is NOT a credential and must never be configured as one.
Owner confirms blank required_group means unrestricted at the gateway. MTPulse
still admits only active CIAM accounts explicitly bound by an Admin beforehand.

Setup after the base CIAM/TLS/local-admin prerequisites:
1. Apply additive migration 9da415c6d7e8 after 8c9304b5c6d7. It adds nullable
   auth_users.ad_username and a unique index; existing identities/data remain intact.
2. Global Settings → CIAM: enter AD Gateway URL, AD App ID and the real AD Secret.
   Blank secret preserves the encrypted value. Reads expose configured-state only.
3. Under users, explicitly bind each CIAM account's AD sAMAccountName. Bindings are
   normalized to lowercase, unique, auditable and cannot target emergency Local Admin.
   Never infer a binding from matching usernames/email. Unbound AD users are rejected.
4. Admin enables break-glass with a reason. AD form is then available, SSO is paused,
   and the separate Local Admin form remains accessible. No automatic outage failover.
5. Test using an approved AD account: same CIAM user ID/role/status, fixed 480-minute
   default expiry. AD passwords are sent only to the configured gateway and are not
   stored or logged by MTPulse. HTTP within the LAN is the owner's explicit choice;
   that transport is not encrypted. Browser → MTPulse HTTPS/Secure cookies stay required.
6. Turn break-glass off: AD sessions are deleted and subsequent requests also check
   the current mode. Binding changes revoke affected AD sessions; gateway changes
   revoke all AD sessions. Role/status changes retain existing all-session revocation.

Gateway contract: JSON app_id, secret_key, username, password, UTC ISO timestamp;
accept only HTTP 200 + status="success" + data.username matching the requested binding.
Reject unexpected responses, redirects, wrong identity and service errors. A 10-second
HTTP timeout, no environment proxy, account/IP throttles and same-origin login guard
apply. Do not fabricate X-Forwarded-For from the IRM guide's VPS example: the inspected
v2 service checks the TCP peer IP. Configure the actual source IP in gateway registry.

Validation limits: TCP connectivity from wa-mtpulse API container to 192.168.12.11:3100
passed; this does NOT verify the real secret, allowed_ips acceptance or AD credentials.
The local ADSyncAgent/index.js copy returns status/data.username but its empty-group
check uses memberOf.some(...), which may reject a user with no listed memberships.
Confirm deployed gateway behavior with an approved test account; no changes were made
to ADSyncAgent, AD or its registry. Browser tool still fails to initialize; responsive
375/768/1024/1440 visual acceptance and PostgreSQL concurrency acceptance remain pending.

Rollback extension only: revert the AD feature application commit to 0c7039e while
keeping the additive nullable column. Disable emergency mode before rollback; old
application code does not enforce AD-provider mode checks. Do not drop auth tables or
restore old business-data backups as part of application rollback.


## Production activation — 2026-10-02

Owner explicitly approved deployment and a certificate without a CA VM. Deployed
c916ff3cddbaba2dead13ce5791fa0aef4958af7, using image tags mtpulse-api:ciam-c916ff3
(API/Worker) and mtpulse-web:ciam-c916ff3. Active compose command:
`docker compose -p mtpulse --env-file .env.server -f compose.server.yaml -f compose.ciam.yaml -f releases/c916ff3/compose.images.yaml ...`
Always include the TLS/image overlays. MTPULSE_AUTH_MODE=ciam is also persisted in
.env.server to prevent accidental development-mode bypass if an overlay is omitted.

Self-signed server certificate (CA:FALSE, serverAuth, SAN wa-mtpulse.wa.net) and RSA3072
private key are under /opt/mtpulse/certificates, key mode 600. No CA VM, domain-wide
GPO change or public exposure configured. Certificate validity ends 2027-10-02 04:27:29 UTC.
SHA256 4F6304A701BD71E3051EC03BA9EEBBE4D536ECCFFEB6C2D3CC69461B85394F9A.
Public certificate was verified and imported into CurrentUser\Root on this Windows
account only. Other employees need the same certificate trusted on their own machines.

Emergency admin mtpulse-emergency bootstrapped in production; only its password hash
is in PostgreSQL. Initial password delivered as a current-user DPAPI encrypted credential
file under D:/Downloads/MTPulse-Access with restricted directory ACL, never in Git/chat.
README.md and Show-Emergency-Login.ps1 in that directory explain local retrieval and
password rotation. Do not distribute the credential XML or server private key. Real
CIAM client secret and AD secret were NOT supplied; SSO/break-glass remain disabled.

Backup before additive migration: /opt/mtpulse/backups/before-ciam-f7f30a1-20261002T042136Z.dump,
213755414 bytes, SHA256 f47c870ad80a54d1f1076acd8e07f097d8b1347299a1989743f4115acda55506;
checksum reverified before upgrade. Production schema now 9da415c6d7e8.
HTTPS page/assets/health and Local Admin login/logout passed using OS certificate trust
(no TLS verification bypass). Anonymous reports return 401; cookie Secure/HttpOnly.
All seven MT report APIs returned 200. HH 2025-04-24 remained 22342.05 / 11; GH March
2025 gross remained 2734747.60 / 870; Sale Out available returned 200. API/Web/DB healthy,
Worker running. Live external CIAM/AD authentication and responsive visual acceptance
are still pending. Earlier statements that no production activation occurred describe
prior steps and are superseded by this section.

Rollback images retained: mtpulse-api:pre-ciam-95b56ac, mtpulse-web:pre-ciam-95b56ac,
mtpulse-worker:pre-ciam-95b56ac. A rollback to that pre-authentication release requires
explicit consideration of restored anonymous access and infrastructure auth mode;
do not downgrade/drop the additive auth schema or restore older business data.

## Saved secret display

Saved CIAM/AD secrets display ******** with an eye control. Owner explicitly authorized Admin on-demand reveal through POST /api/settings/ciam-sso/secrets/{client|ad}/reveal with CSRF, no-store and key-only audit. This supersedes the earlier statement that no endpoint reveals plaintext; ordinary settings GET still never reveals it. Visibility resets on hide, collapse/save/unmount or after 30 seconds. Use the separate Change action to replace a secret; leaving it untouched preserves the stored ciphertext. Other secret endpoints/policies are unchanged.


## User Management / AD always available — latest owner policy

This supersedes the emergency-only AD and explicit-manual-CIAM-link sections above.
Settings > Global > Central IAM SSO > User Management can create an account such as
Chaiwat.N, with display name, role, active status and AD permission. No local password
is created for these accounts. AD permission uses the existing unique normalized
ad_username binding (no schema change). Existing bound AD accounts remain allowed.
AD is available alongside CIAM whenever gateway settings are configured; break-glass
still suspends SSO, but does not disable/revoke AD. Disabling a user's AD permission,
changing role/status or gateway settings retains session revocation protections.

First verified CIAM login with matching preferred_username (trimmed/case-insensitive)
automatically links to an unlinked managed account, preserving user ID, role, status
and AD permission. It never links Local Admin, an already bound issuer/subject, an
ambiguous name or a disabled account; identity conflicts require Admin investigation.
A new CIAM identity with no matching account still provisions Viewer without AD
permission. Subsequent CIAM logins resolve the stable issuer/subject. Manual creation
and CIAM provision/link operations use a shared PostgreSQL transaction advisory lock.

Test on isolated staging: create a managed Operator with AD enabled, authenticate via
simulated Gateway outside emergency mode, disable AD and verify sessions revoked.
Then use a signed provider fixture with differently cased preferred_username; confirm
same user ID and role, deny disabled/local/already-linked identity collisions and
retain new-user Viewer provisioning. Real external provider/AD credential acceptance
must still be checked with an approved user; never create fake production test users.


## System Setting and Transaction Logs (2026-10-02)

Navigation separates ModernTrade Setting (Global and seven existing MT tabs) from
System Setting (Admin only). Central IAM / AD contains connection and emergency
settings; User Management contains accounts, AD permission and Local Admin password
change. Transaction Logs offers server-side date/category/status/actor filters,
pagination and read-only details. Unsaved System Setting edits prompt before leaving.

Apply additive migration ab1526d7e8f9 after 9da415c6d7e8 before starting the new API.
The new transaction_logs table follows specification fields plus event_code.
triggered_by permits 220 characters to preserve existing 200-character account names.
Existing audit_events remains intact; Legacy view shows established metadata only,
without fabricating status/IP or exposing unstructured old detail payloads.
No automatic retention deletion or remote log shipping is enabled.

Covered specification codes: SSO-01/02/03/04, BG-01/02 and CFG-01. Normal AD login
uses AD-01/02 (not BG-02); local login and user/security changes have separate codes.
Details are explicitly allowlisted; no passwords, secrets, token/code/PKCE/session
values are accepted. Failure reasons use sanitized exception type/stage/status.
IP is the server-observed ASGI client address; arbitrary forwarded headers are never
trusted by application logging. With the current Docker reverse proxy this can be the
proxy peer, rather than the employee PC. Original end-user IP attribution requires a
separately verified trusted-proxy configuration. Server-console events have no client IP.

Verify in isolated PostgreSQL: migrate, bootstrap fixture admin, log in, perform a
failed login, query logs as Admin, confirm Viewer denial and redaction. Compare both
metadata and persisted entries after the failed response. Production migration requires
fresh verified pg_dump. Code rollback target is protected release 6971a73; retain the
additive table/history on rollback, never run destructive downgrade on production.
