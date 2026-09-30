import os
import time
from datetime import datetime, date
from collections import defaultdict
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# -------------------------------------------------------------------
# In-memory per-minute rate tracker
# { session_id: [timestamp, timestamp, ...] }
# -------------------------------------------------------------------
_minute_tracker: dict[str, list[float]] = defaultdict(list)


def _check_per_minute(session_id: str, limit: int) -> bool:
    """Returns True if allowed, False if rate limited."""
    now = time.time()
    window = 60  # 1 minute
    timestamps = _minute_tracker[session_id]

    # Remove timestamps older than 1 minute
    _minute_tracker[session_id] = [t for t in timestamps if now - t < window]

    if len(_minute_tracker[session_id]) >= limit:
        return False

    _minute_tracker[session_id].append(now)
    return True


# -------------------------------------------------------------------
# Fetch package limits for a client
# -------------------------------------------------------------------
def get_package_limits(client_id: str) -> dict | None:
    try:
        result = (
            supabase
            .table("clients")
            .select("package_slug, is_active, messages_used, monthly_quota, quota_reset_date, packages(monthly_quota, per_user_daily_limit, per_session_limit, per_minute_limit, is_trial, is_free)")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
            .data
        )
        if not result:
            return None
        return result[0]
    except Exception as e:
        print(f"[Rate limiter - get_package_limits error]: {e}")
        return None


# -------------------------------------------------------------------
# Check and update per-session message count
# -------------------------------------------------------------------
def _get_session_count_today(session_id: str, client_id: str) -> int:
    try:
        today = date.today().isoformat()
        result = (
            supabase
            .table("usage_logs")
            .select("message_count")
            .eq("session_id", session_id)
            .eq("date", today)
            .limit(1)
            .execute()
            .data
        )
        return result[0]["message_count"] if result else 0
    except Exception as e:
        print(f"[Rate limiter - session count error]: {e}")
        return 0


def _increment_usage(session_id: str, client_id: str):
    """Increment usage_logs for session and messages_used for client."""
    try:
        today = date.today().isoformat()

        # Upsert usage log
        existing = (
            supabase
            .table("usage_logs")
            .select("id, message_count")
            .eq("session_id", session_id)
            .eq("date", today)
            .limit(1)
            .execute()
            .data
        )

        if existing:
            supabase.table("usage_logs").update({
                "message_count": existing[0]["message_count"] + 1,
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", existing[0]["id"]).execute()
        else:
            supabase.table("usage_logs").insert({
                "client_id": client_id,
                "session_id": session_id,
                "date": today,
                "message_count": 1
            }).execute()

        # Increment client messages_used
        supabase.rpc("increment_messages_used", {"p_client_id": client_id}).execute()

    except Exception as e:
        print(f"[Rate limiter - increment_usage error]: {e}")


# -------------------------------------------------------------------
# Main check — call this before processing every message
# Returns dict with allowed: bool and reason/message on denial
# -------------------------------------------------------------------
def check_limits(client_id: str, session_id: str) -> dict:
    data = get_package_limits(client_id)

    if not data:
        return {"allowed": False, "reason": "client_not_found", "message": None}

    # Client suspended
    if not data.get("is_active", True):
        return {
            "allowed": False,
            "reason": "client_suspended",
            "message": "This service is currently unavailable."
        }

    pkg = data.get("packages") or {}
    monthly_quota = pkg.get("monthly_quota", 100)
    per_user_daily = pkg.get("per_user_daily_limit", 20)
    per_session = pkg.get("per_session_limit", 10)
    per_minute = pkg.get("per_minute_limit", 5)
    is_trial = pkg.get("is_trial", False)

    # Check quota reset
    _check_and_reset_quota(client_id, data.get("quota_reset_date"))

    # 1. Client monthly quota
    messages_used = data.get("messages_used", 0)
    if monthly_quota < 999999 and messages_used >= monthly_quota:
        if is_trial:
            return {
                "allowed": False,
                "reason": "trial_quota_exceeded",
                "message": "You've used your free trial messages. Upgrade to continue — claribizz.com/pricing"
            }
        return {
            "allowed": False,
            "reason": "quota_exceeded",
            "message": "Our support is temporarily unavailable. Please try again later."
        }

    # 2. Per-minute rate limit
    if not _check_per_minute(session_id, per_minute):
        return {
            "allowed": False,
            "reason": "rate_limited",
            "message": "Please slow down — wait a moment before sending again."
        }

    # 3. Per-session daily limit
    session_count = _get_session_count_today(session_id, client_id)
    if session_count >= per_session:
        return {
            "allowed": False,
            "reason": "session_limit",
            "message": "You've reached your message limit for this session. Please try again tomorrow."
        }

    # 4. Per-user daily limit (same session = same user for widget)
    if session_count >= per_user_daily:
        return {
            "allowed": False,
            "reason": "daily_limit",
            "message": "You've reached your daily message limit. Come back tomorrow!"
        }

    # All checks passed — increment usage
    _increment_usage(session_id, client_id)

    # Check if quota alert should be sent
    _check_quota_alert(client_id, messages_used + 1, monthly_quota)

    return {"allowed": True, "reason": None, "message": None}


# -------------------------------------------------------------------
# Quota reset — resets messages_used when reset date is passed
# -------------------------------------------------------------------
def _check_and_reset_quota(client_id: str, quota_reset_date):
    try:
        if not quota_reset_date:
            return
        reset_date = date.fromisoformat(str(quota_reset_date)[:10])
        if date.today() >= reset_date:
            # Reset and set next reset date 30 days from now
            from datetime import timedelta
            next_reset = (date.today() + timedelta(days=30)).isoformat()
            supabase.table("clients").update({
                "messages_used": 0,
                "quota_reset_date": next_reset
            }).eq("client_id", client_id).execute()

            # Clear quota alerts so they fire again next cycle
            supabase.table("quota_alerts").delete().eq("client_id", client_id).execute()
    except Exception as e:
        print(f"[Rate limiter - reset quota error]: {e}")


# -------------------------------------------------------------------
# Quota alert — sends email at 80%, 95%, 100%
# -------------------------------------------------------------------
def _check_quota_alert(client_id: str, messages_used: int, monthly_quota: int):
    if monthly_quota >= 999999:
        return  # Enterprise — no alerts needed

    try:
        percent = (messages_used / monthly_quota) * 100
        thresholds = [80, 95, 100]

        for threshold in thresholds:
            if percent >= threshold:
                # Check if alert already sent for this threshold
                existing = (
                    supabase
                    .table("quota_alerts")
                    .select("id")
                    .eq("client_id", client_id)
                    .eq("threshold", threshold)
                    .limit(1)
                    .execute()
                    .data
                )
                if not existing:
                    # Mark as sent
                    supabase.table("quota_alerts").insert({
                        "client_id": client_id,
                        "threshold": threshold
                    }).execute()
                    # Send email
                    from core.email_handler import send_quota_alert
                    send_quota_alert(client_id, threshold, messages_used, monthly_quota)
    except Exception as e:
        print(f"[Rate limiter - quota alert error]: {e}")