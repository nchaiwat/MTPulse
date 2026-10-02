# CIAM Mode B — setup and acceptance

This feature is not deployed. Production remains the pre-authentication release.
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
