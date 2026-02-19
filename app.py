import os, json, logging, tempfile
from datetime import datetime
import pytz

from flask import Flask, request, jsonify
import requests

import gspread
from google.oauth2.service_account import Credentials

from openai import OpenAI

# ================== ENV ==================
VERIFY_TOKEN   = os.getenv("WA_VERIFY_TOKEN", "sara_secret_2024")
WA_TOKEN       = os.getenv("WA_TOKEN", "")
WA_PHONE_ID    = os.getenv("WA_PHONE_ID", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SPREADSHEET_ID = "1hI5My8jrH-4W8dX7UCaWCFCjImevDjfoQ-0N0cfRBSk"  # بتاعك
DOCTOR_PHONE   = "201515751566"  # د. محمود بدون +

CAIRO_TZ = pytz.timezone("Africa/Cairo")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sara")

app = Flask(__name__)
ai  = OpenAI(api_key=OPENAI_API_KEY)

# ================== PROMPT ==================
SARA_SYSTEM = (
    "انت 'سارة' سكرتيرة مواعيد لدكتور محمود عزمي.\n"
    "- مصريّة، لبقة، هادية، بنت بلد محترمة\n"
    "- بتتكلمي بالعامية المصرية المهذبة - مش روبوت\n"
    "- ردود قصيرة وواضحة ومباشرة\n"
    "- ممنوع أي نصيحة طبية\n"
    "- لو مش متأكدة: 'ثواني يا فندم، هراجع الدكتور وأرد عليك فوراً'\n"
    "- لو الرسالة من الدكتور محمود: نفّذي الأوامر مباشرة\n"
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
    "dentafix": "Dentafix", "دنتافيكس": "Dentafix"
}

def normalize_clinic(name: str | None):
    if not name:
        return None
    key = name.lower().strip()
    if key in CLINIC_ALIASES:
        return CLINIC_ALIASES[key]
    # لو حد كتب الاسم الرسمي
    for v in set(CLINIC_ALIASES.values()):
        if v.lower() == key:
            return v
    return name.strip()

# ================== GOOGLE SHEETS ==================
def get_sheets_client():
    creds_json = os.getenv("GOOGLE_CREDS_JSON", "")
    if not creds_json:
        raise Exception("GOOGLE_CREDS_JSON missing!")

    creds_dict = json.loads(creds_json)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def ensure_headers(ws):
    headers = [
        "Patient name","Next Visit","Time","Treatment step","Source","Comment",
        "Secretary","Total","Deposit","Installments","Phone","booking_id","created_at"
    ]
    first_row = ws.row_values(1)
    if first_row != headers:
        ws.clear()
        ws.append_row(headers)

def save_booking(clinic_raw, patient_name, patient_phone, date, time, step="Follow-up", comment=""):
    clinic = normalize_clinic(clinic_raw) or "Unknown"
    try:
        gc = get_sheets_client()
        ss = gc.open_by_key(SPREADSHEET_ID)

        # ورقة باسم العيادة
        try:
            ws = ss.worksheet(clinic)
        except gspread.WorksheetNotFound:
            ws = ss.add_worksheet(title=clinic, rows=1000, cols=15)
            ensure_headers(ws)

        # تأكد الهيدر موجود
        if ws.row_count < 1 or ws.row_values(1) == []:
            ensure_headers(ws)

        bid = "B" + datetime.now(CAIRO_TZ).strftime("%d%m%H%M%S")
        now = datetime.now(CAIRO_TZ).strftime("%Y-%m-%d %H:%M:%S")

        ws.append_row([
            patient_name, date, time, step, "whatsapp", comment,
            "", "", "", "", patient_phone, bid, now
        ])

        # logs sheet
        try:
            lg = ss.worksheet("logs")
        except gspread.WorksheetNotFound:
            lg = ss.add_worksheet(title="logs", rows=2000, cols=6)
            lg.append_row(["ts","action","status","clinic","phone","message"])

        lg.append_row([now, "saveBooking", "ok", clinic, patient_phone, "Saved " + bid])

        log.info(f"Saved booking {bid} to sheet {clinic}")
        return {"status": "ok", "booking_id": bid, "clinic": clinic}

    except Exception as e:
        log.error("Sheets error: " + str(e))
        return {"status": "error", "message": str(e), "clinic": clinic}

# ================== MEMORY (simple) ==================
conversations = {}

def get_history(phone):
    return conversations.setdefault(phone, [])

def add_message(phone, role, content):
    h = get_history(phone)
    h.append({"role": role, "content": content})
    if len(h) > 20:
        conversations[phone] = h[-20:]

# ================== OPENAI TOOL-CALL ==================
TOOLS = [{
    "type": "function",
    "function": {
        "name": "save_booking",
        "description": "احجز موعد مريض لما تجمع الاسم والموبايل والعيادة والتاريخ والوقت",
        "parameters": {
            "type": "object",
            "properties": {
                "clinic":        {"type": "string"},
                "patient_name":  {"type": "string"},
                "patient_phone": {"type": "string"},
                "date":          {"type": "string"},
                "time":          {"type": "string"},
                "step":          {"type": "string"},
                "comment":       {"type": "string"}
            },
            "required": ["clinic", "patient_name", "patient_phone", "date", "time"]
        }
    }
}]

def sara_think(phone, user_message, is_doctor=False):
    add_message(phone, "user", user_message)
    history = get_history(phone)

    extra = "\n[Admin Mode - الدكتور محمود]" if is_doctor else ""
    messages = [{"role": "system", "content": SARA_SYSTEM + extra}] + history

    resp = ai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        temperature=0.7,
        max_tokens=400
    )

    msg = resp.choices[0].message

    # لو فيه tool call
    if msg.tool_calls:
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
                fn_args.get("comment", "")
            )

            tool_results.append({
                "tool_call_id": tc.id,
                "role": "tool",
                "content": json.dumps(result, ensure_ascii=False)
            })

        messages2 = messages + [msg] + tool_results
        resp2 = ai.chat.completions.create(
            model="gpt-4o",
            messages=messages2,
            temperature=0.7,
            max_tokens=300
        )
        reply = resp2.choices[0].message.content

    else:
        reply = msg.content

    add_message(phone, "assistant", reply)
    return reply

