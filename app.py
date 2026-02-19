“””
سارة — المساعد الذكي لعيادات دكتور محمود عزمي
Sara WhatsApp Bot — Meta API + OpenAI + Google Sheets
“””

import os, json, logging, tempfile
from flask import Flask, request, jsonify
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
from datetime import datetime
import pytz

# ─────────────────────────────────────────

# Config

# ─────────────────────────────────────────

VERIFY_TOKEN      = os.environ.get(“WA_VERIFY_TOKEN”, “sara_secret_2024”)
WA_TOKEN          = os.environ.get(“WA_TOKEN”, “”)
WA_PHONE_ID       = os.environ.get(“WA_PHONE_ID”, “”)
OPENAI_API_KEY    = os.environ.get(“OPENAI_API_KEY”, “”)
SPREADSHEET_ID    = “1hI5My8jrH-4W8dX7UCaWCFCjImevDjfoQ-0N0cfRBSk”
DOCTOR_PHONE      = “201515751566”
CAIRO_TZ          = pytz.timezone(“Africa/Cairo”)

logging.basicConfig(level=logging.INFO, format=”%(asctime)s %(levelname)s %(message)s”)
log = logging.getLogger(“sara”)

app = Flask(**name**)
ai  = OpenAI(api_key=OPENAI_API_KEY)

# ─────────────────────────────────────────

# Google Sheets — من Environment Variable

# ─────────────────────────────────────────

def get_sheets_client():
creds_json = os.environ.get(“GOOGLE_CREDS_JSON”, “”)
if not creds_json:
raise Exception(“GOOGLE_CREDS_JSON environment variable is missing!”)

```
creds_dict = json.loads(creds_json)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
# نكتب الـ creds في ملف مؤقت
with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    json.dump(creds_dict, f)
    tmp_path = f.name

creds = ServiceAccountCredentials.from_json_keyfile_name(tmp_path, scope)
os.unlink(tmp_path)
return gspread.authorize(creds)
```

# ─────────────────────────────────────────

# دستور سارة

# ─────────────────────────────────────────

SARA_SYSTEM = “””
أنتِ سارة — سكرتيرة طبية ومساعد إداري رقمي لعيادات دكتور محمود عزمي (طبيب تقويم أسنان).

## الشخصية

- مصرية، لبقة، هادئة، “بنت بلد” متعلمة
- بتتكلمي بالعامية المصرية المهذبة — مش روبوت
- ردود قصيرة وواضحة ومباشرة

## مهامك

- حجز وتنظيم المواعيد في 14 عيادة
- الرد على استفسارات المرضى
- جمع بيانات المريض: الاسم الكامل — الموبايل — العيادة — التاريخ — الوقت

## العيادات

Perladent (التجمع) | Dar Eldawaa | Glowy | Alaa Eldeen (مدينة نصر) | SDC (المنيل) | Cornerstone (شيراتون) | Dr.smile (المقطم) | Hamrawy (فيصل) | Kerdasa | Bendary | Elsalam | Paradise (حدائق أكتوبر) | SSS | Dentafix

## قواعد

1. ممنوع أي نصيحة طبية
1. لو مش عندك معلومة: “ثواني يا فندم، هراجع الدكتور وأرد عليك فوراً 🙏”
1. ممنوع التخمين في الأسعار أو المواعيد
1. بيانات المرضى سرية تماماً

## Admin Mode

لو الرسالة من الدكتور محمود — تحولي لوضع منفذ الأوامر وردي بـ “حاضر يا دكتور ✅”
“””

# ─────────────────────────────────────────

# Clinic Aliases

# ─────────────────────────────────────────

CLINIC_ALIASES = {
“perladent”: “Perladent”, “التجمع”: “Perladent”, “تجمع”: “Perladent”,
“dar eldawaa”: “Dar Eldawaa”, “دار الدواء”: “Dar Eldawaa”, “الدواء”: “Dar Eldawaa”,
“glowy”: “Glowy”, “جلوي”: “Glowy”,
“alaa eldeen”: “Alaa Eldeen”, “علاء الدين”: “Alaa Eldeen”, “مدينة نصر”: “Alaa Eldeen”,
“sdc”: “SDC”, “المنيل”: “SDC”,
“cornerstone”: “Cornerstone”, “شيراتون”: “Cornerstone”,
“dr.smile”: “Dr.smile”, “dr smile”: “Dr.smile”, “المقطم”: “Dr.smile”,
“hamrawy”: “Hamrawy”, “فيصل”: “Hamrawy”,
“kerdasa”: “Kerdasa”, “كرداسة”: “Kerdasa”,
“bendary”: “Bendary”, “البنداري”: “Bendary”,
“elsalam”: “Elsalam”, “السلام”: “Elsalam”,
“paradise”: “Paradise”, “حدائق اكتوبر”: “Paradise”, “أكتوبر”: “Paradise”,
“sss”: “SSS”,
“dentafix”: “Dentafix”, “دنتافيكس”: “Dentafix”
}

def normalize_clinic(name):
if not name: return None
key = name.lower().strip()
if key in CLINIC_ALIASES: return CLINIC_ALIASES[key]
for v in CLINIC_ALIASES.values():
if v.lower() == key: return v
return name.strip()

# ─────────────────────────────────────────

# Google Sheets Functions

# ─────────────────────────────────────────

def save_booking(clinic_raw, patient_name, patient_phone, date, time, step=“Follow-up”, comment=””):
try:
clinic = normalize_clinic(clinic_raw)
gc     = get_sheets_client()
ss     = gc.open_by_key(SPREADSHEET_ID)
try:
ws = ss.worksheet(clinic)
except gspread.WorksheetNotFound:
ws = ss.add_worksheet(title=clinic, rows=1000, cols=15)
ws.append_row([“Patient name”,“Next Visit”,“Time”,“Treatment step”,“Source”,“Comment”,“Secretary”,“Total”,“Deposit”,“Installments”,“Phone”,“booking_id”,“created_at”])

