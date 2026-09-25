import os
import uuid
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

    handoffs = [
        s for s in sessions
        if any(
            m.get("role") == "assistant"
            and "connect you with our team" in m.get("content", "")
            for m in s.get("messages", [])
        )
    ]

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

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients,
            "edit_client": None,
            "faqs": [],
            "error": None
        }
    )


# -------------------------------------------------------------------
# CLIENTS — ADD
# -------------------------------------------------------------------
@router.post("/clients/add")
def add_client(
    request: Request,
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

    return templates.TemplateResponse(
        request=request,
        name="clients.html",
        context={
            "clients": clients,
            "edit_client": client,
            "faqs": faqs,
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

    sessions = query.execute().data or []

    return templates.TemplateResponse(
        request=request,
        name="conversations.html",
        context={
            "sessions": sessions,
            "clients": clients,
            "selected_client": client_id
        }
    )