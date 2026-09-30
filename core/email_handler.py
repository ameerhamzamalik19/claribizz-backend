import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "alerts@claribizz.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", "alerts@claribizz.com")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@claribizz.com")

ENABLED = bool(SMTP_PASSWORD)  # Only send if credentials are configured


def _send(to: list[str], subject: str, html: str):
    if not ENABLED:
        print(f"[Email - SMTP not configured] Would send to {to}: {subject}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_FROM
        msg["To"] = ", ".join(to)
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_FROM, to, msg.as_string())

        print(f"[Email] Sent '{subject}' to {to}")

    except Exception as e:
        print(f"[Email error]: {e}")


def send_quota_alert(client_id: str, threshold: int, messages_used: int, monthly_quota: int):
    """Send quota alert to client owner + Claribizz admin."""
    try:
        from supabase import create_client
        supabase = create_client(
            os.getenv("SUPABASE_URL"),
            os.getenv("SUPABASE_KEY")
        )

        client = (
            supabase
            .table("clients")
            .select("business_name, owner_contact, package_slug")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
            .data
        )

        if not client:
            return

        client = client[0]
        business_name = client["business_name"]
        package = client["package_slug"].capitalize()
        percent = round((messages_used / monthly_quota) * 100)

        if threshold == 100:
            subject = f"⚠️ {business_name} — Quota Limit Reached"
            color = "#dc2626"
            headline = "You've used 100% of your monthly messages"
            message = f"""
                Your Claribizz chatbot has reached its monthly message limit
                ({messages_used}/{monthly_quota} messages used on the {package} plan).
                Your customers are currently seeing an upgrade prompt.
            """
            cta = "Upgrade Your Plan"
            cta_url = "https://claribizz.com/pricing"
        elif threshold == 95:
            subject = f"🔴 {business_name} — 95% of Quota Used"
            color = "#f59e0b"
            headline = "You've used 95% of your monthly messages"
            message = f"""
                Your Claribizz chatbot has used {messages_used} of {monthly_quota}
                messages this month on the {package} plan.
                You have approximately {monthly_quota - messages_used} messages remaining.
            """
            cta = "Upgrade Before You Run Out"
            cta_url = "https://claribizz.com/pricing"
        else:  # 80%
            subject = f"🟡 {business_name} — 80% of Quota Used"
            color = "#1c2b1e"
            headline = "You've used 80% of your monthly messages"
            message = f"""
                Your Claribizz chatbot has used {messages_used} of {monthly_quota}
                messages this month on the {package} plan.
                You have {monthly_quota - messages_used} messages remaining.
            """
            cta = "View Plans"
            cta_url = "https://claribizz.com/pricing"

        html = f"""
        <!DOCTYPE html>
        <html>
        <body style="margin:0;padding:0;background:#f5f4f0;font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;">
            <div style="max-width:560px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e8e6e0;">
                <div style="background:{color};padding:28px 32px;">
                    <div style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.5px;">Clari<span style="color:#c9a84c;">bizz</span></div>
                </div>
                <div style="padding:32px;">
                    <h2 style="font-size:18px;font-weight:700;color:#1a1a1a;margin:0 0 12px;">{headline}</h2>
                    <p style="font-size:14px;color:#555;line-height:1.7;margin:0 0 24px;">{message}</p>

                    <div style="background:#f5f4f0;border-radius:10px;padding:16px 20px;margin-bottom:24px;">
                        <div style="font-size:13px;color:#888;margin-bottom:4px;">Usage this month</div>
                        <div style="font-size:24px;font-weight:700;color:#1a1a1a;">{messages_used} / {monthly_quota} messages</div>
                        <div style="background:#e8e6e0;border-radius:4px;height:6px;margin-top:12px;">
                            <div style="background:{color};height:6px;border-radius:4px;width:{min(percent, 100)}%;"></div>
                        </div>
                    </div>

                    <a href="{cta_url}"
                       style="display:inline-block;background:#1c2b1e;color:#fff;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;">
                        {cta}
                    </a>

                    <p style="font-size:12px;color:#aaa;margin-top:24px;line-height:1.6;">
                        This is an automated alert from Claribizz for {business_name} (ID: {client_id}).
                        Your quota resets every 30 days from your signup date.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        # Send to both admin and client
        # Note: owner_contact is a phone number — in future replace with owner_email
        # For now just send to admin
        recipients = [ADMIN_EMAIL]

        # Admin-specific subject prefix
        admin_subject = f"[Claribizz Admin] {subject}"
        _send([ADMIN_EMAIL], admin_subject, html)

        print(f"[Quota alert] {threshold}% alert sent for client {client_id} ({business_name})")

    except Exception as e:
        print(f"[Email - send_quota_alert error]: {e}")