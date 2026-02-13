const express = require("express");
const axios = require("axios");
const OpenAI = require("openai");

const app = express();
app.use(express.json());

/* ================= CONFIG ================= */

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

const openai = new OpenAI({ apiKey: OPENAI_API_KEY });

/* ================= AI BRAIN ================= */

async function generateAIReply(message) {
  try {
    const response = await openai.responses.create({
      model: "gpt-5-2",
      input: `أنتِ سكرتيرة عيادة تقويم أسنان في مصر. اسمك سارة.

أسلوبك:
- مصرية طبيعية جدًا
- ودودة وبشرية
- مختصرة
- غير رسمية
- غير روبوتية
- تفهمي الأخطاء الإملائية

رسالة المريض:
"${message}"

ردي بشكل بشري طبيعي جدًا.`
    });

    return response.output[0].content[0].text;

  } catch (err) {
    console.log("AI Error:", err.message);
    return "معلش حصل مشكلة بسيطة، ابعتلي تاني 🙏";
  }
}

/* ================= SEND WHATSAPP ================= */

async function sendWhatsAppMessage(to, text) {
  try {
    await axios.post(
      `https://graph.facebook.com/v18.0/${PHONE_NUMBER_ID}/messages`,
      {
        messaging_product: "whatsapp",
        to: to,
        text: { body: text }
      },
      {
        headers: {
          Authorization: `Bearer ${WHATSAPP_TOKEN}`,
          "Content-Type": "application/json"
        }
      }
    );
  } catch (err) {
    console.log("WhatsApp Send Error:", err.message);
  }
}

/* ================= WEBHOOK VERIFY ================= */

app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    console.log("Webhook verified");
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

/* ================= WEBHOOK RECEIVE ================= */

app.post("/webhook", async (req, res) => {
  try {
    const entry = req.body.entry?.[0];
    const changes = entry?.changes?.[0];
    const value = changes?.value;
    const message = value?.messages?.[0];

    if (!message) {
      return res.sendStatus(200);
    }

    const from = message.from;
    const text = message.text?.body;

    if (!text) {
      return res.sendStatus(200);
    }

    console.log("Incoming:", text);

    const reply = await generateAIReply(text);

    await sendWhatsAppMessage(from, reply);

    res.sendStatus(200);

  } catch (err) {
    console.log("Webhook Error:", err.message);
    res.sendStatus(200);
  }
});

/* ================= START SERVER ================= */

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log("Server running");
});