# ================== WHATSAPP SEND ==================
def send_whatsapp(to, text):
    if not (WA_TOKEN and WA_PHONE_ID):
        log.warning("WA_TOKEN/WA_PHONE_ID missing; skipping send")
        return

    url = f"https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }

    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {WA_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=15
    )
    log.info(f"WA send status={r.status_code} body={r.text[:200]}")

# ================== ROUTES ==================
@app.get("/webhook")
def verify():
    mode      = request.args.get("hub.mode")
    token     = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Forbidden", 403

@app.post("/webhook")
def webhook():
    data = request.get_json(silent=True) or {}

    try:
        entry = (data.get("entry") or [{}])[0]
        changes = (entry.get("changes") or [{}])[0]
        value = changes.get("value") or {}

        msgs = value.get("messages") or []
        # تجاهل statuses
        if not msgs:
            return jsonify({"status": "ok"}), 200

        for m in msgs:
            sender = (m.get("from") or "").strip()
            mtype = m.get("type")

            if mtype == "text":
                text = (m.get("text") or {}).get("body", "").strip()
            else:
                text = f"[{mtype}]"

            if not text or not sender:
                continue

            is_doctor = sender.replace("+", "") == DOCTOR_PHONE
            reply = sara_think(sender, text, is_doctor=is_doctor)
            send_whatsapp(sender, reply)

    except Exception as e:
        log.error("Webhook error: " + str(e))

    return jsonify({"status": "ok"}), 200

@app.get("/health")
def health():
    return jsonify({"status": "sara is alive", "time": datetime.now(CAIRO_TZ).isoformat()})

@app.post("/test")
def test():
    body = request.get_json(silent=True) or {}
    phone = body.get("phone", "test")
    message = body.get("message", "مرحبا")
    is_doctor = bool(body.get("is_doctor", False))
    reply = sara_think(phone, message, is_doctor=is_doctor)
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
