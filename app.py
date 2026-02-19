# app.py
import os
import json
import logging
import tempfile
from datetime import datetime

import requests
import gspread
import pytz
from flask import Flask, request, jsonify
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI

# =========================
# ENV VARS
# =========================
VERIFY_TOKEN = os.environ.get("WA_VERIFY_TOKEN", "sara_secret_2024y")
WA_TOKEN = os.environ.get("WA_TOKEN", "")
WA_PHONE_ID = os.environ.get("WA_PHONE_ID", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDS_JSON", "")

SPREADSHEET_ID = os.environ.get(
    "SPREADSHEET_ID",
    "1hI5My8jrH-4W8dX7UCaWCFCjImevDjfoQ-0N0cfRBSk"
)

# رقمك (بدون +) — لازم يكون نفس الفورمات اللي بيجي من واتساب
DOCTOR_PHONE = os.environ.get("DOCTOR_PHONE", "201515751566")

CAIRO_TZ = pytz.timezone("Africa/Cairo")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sara")

# Flask app
app = Flask(__name__)

# OpenAI client
ai = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# SARA SYSTEM PROMPT
# =========================
SARA_SYSTEM = (
    "انتي سارة - سكرتيرة مواعيد لطبيب تقويم اسنان دكتور محمود عزمي.\n"
    "- مصرية، لبيقة، هادية، بنت بلد محترمة.\n"
    "- بتتكلمي بالعامية المصرية المهذبة، مش روبوت.\n"
    "- ردود قصيرة وواضحة ومباشرة.\n"
    "- ممنوع اي نصيحة طبية.\n"
    "- لو مش متأكدة: 'ثواني يا فندم، هراجع الدكتور وارد عليك فورًا'.\n"
    "- لو الرسالة من الدكتور محمود: ادخلي وضع اوامر مباشر.\n"
)

CLINIC_ALIASES = {
    "perladent": "Perladent", "التجمع": "Perladent", "تجمع": "Perladent",
    "dar eldawaa": "Dar Eldawaa", "دار الدواء": "Dar Eldawaa", "الدواء": "Dar Eldawaa",
    "glowy": "Glowy", "جلوي": "Glowy",
    "alaa eldeen": "Alaa Eldeen", "علاء الدين": "Alaa Eldeen", "مدينة نصر": "Alaa Eldeen",
    "sdc": "SDC", "المنيل": "SDC",
    "cornerstone": "Cornerstone", "شيراتون": "Cornerstone",
    "dr.smile": "Dr.smile", "dr smile": "Dr.smile", "المقطم": "Dr.smile",
    "hamrawy": "Hamrawy", "فيصل": "Hamrawy",
    "kerdasa": "Kerdasa", "كرداسة": "Kerdasa",
    "bendary": "Bendary", "البنداري": "Bendary",
    "elsalam": "Elsalam", "السلام": "Elsalam",
    "paradise": "Paradise", "حدائق اكتوبر": "Paradise",
    "sss": "SSS",
    "dentafix": "Dentafix", "دنتافيكس": "Dentafix",
}

def normalize_clinic(name: str):
    if not name:
        return None
    key = str(name).lower().strip()
    if key in CLINIC_ALIASES:
        return CLINIC_ALIASES[key]
    for v in CLINIC_ALIASES.values():
        if v.lower() == key:
            return v
    return str(name).strip()

# =========================
# GOOGLE SHEETS
# =========================
def get_sheets_client():
    if not GOOGLE_CREDS_JSON:
        raise Exception("GOOGLE_CREDS_JSON missing in env!")
    creds_dict = json.loads(GOOGLE_CREDS_JSON)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]

    # gspread يحتاج ملف creds؛ بنعمل temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(creds_dict, f)
        tmp = f.name

    creds = ServiceAccountCredentials.from_json_keyfile_name(tmp, scope)
    os.unlink(tmp)
    return gspread.authorize(creds)

def ensure_headers(ws):
    # هيدر ثابت (حسب شيت التقويم بتاعك)
    headers = [
        "Patient name", "Next Visit", "Time", "Treatment step", "Source", "Comment",
        "Secretary", "Total", "Deposit", "Installments", "Phone", "booking_id", "created_at"
    ]
    try:
        first_row = ws.row_values(1)
        if not first_row or first_row[:3] != headers[:3]:
            ws.insert_row(headers, 1)
    except Exception:
        ws.insert_row(headers, 1)

def save_booking(clinic_raw, patient_name, patient_phone, date, time, step="Follow-up", comment=""):
    try:
        clinic = normalize_clinic(clinic_raw) or "Unknown"
        gc = get_sheets_client()
        ss = gc.open_by_key(SPREADSHEET_ID)

        # كل عيادة Worksheet باسمها
        try:
            ws = ss.worksheet(clinic)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=clinic, rows=1000, cols=15)
            ensure_headers(ws)

        # ID + timestamp
        bid = "B" + datetime.now(CAIRO_TZ).strftime("%d%m%H%M%S")
        now = datetime.now(CAIRO_TZ).strftime("%Y-%m-%d %H:%M:%S")

        ws.append_row([
            patient_name, date, time, step, "whatsapp", comment,
            "", "", "", "", patient_phone, bid, now
        ])

        # logs sheet
        try:
            lg = ss.worksheet("logs")
        except Exception:
            lg = ss.add_worksheet(title="logs", rows=2000, cols=6)
            lg.append_row(["ts", "action", "status", "clinic", "phone", "message"])

        lg.append_row([now, "saveBooking", "ok", clinic, patient_phone, "Saved " + bid])

        log.info("Saved booking %s to clinic=%s", bid, clinic)
        return {"status": "ok", "booking_id": bid, "clinic": clinic}

    except Exception as e:
        log.error("Sheets error: %s", str(e))
        return {"status": "error", "message": str(e)}

