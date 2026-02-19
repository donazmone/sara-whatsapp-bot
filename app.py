import os, json, logging, tempfile
from flask import Flask, request, jsonify
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
from datetime import datetime
import pytz

VERIFY_TOKEN   = os.environ.get(“WA_VERIFY_TOKEN”, “sara_secret_2024”)
WA_TOKEN       = os.environ.get(“WA_TOKEN”, “”)
WA_PHONE_ID    = os.environ.get(“WA_PHONE_ID”, “”)
OPENAI_API_KEY = os.environ.get(“OPENAI_API_KEY”, “”)
SPREADSHEET_ID = “1hI5My8jrH-4W8dX7UCaWCFCjImevDjfoQ-0N0cfRBSk”
DOCTOR_PHONE   = “201515751566”
CAIRO_TZ       = pytz.timezone(“Africa/Cairo”)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(“sara”)
app = Flask(**name**)
ai  = OpenAI(api_key=OPENAI_API_KEY)

SARA_SYSTEM = (
“anti sara - sckrtera tbyya lyadat dktwr mahmwd azmy.\n”
“- masrya, lbyqa, hadya, bnt bld mtlma\n”
“- bttklmy blAamya almSrya almhzba - msh rwbwt\n”
“- rdwd qSyra wwaoDHa wmbashra\n”
“- alOyadat: Perladent(altjmE) | Dar Eldawaa | Glowy | Alaa Eldeen | SDC | Cornerstone | Dr.smile | Hamrawy | Kerdasa | Bendary | Elsalam | Paradise | SSS | Dentafix\n”
“- mmnoE ay nSyHa Tbya\n”
“- lwla mEndksh mElwma: ‘THwany ya fndm, hrajE aldktwr ward Elyky fwra’\n”
“- lw alrsala mn aldktwr mHmwd: wDO mnfz alawamr\n”
)

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
“paradise”: “Paradise”, “حدائق اكتوبر”: “Paradise”,
“sss”: “SSS”,
“dentafix”: “Dentafix”, “دنتافيكس”: “Dentafix”
}

def normalize_clinic(name):
if not name:
return None
key = name.lower().strip()
if key in CLINIC_ALIASES:
return CLINIC_ALIASES[key]
for v in CLINIC_ALIASES.values():
if v.lower() == key:
return v
return name.strip()

def get_sheets_client():
creds_json = os.environ.get(“GOOGLE_CREDS_JSON”, “”)
if not creds_json:
raise Exception(“GOOGLE_CREDS_JSON missing!”)
creds_dict = json.loads(creds_json)
scope = [
“https://spreadsheets.google.com/feeds”,
“https://www.googleapis.com/auth/drive”
]
with tempfile.NamedTemporaryFile(mode=“w”, suffix=”.json”, delete=False) as f:
json.dump(creds_dict, f)
tmp = f.name
creds = ServiceAccountCredentials.from_json_keyfile_name(tmp, scope)
os.unlink(tmp)
return gspread.authorize(creds)

def save_booking(clinic_raw, patient_name, patient_phone, date, time, step=“Follow-up”, comment=””):
try:
clinic = normalize_clinic(clinic_raw)
gc = get_sheets_client()
ss = gc.open_by_key(SPREADSHEET_ID)
try:
ws = ss.worksheet(clinic)
except gspread.WorksheetNotFound:
ws = ss.add_worksheet(title=clinic, rows=1000, cols=15)
ws.append_row([“Patient name”,“Next Visit”,“Time”,“Treatment step”,“Source”,“Comment”,“Secretary”,“Total”,“Deposit”,“Installments”,“Phone”,“booking_id”,“created_at”])
bid = “B” + datetime.now(CAIRO_TZ).strftime(”%d%m%H%M%S”)
now = datetime.now(CAIRO_TZ).strftime(”%Y-%m-%d %H:%M:%S”)
ws.append_row([patient_name, date, time, step, “whatsapp”, comment, “”, “”, “”, “”, patient_phone, bid, now])
try:
lg = ss.worksheet(“logs”)
except Exception:
lg = ss.add_worksheet(title=“logs”, rows=1000, cols=6)
lg.append_row([“ts”,“action”,“status”,“clinic”,“phone”,“message”])
lg.append_row([now, “saveBooking”, “ok”, clinic, patient_phone, “Saved “ + bid])
log.info(“Saved: “ + bid)
return {“status”: “ok”, “booking_id”: bid, “clinic”: clinic}
except Exception as e:
log.error(“Sheets error: “ + str(e))
return {“status”: “error”, “message”: str(e)}

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