```
    booking_id = "B" + datetime.now(CAIRO_TZ).strftime("%d%m%H%M%S")
    now_str    = datetime.now(CAIRO_TZ).strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([patient_name, date, time, step or "Follow-up", "whatsapp", comment, "", "", "", "", patient_phone, booking_id, now_str])

    try:
        logs = ss.worksheet("logs")
    except:
        logs = ss.add_worksheet(title="logs", rows=1000, cols=6)
        logs.append_row(["ts","action","status","clinic","phone","message"])
    logs.append_row([now_str, "saveBooking", "ok", clinic, patient_phone, f"Saved {booking_id}"])

    log.info(f"✅ Saved: {booking_id} | {clinic} | {patient_name}")
    return {"status": "ok", "booking_id": booking_id, "clinic": clinic}
except Exception as e:
    log.error(f"❌ Sheets error: {e}")
    return {"status": "error", "message": str(e)}
```

# ─────────────────────────────────────────

# ذاكرة المحادثات

# ─────────────────────────────────────────

conversations = {}

def get_history(phone):
if phone not in conversations:
conversations[phone] = []
return conversations[phone]

def add_message(phone, role, content):
h = get_history(phone)
h.append({“role”: role, “content”: content})
if len(h) > 20:
conversations[phone] = h[-20:]

# ─────────────────────────────────────────

# AI Brain

# ─────────────────────────────────────────

def sara_think(phone, user_message, is_doctor=False):
add_message(phone, “user”, user_message)
history  = get_history(phone)
extra    = “\n[تنبيه: الشخص ده هو الدكتور محمود — Admin Mode]” if is_doctor else “”

```
tools = [{
    "type": "function",
    "function": {
        "name": "save_booking",
        "description": "احجز موعد مريض. استخدمها لما تجمع: الاسم والموبايل والعيادة والتاريخ والوقت.",
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

messages = [{"role": "system", "content": SARA_SYSTEM + extra}] + history
response = ai.chat.completions.create(
    model="gpt-4o", messages=messages, tools=tools,
    tool_choice="auto", temperature=0.7, max_tokens=400
)
msg = response.choices[0].message

if msg.tool_calls:
    tool_results = []
    for tc in msg.tool_calls:
        fn_args = json.loads(tc.function.arguments)
        result  = save_booking(
            fn_args.get("clinic"), fn_args.get("patient_name"),
            fn_args.get("patient_phone"), fn_args.get("date"),
            fn_args.get("time"), fn_args.get("step","Follow-up"),
            fn_args.get("comment","")
        )
        tool_results.append({"tool_call_id": tc.id, "role": "tool", "content": json.dumps(result, ensure_ascii=False)})

    messages2 = messages + [msg] + tool_results
    response2 = ai.chat.completions.create(model="gpt-4o", messages=messages2, temperature=0.7, max_tokens=300)
    reply = response2.choices[0].message.content
else:
    reply = msg.content

add_message(phone, "assistant", reply)
return reply
```

# ─────────────────────────────────────────

# WhatsApp

# ─────────────────────────────────────────

def send_whatsapp(to, text):
url = f”https://graph.facebook.com/v19.0/{WA_PHONE_ID}/messages”
try:
r = requests.post(url,
headers={“Authorization”: f”Bearer {WA_TOKEN}”, “Content-Type”: “application/json”},
json={“messaging_product”: “whatsapp”, “to”: to, “type”: “text”, “text”: {“body”: text}},
timeout=10)
log.info(f”WA → {to}: {r.status_code}”)
except Exception as e:
log.error(f”WA error: {e}”)

# ─────────────────────────────────────────

# Endpoints

# ─────────────────────────────────────────

@app.route(”/webhook”, methods=[“GET”])
def verify():
mode      = request.args.get(“hub.mode”)
token     = request.args.get(“hub.verify_token”)
challenge = request.args.get(“hub.challenge”)
if mode == “subscribe” and token == VERIFY_TOKEN:
log.info(“✅ Webhook verified”)
return challenge, 200
return “Forbidden”, 403

@app.route(”/webhook”, methods=[“POST”])
def webhook():
data = request.get_json(silent=True) or {}
try:
msgs = data.get(“entry”,[{}])[0].get(“changes”,[{}])[0].get(“value”,{}).get(“messages”,[])
for msg in msgs:
sender   = msg.get(“from”,””)
msg_type = msg.get(“type”,””)
text     = msg.get(“text”,{}).get(“body”,””).strip() if msg_type == “text” else f”[{msg_type}]”
if not text: continue
log.info(f”📩 {sender}: {text}”)
is_doctor = sender.replace(”+”,””) == DOCTOR_PHONE
reply     = sara_think(sender, text, is_doctor=is_doctor)
send_whatsapp(sender, reply)
except Exception as e:
log.error(f”Webhook error: {e}”)
return jsonify({“status”: “ok”}), 200

@app.route(”/health”, methods=[“GET”])
def health():
return jsonify({“status”: “سارة شغالة ✅”, “time”: datetime.now(CAIRO_TZ).isoformat()})

@app.route(”/test”, methods=[“POST”])
def test():
body  = request.get_json(silent=True) or {}
reply = sara_think(body.get(“phone”,“test”), body.get(“message”,“مرحبا”), body.get(“is_doctor”,False))
return jsonify({“reply”: reply})

if **name** == “**main**”:
app.run(host=“0.0.0.0”, port=int(os.environ.get(“PORT”,5000)))