# =========================
# SIMPLE IN-MEMORY HISTORY
# =========================
conversations = {}

def get_history(phone):
    if phone not in conversations:
        conversations[phone] = []
    return conversations[phone]

def add_message(phone, role, content):
    h = get_history(phone)
    h.append({"role": role, "content": content})
    if len(h) > 20:
        conversations[phone] = h[-20:]

# =========================
# AI CORE
# =========================
def sara_think(phone, user_message, is_doctor=False):
    add_message(phone, "user", user_message)
    history = get_history(phone)
    extra = "\n[Admin Mode - الدكتور محمود]" if is_doctor else ""

    tools = [{
        "type": "function",
        "function": {
            "name": "save_booking",
            "description": "احجز موعد لما تكون جمعت: العيادة + الاسم + الموبايل + التاريخ + الوقت",
            "parameters": {
                "type": "object",
                "properties": {
                    "clinic": {"type": "string"},
                    "patient_name": {"type": "string"},
                    "patient_phone": {"type": "string"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "step": {"type": "string"},
                    "comment": {"type": "string"}
                },
                "required": ["clinic", "patient_name", "patient_phone", "date", "time"]
            }
        }
    }]

    messages = [{"role": "system", "content": SARA_SYSTEM + extra}] + history

    # 1) model response (may call tool)
    response = ai.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
        messages=messages,
        tools=tools,
        tool_choice="auto",
        temperature=0.7,
        max_tokens=450,
    )

    msg = response.choices[0].message

    # 2) handle tool call if any
    if getattr(msg, "tool_calls", None):
        tool_results = []
        for tc in msg.tool_calls:
            fn_args = json.loads(tc.function.arguments)

            result = save_booking(
                fn_args.get("clinic"),
                fn_args.get("patient_name"),
                fn_args.get("patient_phone"),
                fn_args.get("date"),
                fn_args.get("time"),
                fn_args.get("step", "Follow-up"),
                fn_args.get("comment", ""),
            )

            tool_results.append({
                "tool_call_id": tc.id,
                "role": "tool",
                "content": json.dumps(result, ensure_ascii=False)
            })

        messages2 = messages + [msg] + tool_results
        response2 = ai.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o"),
            messages=messages2,
            temperature=0.7,
            max_tokens=350,
        )
        reply = response2.choices[0].message.content
    else:
        reply = msg.content

    add_message(phone, "assistant", reply)
    return reply

# =========================
# WHATSAPP SEND
# =========================
def send_whatsapp(to, text):
    if not WA_TOKEN or not WA_PHONE_ID:
        log.error("WA_TOKEN / WA_PHONE_ID missing")
        return

    url = f"https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }

    try:
        r = requests.post(
            url,
            headers={"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        log.info("WA sent status=%s body=%s", r.status_code, r.text[:200])
    except Exception as e:
        log.error("WA error: %s", str(e))

# =========================
# ROUTES (IMPORTANT)
# =========================
@app.get("/webhook")
def verify():
    """
    Meta verification:
    GET /webhook?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200

    return "Forbidden", 403

@app.post("/webhook")
def webhook():
    """
    WhatsApp inbound messages
    """
    data = request.get_json(silent=True) or {}
    try:
        entries = data.get("entry", [])
        for entry in entries:
            changes = entry.get("changes", [])
            for ch in changes:
                value = ch.get("value", {})
                msgs = value.get("messages", []) or []
                for m in msgs:
                    sender = (m.get("from") or "").strip()
                    msg_type = m.get("type", "")

                    if msg_type == "text":
                        text = (m.get("text", {}) or {}).get("body", "").strip()
                    else:
                        text = f"[{msg_type}]"

                    if not sender or not text:
                        continue

                    # doctor check
                    sender_digits = sender.replace("+", "").strip()
                    is_doctor = (sender_digits == DOCTOR_PHONE)

                    reply = sara_think(sender_digits, text, is_doctor=is_doctor)
                    send_whatsapp(sender_digits, reply)

    except Exception as e:
        log.error("Webhook error: %s", str(e))

    return jsonify({"status": "ok"}), 200

@app.get("/health")
def health():
    return jsonify({"status": "sara is alive", "time": datetime.now(CAIRO_TZ).isoformat()}), 200

@app.post("/test")
def test():
    body = request.get_json(silent=True) or {}
    phone = body.get("phone", "test")
    message = body.get("message", "مرحبا")
    is_doctor = bool(body.get("is_doctor", False))
    reply = sara_think(phone, message, is_doctor=is_doctor)
    return jsonify({"reply": reply}), 200

# =========================
# MAIN
# =========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
