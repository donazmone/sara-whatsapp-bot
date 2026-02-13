const express = require("express");
const axios = require("axios");

const app = express();
app.use(express.json());

// =======================
// REQUIRED ENV VARS
// =======================
const VERIFY_TOKEN     = process.env.VERIFY_TOKEN;      // مثال: sara_verify_token
const WHATSAPP_TOKEN   = process.env.WHATSAPP_TOKEN;    // Access Token
const PHONE_NUMBER_ID  = process.env.PHONE_NUMBER_ID;   // Phone Number ID (لسارة)
const DOCTOR_NUMBER    = process.env.DOCTOR_NUMBER;     // رقمك لاستقبال التنبيهات بصيغة 20XXXXXXXXXX
const GRAPH_VERSION    = process.env.GRAPH_VERSION || "v22.0";

// Optional tuning
const MAX_USER_MSG_LEN = Number(process.env.MAX_USER_MSG_LEN || 350); // لو الرسالة طويلة نرجّع للدكتور
const SILENT_ON_UNK    = (process.env.SILENT_ON_UNKNOWN || "1") === "1"; // لو مش فاهمة: لا ترد + ابعت للدكتور
const OFFICE_END_HHMM  = process.env.OFFICE_END_HHMM || "19:30"; // للمنطق لاحقًا (مش مُلزم الآن)

// =======================
// BASIC VALIDATION
// =======================
function must(v, name) {
  if (!v) throw new Error(`Missing env var: ${name}`);
}
try {
  must(VERIFY_TOKEN, "VERIFY_TOKEN");
  must(WHATSAPP_TOKEN, "WHATSAPP_TOKEN");
  must(PHONE_NUMBER_ID, "PHONE_NUMBER_ID");
  must(DOCTOR_NUMBER, "DOCTOR_NUMBER");
} catch (e) {
  console.error(e.message);
  // نخلي السيرفر يقوم لكن يوضح في اللوجز. Render هيعتبره شغال، لكن هتشوف الخطأ.
}

// =======================
// DEDUPE (Meta may retry)
// =======================
const seenMsgIds = new Map(); // msg_id -> timestamp
const SEEN_TTL_MS = 10 * 60 * 1000; // 10 minutes

function markSeen(id) {
  const now = Date.now();
  seenMsgIds.set(id, now);
  // تنظيف بسيط
  for (const [k, t] of seenMsgIds.entries()) {
    if (now - t > SEEN_TTL_MS) seenMsgIds.delete(k);
  }
}

function alreadySeen(id) {
  if (!id) return false;
  const t = seenMsgIds.get(id);
  if (!t) return false;
  return (Date.now() - t) <= SEEN_TTL_MS;
}

// =======================
// WhatsApp send helpers
// =======================
async function sendText(to, body) {
  if (!to) return;
  const url = `https://graph.facebook.com/${GRAPH_VERSION}/${PHONE_NUMBER_ID}/messages`;

  await axios.post(
    url,
    {
      messaging_product: "whatsapp",
      to,
      type: "text",
      text: { body }
    },
    {
      headers: {
        Authorization: `Bearer ${WHATSAPP_TOKEN}`,
        "Content-Type": "application/json"
      },
      timeout: 15000
    }
  );
}

async function notifyDoctor(summary) {
  // تنبيه لك على واتساب
  const msg = `🟦 تنبيه سارة\n${summary}`;
  await sendText(DOCTOR_NUMBER, msg);
}

// =======================
// Message understanding (simple + stable)
// =======================
function normalizeArabic(s) {
  return (s || "")
    .replace(/[إأآا]/g, "ا")
    .replace(/ى/g, "ي")
    .replace(/ؤ/g, "و")
    .replace(/ئ/g, "ي")
    .replace(/ة/g, "ه")
    .replace(/\s+/g, " ")
    .trim();
}

