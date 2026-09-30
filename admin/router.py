import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from supabase import create_client
from dotenv import load_dotenv
from admin.auth import (
    check_credentials,
    create_session_token,
    require_admin,
    COOKIE_NAME,
    COOKIE_MAX_AGE
)

load_dotenv()

router = APIRouter(prefix="/admin")

templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)


# -------------------------------------------------------------------
# LOGIN
# -------------------------------------------------------------------
@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": None}
    )


@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if check_credentials(username, password):
        token = create_session_token(username)
        response = RedirectResponse(url="/admin/dashboard", status_code=302)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            max_age=COOKIE_MAX_AGE,
            samesite="lax"
        )
        return response

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": "Invalid username or password"}
    )


@router.get("/logout")
def logout():
    response = RedirectResponse(url="/admin/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# -------------------------------------------------------------------
# DASHBOARD
# -------------------------------------------------------------------
@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    clients = (
        supabase
        .table("clients")
        .select("*")
        .execute()
        .data or []
    )

    sessions = (
        supabase
        .table("conversation_sessions")
        .select("*")
        .execute()
        .data or []
    )

    handoffs = [s for s in sessions if s.get("handoff_triggered") is True]

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "total_clients": len(clients),
            "total_sessions": len(sessions),
            "total_handoffs": len(handoffs)
        }
    )


# -------------------------------------------------------------------
# CLIENTS — LIST
# -------------------------------------------------------------------
@router.get("/clients", response_class=HTMLResponse)
def clients_list(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    clients = (
        supabase
        .table("clients")
        .select("*")
        .order("created_at", desc=True)
        .execute()
        .data or []
    )

    packages = (
        supabase
        .table("packages")
        .select("slug, name, is_active")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
        .data or []
    )

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients,
            "edit_client": None,
            "faqs": [],
            "widget": {},
            "packages": packages,
            "error": None
        }
    )


# -------------------------------------------------------------------
# CLIENTS — ADD
# -------------------------------------------------------------------
@router.post("/clients/add")
def add_client(
    request: Request,
    package_slug: str = Form("trial"),
    business_name: str = Form(...),
    business_description: str = Form(...),
    timings: str = Form(...),
    location: str = Form(...),
    pricing: str = Form(...),
    tone: str = Form(...),
    handoff_message: str = Form(...),
    owner_contact: str = Form(...),
    whatsapp_number: str = Form("")
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    new_client = {
        "client_id": str(uuid.uuid4())[:8],
        "package_slug": package_slug,
        "business_name": business_name,
        "business_description": business_description,
        "timings": timings,
        "location": location,
        "pricing": pricing,
        "tone": tone,
        "handoff_message": handoff_message,
        "owner_contact": owner_contact,
        "whatsapp_number": whatsapp_number
    }

    supabase.table("clients").insert(new_client).execute()
    return RedirectResponse(url="/admin/clients", status_code=302)


# -------------------------------------------------------------------
# CLIENTS — EDIT PAGE
# -------------------------------------------------------------------
@router.get("/clients/{client_id}/edit", response_class=HTMLResponse)
def edit_client_page(client_id: str, request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    client = (
        supabase
        .table("clients")
        .select("*")
        .eq("client_id", client_id)
        .single()
        .execute()
        .data
    )

    clients = (
        supabase
        .table("clients")
        .select("*")
        .order("created_at", desc=True)
        .execute()
        .data or []
    )

    faqs = (
        supabase
        .table("client_faqs")
        .select("*")
        .eq("client_id", client_id)
        .order("order_index")
        .execute()
        .data or []
    )

    widget = get_widget_config(client_id)

    packages = (
        supabase
        .table("packages")
        .select("slug, name, is_active")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
        .data or []
    )

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients,
            "edit_client": client,
            "faqs": faqs,
            "widget": widget,
            "packages": packages,
            "error": None
        }
    )


