import os
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(prefix="/widget")

supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

DEFAULT_CONFIG = {
    "primary_color": "#1c2b1e",
    "secondary_color": "#c9a84c",
    "position": "bottom-right",
    "greeting": "Hi! How can I help you today?",
    "bot_name": "Assistant",
    "is_active": True
}


def get_widget_config(client_id: str) -> dict | None:
    try:
        # Check client exists — use limit(1) to avoid error on 0 rows
        client_rows = (
            supabase
            .table("clients")
            .select("client_id, business_name")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
            .data
        )
        if not client_rows:
            return None

        client = client_rows[0]

        # Get widget config — fall back to defaults if no row yet
        widget_rows = (
            supabase
            .table("client_widgets")
            .select("*")
            .eq("client_id", client_id)
            .limit(1)
            .execute()
            .data
        )

        config = DEFAULT_CONFIG.copy()
        if widget_rows:
            config.update(widget_rows[0])

        config["business_name"] = client["business_name"]
        return config

    except Exception as e:
        print(f"[Widget config error]: {e}")
        return None


# -------------------------------------------------------------------
# GET /widget.js?client_id=abc123
# The embed script clients paste on their website
# -------------------------------------------------------------------
@router.get("/widget.js")
def serve_widget_js(client_id: str, request: Request):
    config = get_widget_config(client_id)

    if not config:
        return Response(
            content=f"console.error('Claribizz: client \"{client_id}\" not found.');",
            media_type="application/javascript"
        )

    if not config.get("is_active", True):
        return Response(
            content="console.warn('Claribizz: widget is currently inactive.');",
            media_type="application/javascript"
        )

    base_url = str(request.base_url).rstrip("/")
    position = config["position"]

    # Position CSS
    if position == "bottom-left":
        position_css = "bottom: 24px; left: 24px;"
        panel_css = "bottom: 90px; left: 24px;"
    else:  # bottom-right default
        position_css = "bottom: 24px; right: 24px;"
        panel_css = "bottom: 90px; right: 24px;"

    js = f"""
(function() {{
    var CLIENT_ID = "{client_id}";
    var BASE_URL = "{base_url}";
    var PRIMARY = "{config['primary_color']}";
    var SECONDARY = "{config['secondary_color']}";
    var BOT_NAME = "{config['bot_name']}";
    var GREETING = "{config['greeting']}";
    var SESSION_EXPIRY_MS = 24 * 60 * 60 * 1000; // 24 hours
    var STORAGE_KEY = 'cbz_session_' + CLIENT_ID;

    // -------------------------------------------------------------------
    // Session management — persists with 24hr inactivity expiry
    // -------------------------------------------------------------------
    function generateSessionId() {{
        return 'widget_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }}

    function loadSession() {{
        try {{
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return null;
            var data = JSON.parse(raw);
            var now = Date.now();
            // Expire if inactive for more than 24 hours
            if (now - data.last_active > SESSION_EXPIRY_MS) {{
                localStorage.removeItem(STORAGE_KEY);
                return null;
            }}
            return data.session_id;
        }} catch(e) {{
            localStorage.removeItem(STORAGE_KEY);
            return null;
        }}
    }}

    function saveSession(sessionId) {{
        localStorage.setItem(STORAGE_KEY, JSON.stringify({{
            session_id: sessionId,
            last_active: Date.now()
        }}));
    }}

    function touchSession() {{
        try {{
            var raw = localStorage.getItem(STORAGE_KEY);
            if (!raw) return;
            var data = JSON.parse(raw);
            data.last_active = Date.now();
            localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
        }} catch(e) {{}}
    }}

    function resetSession() {{
        var newId = generateSessionId();
        saveSession(newId);
        return newId;
    }}

    // Load or create session
    var SESSION_ID = loadSession();
    if (!SESSION_ID) {{
        SESSION_ID = generateSessionId();
        saveSession(SESSION_ID);
    }}

    // Inject styles
    var style = document.createElement('style');
    style.innerHTML = `
        #cbz-bubble {{
            position: fixed;
            {position_css}
            width: 56px;
            height: 56px;
            background: ${{PRIMARY}};
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
            z-index: 99999;
            transition: transform 0.2s;
        }}
        #cbz-bubble:hover {{ transform: scale(1.08); }}
        #cbz-bubble svg {{ width: 26px; height: 26px; fill: #fff; }}

        #cbz-panel {{
            position: fixed;
            {panel_css}
            width: 360px;
            height: 520px;
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 8px 40px rgba(0,0,0,0.15);
            z-index: 99998;
            display: none;
            flex-direction: column;
            overflow: hidden;
            font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
        }}
        #cbz-panel.open {{ display: flex; }}

        #cbz-header {{
            background: ${{PRIMARY}};
            padding: 16px 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        #cbz-header-title {{
            color: #fff;
            font-size: 15px;
            font-weight: 600;
            letter-spacing: -0.2px;
        }}
        #cbz-header-sub {{
            color: rgba(255,255,255,0.65);
            font-size: 12px;
            margin-top: 2px;
        }}
        #cbz-close {{
            background: none;
            border: none;
            cursor: pointer;
            color: rgba(255,255,255,0.8);
            font-size: 20px;
            line-height: 1;
            padding: 0;
        }}
        #cbz-close:hover {{ color: #fff; }}

        #cbz-messages {{
            flex: 1;
            overflow-y: auto;
            padding: 16px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            background: #f9f8f5;
        }}

        .cbz-msg {{
            max-width: 82%;
            padding: 10px 14px;
            border-radius: 14px;
            font-size: 14px;
            line-height: 1.5;
            word-wrap: break-word;
        }}
        .cbz-msg.bot {{
            background: #fff;
            color: #1a1a1a;
            align-self: flex-start;
            border: 1px solid #e8e6e0;
            border-bottom-left-radius: 4px;
        }}
        .cbz-msg.user {{
            background: ${{PRIMARY}};
            color: #fff;
            align-self: flex-end;
            border-bottom-right-radius: 4px;
        }}
        .cbz-msg.typing {{
            background: #fff;
            border: 1px solid #e8e6e0;
            align-self: flex-start;
            color: #999;
            font-style: italic;
            border-bottom-left-radius: 4px;
        }}

        #cbz-input-row {{
            display: flex;
            align-items: center;
            padding: 12px 14px;
            border-top: 1px solid #e8e6e0;
            gap: 8px;
            background: #fff;
        }}
        #cbz-input {{
            flex: 1;
            border: 1px solid #ddd;
            border-radius: 22px;
            padding: 9px 16px;
            font-size: 14px;
            font-family: inherit;
            outline: none;
            background: #fafafa;
            transition: border-color 0.15s;
        }}
        #cbz-input:focus {{ border-color: ${{PRIMARY}}; background: #fff; }}
        #cbz-send {{
            width: 38px;
            height: 38px;
            background: ${{PRIMARY}};
            border: none;
            border-radius: 50%;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            transition: opacity 0.15s;
        }}
        #cbz-send:hover {{ opacity: 0.85; }}
        #cbz-send svg {{ width: 16px; height: 16px; fill: #fff; }}

        #cbz-powered {{
            text-align: center;
            font-size: 11px;
            color: #bbb;
            padding: 6px 0 10px;
            background: #fff;
        }}
        #cbz-powered a {{ color: #bbb; text-decoration: none; }}
        #cbz-powered a:hover {{ color: #888; }}
    `;
    document.head.appendChild(style);

    // Chat bubble
    var bubble = document.createElement('div');
    bubble.id = 'cbz-bubble';
    bubble.innerHTML = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2C6.48 2 2 6.48 2 12c0 1.85.5 3.58 1.37 5.07L2 22l4.93-1.37C8.42 21.5 10.15 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2zm-1 13H7v-2h4v2zm6 0h-4v-2h4v2zm0-4H7V9h10v2z"/>
    </svg>`;
    document.body.appendChild(bubble);

    // Chat panel
    var panel = document.createElement('div');
    panel.id = 'cbz-panel';
    panel.innerHTML = `
        <div id="cbz-header">
            <div>
                <div id="cbz-header-title">${{BOT_NAME}}</div>
                <div id="cbz-header-sub">Typically replies instantly</div>
            </div>
            <div style="display: flex; align-items: center; gap: 10px;">
                <button id="cbz-new" title="Start new conversation" style="
                    background: rgba(255,255,255,0.15);
                    border: none;
                    border-radius: 6px;
                    color: rgba(255,255,255,0.8);
                    font-size: 11px;
                    padding: 4px 8px;
                    cursor: pointer;
                    font-family: inherit;
                    transition: background 0.15s;
                ">New chat</button>
                <button id="cbz-close">×</button>
            </div>
        </div>
        <div id="cbz-messages"></div>
        <div id="cbz-input-row">
            <input id="cbz-input" type="text" placeholder="Type a message..." autocomplete="off"/>
            <button id="cbz-send">
                <svg viewBox="0 0 24 24"><path d="M2 21l21-9L2 3v7l15 2-15 2v7z"/></svg>
            </button>
        </div>
        <div id="cbz-powered">Powered by <a href="https://claribizz.com" target="_blank">Claribizz</a></div>
    `;
    document.body.appendChild(panel);

    var messages = document.getElementById('cbz-messages');
    var input = document.getElementById('cbz-input');
    var isOpen = false;
    var greetingSent = false;

    function addMessage(text, role) {{
        var msg = document.createElement('div');
        msg.className = 'cbz-msg ' + role;
        msg.innerText = text;
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
        return msg;
    }}

    function showTyping() {{
        var msg = document.createElement('div');
        msg.className = 'cbz-msg typing';
        msg.id = 'cbz-typing';
        msg.innerText = 'Typing...';
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }}

    function removeTyping() {{
        var t = document.getElementById('cbz-typing');
        if (t) t.remove();
    }}

    function setInputLocked(locked) {{
        var sendBtn = document.getElementById('cbz-send');
        input.disabled = locked;
        sendBtn.disabled = locked;
        sendBtn.style.opacity = locked ? '0.4' : '1';
        sendBtn.style.cursor = locked ? 'not-allowed' : 'pointer';
        input.style.opacity = locked ? '0.6' : '1';
        input.placeholder = locked ? 'Waiting for reply...' : 'Type a message...';
    }}

    function sendMessage(text) {{
        if (!text.trim()) return;
        addMessage(text, 'user');
        input.value = '';
        showTyping();
        setInputLocked(true);
        touchSession(); // Refresh 24hr expiry on every message

        fetch(BASE_URL + '/chat', {{
            method: 'POST',
            headers: {{ 'Content-Type': 'application/json' }},
            body: JSON.stringify({{
                client_id: CLIENT_ID,
                message: text,
                session_id: SESSION_ID
            }})
        }})
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
            removeTyping();
            if (data.reply) addMessage(data.reply, 'bot');
        }})
        .catch(function() {{
            removeTyping();
            addMessage('Sorry, something went wrong. Please try again.', 'bot');
        }})
        .finally(function() {{
            setInputLocked(false);
            input.focus();
        }});
    }}

    function openPanel() {{
        panel.classList.add('open');
        isOpen = true;
        bubble.innerHTML = `<svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>`;
        input.focus();

        // Load history on first open
        if (!greetingSent) {{
            greetingSent = true;
            setInputLocked(true);

            fetch(BASE_URL + '/widget/history?session_id=' + SESSION_ID + '&client_id=' + CLIENT_ID)
            .then(function(r) {{ return r.json(); }})
            .then(function(data) {{
                setInputLocked(false);
                if (data.messages && data.messages.length > 0) {{
                    // Returning user — render history
                    data.messages.forEach(function(msg) {{
                        addMessage(msg.content, msg.role === 'user' ? 'user' : 'bot');
                    }});
                    messages.scrollTop = messages.scrollHeight;
                }} else {{
                    // New user — show greeting
                    setTimeout(function() {{
                        addMessage(GREETING, 'bot');
                    }}, 300);
                }}
            }})
            .catch(function() {{
                setInputLocked(false);
                // On error fall back to greeting
                setTimeout(function() {{
                    addMessage(GREETING, 'bot');
                }}, 300);
            }});
        }}
    }}

    function closePanel() {{
        panel.classList.remove('open');
        isOpen = false;
        bubble.innerHTML = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2C6.48 2 2 6.48 2 12c0 1.85.5 3.58 1.37 5.07L2 22l4.93-1.37C8.42 21.5 10.15 22 12 22c5.52 0 10-4.48 10-10S17.52 2 12 2zm-1 13H7v-2h4v2zm6 0h-4v-2h4v2zm0-4H7V9h10v2z"/>
        </svg>`;
    }}

    bubble.addEventListener('click', function() {{
        isOpen ? closePanel() : openPanel();
    }});

    document.getElementById('cbz-close').addEventListener('click', closePanel);

    document.getElementById('cbz-new').addEventListener('click', function() {{
        if (!confirm('Start a new conversation? Your current chat will be saved.')) return;
        // Reset session
        SESSION_ID = resetSession();
        // Clear UI
        messages.innerHTML = '';
        // Show greeting after short delay
        setTimeout(function() {{
            addMessage(GREETING, 'bot');
        }}, 300);
        input.focus();
    }});

    document.getElementById('cbz-send').addEventListener('click', function() {{
        sendMessage(input.value);
    }});

    input.addEventListener('keydown', function(e) {{
        if (e.key === 'Enter') sendMessage(input.value);
    }});

}})();
"""

    return Response(content=js, media_type="application/javascript")


# -------------------------------------------------------------------
# GET /widget/history?session_id=xxx&client_id=xxx
# Returns conversation history for a session
# -------------------------------------------------------------------
@router.get("/history")
def get_history(session_id: str, client_id: str):
    try:
        from core.session_manager import get_history_for_ai, normalize_session_id

        # Normalize the session_id the same way the agent does
        normalized = normalize_session_id(session_id)

        rows = (
            supabase
            .table("conversation_sessions")
            .select("messages")
            .eq("session_id", normalized)
            .eq("client_id", client_id)
            .limit(1)
            .execute()
            .data
        )

        if not rows or not rows[0].get("messages"):
            return {"messages": []}

        # Sort oldest to newest and return
        messages = sorted(
            rows[0]["messages"],
            key=lambda m: m.get("timestamp", "")
        )

        return {"messages": messages}

    except Exception as e:
        print(f"[History error]: {e}")
        return {"messages": []}