function detectIntent(textRaw) {
  const t = normalizeArabic(textRaw).toLowerCase();

  // كلمات مفتاحية أساسية
  const wantsNew = /كشف|اول مره|اول زيارة|new|first|حجز|ميعاد|موعد/.test(t);
  const wantsReschedule = /تغيير|غير|تقديم|تاخير|بدل|نقل|اجل|تعديل|reschedule|change/.test(t);
  const asksLocation = /لوكيشن|عنوان|فين|مكان|location|address/.test(t);
  const urgentAngry = /مستعجل|ضروري|طارئ|مهم|مش عاجب|زعلان|شكوى|غصب/.test(t);

  return { wantsNew, wantsReschedule, asksLocation, urgentAngry, norm: t };
}

function shouldEscalate(textRaw) {
  if (!textRaw) return true;
  if (textRaw.length > MAX_USER_MSG_LEN) return true;

  const t = normalizeArabic(textRaw);
  // لو رسالة “مبهمة جدًا”
  if (t.length < 2) return true;

  // لو فيها كلام معقد/طويل أو شتائم/توتر
  const hostile = /(حمار|غبي|زباله|قرف|وسخ)/.test(t);
  if (hostile) return true;

  return false;
}

function patientReplyTemplate(intent) {
  // رد محايد لطيف زي ما اتفقنا
  // من غير “ثانية واحدة” ومن غير ما نحسس الموضوع كبير
  if (intent.asksLocation) {
    // حسب تعليماتك: ما تبعتش لوكيشن إلا لما ترجع لك
    return null; // نرجّع للدكتور
  }

  if (intent.wantsReschedule) {
    return "تمام يا فندم، هراجع جدول المواعيد وأرتب التغيير المناسب لحضرتك ✅";
  }

  if (intent.wantsNew) {
    return "تمام يا فندم، هراجع أقرب ميعاد متاح وأرجع لحضرتك ✅";
  }

  // افتراضي
  return "تمام يا فندم ✅ وصلتني رسالتك.";
}

// =======================
// Health endpoint
// =======================
app.get("/", (req, res) => res.send("Sara server running ✅"));

// =======================
// Webhook verification (GET)
// =======================
app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    return res.status(200).send(challenge);
  }
  return res.sendStatus(403);
});

// =======================
// Webhook receiver (POST)
// =======================
app.post("/webhook", async (req, res) => {
  // مهم: نرد 200 بسرعة
  res.sendStatus(200);

  try {
    const value = req.body?.entry?.[0]?.changes?.[0]?.value;
    if (!value) return;

    // أحيانًا بييجي status فقط
    const msg = value?.messages?.[0];
    if (!msg) return;

    const msgId = msg.id;
    if (alreadySeen(msgId)) return;
    markSeen(msgId);

    const from = msg.from; // رقم المرسل بصيغة دولية بدون +
    const textBody = msg?.text?.body || "";

    console.log("INCOMING:", { from, msgId, textBody });

    // قرار التصعيد
    const intent = detectIntent(textBody);
    const escalate = shouldEscalate(textBody) || intent.urgentAngry || intent.asksLocation;

    if (escalate) {
      // لا نرد على المريض (حسب طلبك) لو SILENT_ON_UNK = 1
      // لكن نبلغك فورًا
      await notifyDoctor(
        `رسالة محتاجة قرار منك.\nمن: ${from}\nالنص: ${textBody}`
      );

      if (!SILENT_ON_UNK) {
        // خيار لو حبيت لاحقًا: رد بسيط جداً
        await sendText(from, "تمام يا فندم ✅");
      }
      return;
    }

    // رد مبدئي محترم
    const reply = patientReplyTemplate(intent);

    if (!reply) {
      // مثلا لو لوكيشن: ما نردش ونرجع للدكتور
      await notifyDoctor(
        `طلب لوكيشن/عنوان.\nمن: ${from}\nالنص: ${textBody}\n(مش هارد على المريض لحد ما تقوللي)`
      );
      return;
    }

    await sendText(from, reply);
    console.log("REPLIED:", { to: from });

  } catch (err) {
    console.error("WEBHOOK ERROR:", err?.response?.data || err.message);
    // لو حصل خطأ في الإرسال… بلغك
    try {
      await notifyDoctor(`خطأ في السيرفر/الإرسال:\n${err?.response?.data ? JSON.stringify(err.response.data) : err.message}`);
    } catch (_) {}
  }
});

// =======================
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Server running on", PORT));