# -------------------------------------------------------------------
# CLIENTS — SAVE EDIT
# -------------------------------------------------------------------
@router.post("/clients/{client_id}/edit")
def edit_client(
    client_id: str,
    request: Request,
    package_slug: str = Form("trial"),
    business_name: str = Form(...),
    business_description: str = Form(...),
    timings: str = Form(...),
    location: str = Form(...),
    pricing: str = Form(...),
    tone: str = Form(...),
    handoff_message: str = Form(...),
    owner_contact: str = Form(...),
    whatsapp_number: str = Form("")
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    supabase.table("clients").update({
        "package_slug": package_slug,
        "business_name": business_name,
        "business_description": business_description,
        "timings": timings,
        "location": location,
        "pricing": pricing,
        "tone": tone,
        "handoff_message": handoff_message,
        "owner_contact": owner_contact,
        "whatsapp_number": whatsapp_number
    }).eq("client_id", client_id).execute()

    return RedirectResponse(
        url=f"/admin/clients/{client_id}/edit",
        status_code=302
    )


# -------------------------------------------------------------------
# CLIENTS — DELETE
# -------------------------------------------------------------------
@router.post("/clients/{client_id}/delete")
def delete_client(client_id: str, request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    # FAQs deleted automatically via ON DELETE CASCADE
    supabase.table("clients").delete().eq("client_id", client_id).execute()
    return RedirectResponse(url="/admin/clients", status_code=302)


# -------------------------------------------------------------------
# FAQS — ADD
# -------------------------------------------------------------------
@router.post("/clients/{client_id}/faqs/add")
def add_faq(
    client_id: str,
    request: Request,
    question: str = Form(...),
    answer: str = Form(...)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    existing = (
        supabase
        .table("client_faqs")
        .select("order_index")
        .eq("client_id", client_id)
        .order("order_index", desc=True)
        .limit(1)
        .execute()
        .data
    )
    next_index = (existing[0]["order_index"] + 1) if existing else 0

    supabase.table("client_faqs").insert({
        "client_id": client_id,
        "question": question,
        "answer": answer,
        "order_index": next_index
    }).execute()

    return RedirectResponse(
        url=f"/admin/clients/{client_id}/edit",
        status_code=302
    )


# -------------------------------------------------------------------
# FAQS — EDIT
# -------------------------------------------------------------------
@router.post("/clients/{client_id}/faqs/{faq_id}/edit")
def edit_faq(
    client_id: str,
    faq_id: str,
    request: Request,
    question: str = Form(...),
    answer: str = Form(...)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    supabase.table("client_faqs").update({
        "question": question,
        "answer": answer
    }).eq("id", faq_id).execute()

    return RedirectResponse(
        url=f"/admin/clients/{client_id}/edit",
        status_code=302
    )


# -------------------------------------------------------------------
# FAQS — DELETE
# -------------------------------------------------------------------
@router.post("/clients/{client_id}/faqs/{faq_id}/delete")
def delete_faq(client_id: str, faq_id: str, request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    supabase.table("client_faqs").delete().eq("id", faq_id).execute()

    return RedirectResponse(
        url=f"/admin/clients/{client_id}/edit",
        status_code=302
    )


# -------------------------------------------------------------------
# CONVERSATIONS
# -------------------------------------------------------------------
@router.get("/conversations", response_class=HTMLResponse)
def conversations(request: Request, client_id: str = None):
    redirect = require_admin(request)
    if redirect:
        return redirect

    clients = (
        supabase
        .table("clients")
        .select("client_id, business_name")
        .execute()
        .data or []
    )

    query = (
        supabase
        .table("conversation_sessions")
        .select("*")
        .order("updated_at", desc=True)
    )

    if client_id:
        query = query.eq("client_id", client_id)

    # Load all sessions — no limit
    sessions = query.execute().data or []

    # Ensure messages within each session are oldest to newest
    for session in sessions:
        if session.get("messages"):
            session["messages"] = sorted(
                session["messages"],
                key=lambda m: m.get("timestamp", "")
            )

    return templates.TemplateResponse(
        request=request,
        name="conversations.html",
        context={
            "sessions": sessions,
            "clients": clients,
            "selected_client": client_id
        }
    )


# -------------------------------------------------------------------
# WIDGET — GET SETTINGS (used in edit page)
# -------------------------------------------------------------------
def get_widget_config(client_id: str) -> dict:
    DEFAULT = {
        "primary_color": "#1c2b1e",
        "secondary_color": "#c9a84c",
        "position": "bottom-right",
        "greeting": "Hi! How can I help you today?",
        "bot_name": "Assistant",
        "is_active": True
    }
    try:
        widget_rows = (
            supabase
            .table("client_widgets")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
            .data
        )
        if widget_rows:
            return {**DEFAULT, **widget_rows[0]}
    except Exception:
        pass
    return DEFAULT


# -------------------------------------------------------------------
# WIDGET — SAVE SETTINGS
# -------------------------------------------------------------------
@router.post("/clients/{client_id}/widget")
def save_widget(
    client_id: str,
    request: Request,
    bot_name: str = Form(...),
    greeting: str = Form(...),
    primary_color: str = Form(...),
    secondary_color: str = Form(...),
    position: str = Form(...),
    is_active: str = Form("off")
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    config = {
        "client_id": client_id,
        "bot_name": bot_name,
        "greeting": greeting,
        "primary_color": primary_color,
        "secondary_color": secondary_color,
        "position": position,
        "is_active": is_active == "on"
    }

    # Upsert — insert if not exists, update if exists
    supabase.table("client_widgets").upsert(
        config,
        on_conflict="client_id"
    ).execute()

    return RedirectResponse(
        url=f"/admin/clients/{client_id}/edit",
        status_code=302
    )


# -------------------------------------------------------------------
# PACKAGES — LIST
# -------------------------------------------------------------------
@router.get("/packages", response_class=HTMLResponse)
def packages_list(request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    packages = (
        supabase
        .table("packages")
        .select("*")
        .order("sort_order")
        .execute()
        .data or []
    )

    return templates.TemplateResponse(
        request=request,
        name="packages.html",
        context={
            "packages": packages,
            "edit_package": None,
            "error": None
        }
    )


# -------------------------------------------------------------------
# PACKAGES — ADD
# -------------------------------------------------------------------
@router.post("/packages/add")
def add_package(
    request: Request,
    name: str = Form(...),
    price: float = Form(...),
    currency: str = Form("USD"),
    billing_period: str = Form("monthly"),
    monthly_quota: int = Form(...),
    per_user_daily_limit: int = Form(...),
    per_session_limit: int = Form(...),
    per_minute_limit: int = Form(...),
    is_trial: str = Form("off"),
    is_free: str = Form("off"),
    is_active: str = Form("off"),
    sort_order: int = Form(0)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    slug = name.lower().replace(" ", "-")

    supabase.table("packages").insert({
        "name": name,
        "slug": slug,
        "price": price,
        "currency": currency,
        "billing_period": billing_period,
        "monthly_quota": monthly_quota,
        "per_user_daily_limit": per_user_daily_limit,
        "per_session_limit": per_session_limit,
        "per_minute_limit": per_minute_limit,
        "is_trial": is_trial == "on",
        "is_free": is_free == "on",
        "is_active": is_active == "on",
        "sort_order": sort_order
    }).execute()

    return RedirectResponse(url="/admin/packages", status_code=302)


# -------------------------------------------------------------------
# PACKAGES — EDIT PAGE
# -------------------------------------------------------------------
@router.get("/packages/{package_id}/edit", response_class=HTMLResponse)
def edit_package_page(package_id: str, request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    packages = (
        supabase
        .table("packages")
        .select("*")
        .order("sort_order")
        .execute()
        .data or []
    )

    edit_package = next((p for p in packages if p["id"] == package_id), None)

    return templates.TemplateResponse(
        request=request,
        name="packages.html",
        context={
            "packages": packages,
            "edit_package": edit_package,
            "error": None
        }
    )


# -------------------------------------------------------------------
# PACKAGES — SAVE EDIT
# -------------------------------------------------------------------
@router.post("/packages/{package_id}/edit")
def edit_package(
    package_id: str,
    request: Request,
    name: str = Form(...),
    price: float = Form(...),
    currency: str = Form("USD"),
    billing_period: str = Form("monthly"),
    monthly_quota: int = Form(...),
    per_user_daily_limit: int = Form(...),
    per_session_limit: int = Form(...),
    per_minute_limit: int = Form(...),
    is_trial: str = Form("off"),
    is_free: str = Form("off"),
    is_active: str = Form("off"),
    sort_order: int = Form(0)
):
    redirect = require_admin(request)
    if redirect:
        return redirect

    supabase.table("packages").update({
        "name": name,
        "price": price,
        "currency": currency,
        "billing_period": billing_period,
        "monthly_quota": monthly_quota,
        "per_user_daily_limit": per_user_daily_limit,
        "per_session_limit": per_session_limit,
        "per_minute_limit": per_minute_limit,
        "is_trial": is_trial == "on",
        "is_free": is_free == "on",
        "is_active": is_active == "on",
        "sort_order": sort_order,
        "updated_at": datetime.utcnow().isoformat()
    }).eq("id", package_id).execute()

    return RedirectResponse(url="/admin/packages", status_code=302)


# -------------------------------------------------------------------
# PACKAGES — DELETE (only if no clients on this package)
# -------------------------------------------------------------------
@router.post("/packages/{package_id}/delete")
def delete_package(package_id: str, request: Request):
    redirect = require_admin(request)
    if redirect:
        return redirect

    # Get package slug first
    pkg = (
        supabase
        .table("packages")
        .select("slug, is_trial")
        .eq("id", package_id)
        .limit(1)
        .execute()
        .data
    )

    if not pkg:
        return RedirectResponse(url="/admin/packages", status_code=302)

    pkg = pkg[0]

    # Prevent deleting trial package
    if pkg["is_trial"]:
        packages = supabase.table("packages").select("*").order("sort_order").execute().data or []
        return templates.TemplateResponse(
            request=request,
            name="packages.html",
            context={
                "packages": packages,
                "edit_package": None,
                "error": "Cannot delete the trial package."
            }
        )

    # Check if any clients are on this package
    clients_on_pkg = (
        supabase
        .table("clients")
        .select("client_id")
        .eq("package_slug", pkg["slug"])
        .limit(1)
        .execute()
        .data
    )

    if clients_on_pkg:
        packages = supabase.table("packages").select("*").order("sort_order").execute().data or []
        return templates.TemplateResponse(
            request=request,
            name="packages.html",
            context={
                "packages": packages,
                "edit_package": None,
                "error": f"Cannot delete — {len(clients_on_pkg)}+ client(s) are on this package. Move them first."
            }
        )

    supabase.table("packages").delete().eq("id", package_id).execute()
    return RedirectResponse(url="/admin/packages", status_code=302)