"""Structured, allowlisted authentication audit events. Never accepts raw request bodies."""

import json
from time import perf_counter

from sqlalchemy.orm import Session

from app.models import AuthUser, TransactionLog

EVENTS = {
    "ad_gateway_test": (
        "CFG-03",
        "system_setting",
        "ad_gateway_test",
        "success",
        "ทดสอบบัญชีกับ AD Gateway",
    ),
    "auto_provision": (
        "SSO-03",
        "ciam_sso",
        "auto_provision_user",
        "info",
        "สร้างบัญชีอัตโนมัติจาก Central IAM",
    ),
    "account_deactivated": (
        "SSO-04",
        "ciam_sso",
        "account_deactivated",
        "warning",
        "ปฏิเสธการเข้าสู่ระบบ: บัญชีถูกระงับ",
    ),
    "break_glass_toggle": (
        "BG-01",
        "security_break_glass",
        "toggle_break_glass",
        "warning",
        "สลับสถานะโหมดฉุกเฉิน",
    ),
    "settings_changed": (
        "CFG-01",
        "system_setting",
        "update_ciam_settings",
        "success",
        "แก้ไขการตั้งค่า Central IAM / AD",
    ),
    "user_created": ("USR-01", "user_management", "user_created", "success", "สร้างบัญชีผู้ใช้"),
    "user_updated": ("USR-02", "user_management", "user_updated", "success", "แก้ไขสิทธิ์หรือสถานะผู้ใช้"),
    "ad_binding_changed": (
        "USR-03",
        "user_management",
        "ad_binding_changed",
        "success",
        "แก้ไขบัญชี AD ที่เชื่อมต่อ",
    ),
    "ciam_account_linked": (
        "USR-04",
        "user_management",
        "ciam_account_linked",
        "success",
        "เชื่อมบัญชี CIAM อัตโนมัติ",
    ),
    "secret_revealed": (
        "SEC-01",
        "system_setting",
        "secret_revealed",
        "success",
        "ผู้ดูแลระบบเปิดดู Secret",
    ),
    "connection_test": (
        "CFG-02",
        "system_setting",
        "connection_test",
        "success",
        "ทดสอบการเชื่อมต่อ CIAM",
    ),
    "logout": ("AUTH-03", "authentication", "logout", "success", "ออกจากระบบ"),
    "password_changed": (
        "SEC-02",
        "user_management",
        "password_changed",
        "success",
        "เปลี่ยนรหัสผ่าน Local Admin",
    ),
    "password_change_failed": (
        "SEC-03",
        "user_management",
        "password_change_failed",
        "failed",
        "เปลี่ยนรหัสผ่าน Local Admin ไม่สำเร็จ",
    ),
    "local_admin_bootstrap": (
        "USR-05",
        "user_management",
        "local_admin_bootstrap",
        "success",
        "ตั้งค่าบัญชี Local Admin บน Server",
    ),
}
USER_FIELDS = ("id", "username", "role", "active", "ad_username", "ad_enabled", "ciam_linked")


def record(session: Session, action: str, actor: str, source: dict):
    context = session.info.get("audit_context", {})
    details = {key: context.get(key) for key in ("ip", "peer_ip", "request_method", "request_path")}
    details["ip_source"] = context.get("ip_source", "server_observed")
    provider = source.get("provider", context.get("provider"))
    user = session.get(AuthUser, actor[5:]) if actor.startswith("user:") else None
    if user:
        actor = "user:" + user.username
        details.update(username=user.username, roles={"role": user.role}, ciam_issuer=user.issuer)
    if provider:
        details["provider"] = provider
    if action in ("login_success", "login_failed"):
        success = action == "login_success"
        if provider == "sso":
            event = (
                "SSO-01" if success else "SSO-02",
                "ciam_sso",
                action,
                "success" if success else "failed",
                "เข้าสู่ระบบผ่าน Central IAM SSO สำเร็จ" if success else "การยืนยันตัวตน SSO ล้มเหลว",
            )
            details["auth_method"] = "OIDC_PKCE_S256"
        elif provider == "ad" and source.get("break_glass_active") and success:
            event = (
                "BG-02",
                "security_break_glass",
                "fallback_ad_login",
                "success",
                "เข้าสู่ระบบผ่าน AD ในโหมดฉุกเฉิน",
            )
        else:
            event = (
                "AD-01"
                if provider == "ad" and success
                else "AD-02"
                if provider == "ad"
                else "LOCAL-01"
                if success
                else "LOCAL-02",
                "authentication",
                action,
                "success" if success else "failed",
                "เข้าสู่ระบบสำเร็จ" if success else "เข้าสู่ระบบไม่สำเร็จ",
            )
        if not success:
            session.info["login_failure_logged"] = True
    else:
        event = EVENTS.get(action)
        if not event:
            return
    code, category, event_action, status, message = event
    for key in (
        "username",
        "error",
        "stage",
        "http_status",
        "gateway",
        "break_glass_active",
        "prev_state",
        "key",
        "user_id",
        "tested_username",
        "gateway_status",
        "mtpulse_status",
        "app_id",
        "auth_method",
    ):
        if key in source:
            details[key] = source[key]
    if action == "auto_provision":
        actor = "system:ciam"
        details["group_assigned"] = "viewer"
        details["claims"] = {"username": user.username, "email": user.email} if user else {}
    if action == "settings_changed":
        before, after = source.get("before", {}), source.get("after", {})
        details["changed_fields"] = [key for key in after if before.get(key) != after[key]]
        for key, flag in (
            ("ciam_client_secret", "secret_changed"),
            ("ciam_ad_secret", "ad_secret_changed"),
        ):
            if source.get(flag):
                details["changed_fields"].append(key)
    if action in ("user_created", "user_updated"):
        for key in ("before", "after"):
            values = source.get(key, source if key == "after" else {})
            details[key] = {k: values[k] for k in USER_FIELDS if k in values}
    if action == "ad_binding_changed":
        details.update(before=source.get("before"), after=source.get("after"))
    if action == "break_glass_toggle":
        details["break_glass_active"] = source.get("active")
        # Reason is a deliberate admin-entered audit note, not an exception/payload dump.
        details["reason"] = str(source.get("reason", ""))[:300]
        status = "warning" if source.get("active") else "success"
        message += ": ENABLED" if source.get("active") else ": DISABLED"
    if action in ("connection_test", "ad_gateway_test"):
        status = source.get("status", "failed")
    if action == "ad_gateway_test":
        target = source.get("tested_username") or "ไม่ระบุบัญชี (ข้อมูลไม่ผ่านการตรวจสอบ)"
        message = "ทดสอบบัญชี AD: " + target
    elif details.get("username"):
        message += ": " + str(details["username"])
    started = context.get("started")
    session.add(
        TransactionLog(
            event_code=code,
            category=category,
            action=event_action,
            status=status,
            message=message[:500],
            details=json.dumps(details, ensure_ascii=False),
            records_count=1 if action in ("auto_provision", "user_created", "user_updated") else 0,
            duration_ms=max(0, int((perf_counter() - started) * 1000)) if started else 0,
            triggered_by=actor[:220],
        )
    )