def sara_think(phone, user_message, is_doctor=False):
add_message(phone, “user”, user_message)
history = get_history(phone)
extra = “\n[Admin Mode - aldktwr mHmwd]” if is_doctor else “”
tools = [{
“type”: “function”,
“function”: {
“name”: “save_booking”,
“description”: “احجز موعد مريض لما تجمع الاسم والموبايل والعيادة والتاريخ والوقت”,
“parameters”: {
“type”: “object”,
“properties”: {
“clinic”:        {“type”: “string”},
“patient_name”:  {“type”: “string”},
“patient_phone”: {“type”: “string”},
“date”:          {“type”: “string”},
“time”:          {“type”: “string”},
“step”:          {“type”: “string”},
“comment”:       {“type”: “string”}
},
“required”: [“clinic”, “patient_name”, “patient_phone”, “date”, “time”]
}
}
}]
messages = [{“role”: “system”, “content”: SARA_SYSTEM + extra}] + history
response = ai.chat.completions.create(
model=“gpt-4o”, messages=messages, tools=tools,
tool_choice=“auto”, temperature=0.7, max_tokens=400
)
msg = response.choices[0].message
if msg.tool_calls:
tool_results = []
for tc in msg.tool_calls:
fn_args = json.loads(tc.function.arguments)
result = save_booking(
fn_args.get(“clinic”), fn_args.get(“patient_name”),
fn_args.get(“patient_phone”), fn_args.get(“date”),
fn_args.get(“time”), fn_args.get(“step”, “Follow-up”),
fn_args.get(“comment”, “”)
)
tool_results.append({“tool_call_id”: tc.id, “role”: “tool”, “content”: json.dumps(result, ensure_ascii=False)})
messages2 = messages + [msg] + tool_results
response2 = ai.chat.completions.create(model=“gpt-4o”, messages=messages2, temperature=0.7, max_tokens=300)
reply = response2.choices[0].message.content
else:
reply = msg.content
add_message(phone, “assistant”, reply)
return reply

def send_whatsapp(to, text):
url = “https://graph.facebook.com/v19.0/” + WA_PHONE_ID + “/messages”
try:
r = requests.post(url,
headers={“Authorization”: “Bearer “ + WA_TOKEN, “Content-Type”: “application/json”},
json={“messaging_product”: “whatsapp”, “to”: to, “type”: “text”, “text”: {“body”: text}},
timeout=10)
log.info(“WA sent: “ + str(r.status_code))
except Exception as e:
log.error(“WA error: “ + str(e))

@app.route(”/webhook”, methods=[“GET”])
def verify():
mode      = request.args.get(“hub.mode”)
token     = request.args.get(“hub.verify_token”)
challenge = request.args.get(“hub.challenge”)
if mode == “subscribe” and token == VERIFY_TOKEN:
return challenge, 200
return “Forbidden”, 403

@app.route(”/webhook”, methods=[“POST”])
def webhook():
data = request.get_json(silent=True) or {}
try:
msgs = data.get(“entry”,[{}])[0].get(“changes”,[{}])[0].get(“value”,{}).get(“messages”,[])
for msg in msgs:
sender   = msg.get(“from”, “”)
msg_type = msg.get(“type”, “”)
if msg_type == “text”:
text = msg.get(“text”, {}).get(“body”, “”).strip()
else:
text = “[” + msg_type + “]”
if not text:
continue
is_doctor = sender.replace(”+”, “”) == DOCTOR_PHONE
reply = sara_think(sender, text, is_doctor=is_doctor)
send_whatsapp(sender, reply)
except Exception as e:
log.error(“Webhook error: “ + str(e))
return jsonify({“status”: “ok”}), 200

@app.route(”/health”, methods=[“GET”])
def health():
return jsonify({“status”: “sara is alive”, “time”: datetime.now(CAIRO_TZ).isoformat()})

@app.route(”/test”, methods=[“POST”])
def test():
body  = request.get_json(silent=True) or {}
reply = sara_think(body.get(“phone”, “test”), body.get(“message”, “مرحبا”), body.get(“is_doctor”, False))
return jsonify({“reply”: reply})

if **name** == “**main**”:
app.run(host=“0.0.0.0”, port=int(os.environ.get(“PORT”, 5000)))
