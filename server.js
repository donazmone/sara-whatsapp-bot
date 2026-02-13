const express = require("express");
const axios = require("axios");
require("dotenv").config();

const app = express();
app.use(express.json());

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

/* =========================
   Clinic Mapping
========================= */

const clinics = {
  "التجمع الخامس": { type: "redirect", phone: "PerlaDent" },
  "المقطم": { type: "redirect", phone: "Smile" },
  "حدائق اكتوبر": { type: "redirect", phone: "Paradise" },
  "السلام": { type: "redirect", phone: "Elsalam" },
  "كرداسة": { type: "redirect", phone: "Kerdasa" },
  "مدينة نصر": { type: "redirect", phone: "Alaa Eldeen" },
  "شيراتون": { type: "redirect", phone: "Cornerstone" },
  "المنيل عيادة سرور": { type: "redirect", phone: "SDC" },
  "عيادة دكتور بنداري المنيل": { type: "bandari" }
};

/* =========================
   Helper Functions
========================= */

async function askOpenAI(message) {
  const response = await axios.post(
    "https://api.openai.com/v1/chat/completions",
    {
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content: `
أنت سكرتيرة ذكية اسمها سارة.
تتكلمي مصري طبيعي.
ردود قصيرة.
هدفك تفهمي المريض وتساعديه يحجز.
لو مش محدد عيادة اسأليه يحب يحجز في أنهي عيادة.
`
        },
        { role: "user", content: message }
      ]
    },
    {
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`
      }
    }
  );

  return response.data.choices[0].message.content;
}

async function sendWhatsApp(to, text) {
  await axios.post(
    `https://graph.facebook.com/v19.0/${PHONE_NUMBER_ID}/messages`,
    {
      messaging_product: "whatsapp",
      to,
      text: { body: text }
    },
    {
      headers: {
        Authorization: `Bearer ${WHATSAPP_TOKEN}`
      }
    }
  );
}

/* =========================
   Webhook Verification
========================= */

app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode && token === VERIFY_TOKEN) {
    return res.status(200).send(challenge);
  }

  res.sendStatus(403);
});

/* =========================
   Incoming Messages
========================= */

app.post("/webhook", async (req, res) => {
  try {
    const entry = req.body.entry?.[0];
    const changes = entry?.changes?.[0];
    const message = changes?.value?.messages?.[0];

    if (!message) return res.sendStatus(200);

    const from = message.from;
    const text = message.text?.body;

    if (!text) return res.sendStatus(200);

    console.log("Message:", text);

    /* ===== Clinic Detection ===== */

    const matchedClinic = Object.keys(clinics).find(c =>
      text.includes(c)
    );

    if (matchedClinic) {
      const clinic = clinics[matchedClinic];

      if (clinic.type === "redirect") {
        await sendWhatsApp(
          from,
          `تمام 👍 تواصلي مع سكرتارية الفرع ده:\n${clinic.phone}`
        );
      } else {
        await sendWhatsApp(
          from,
          "تمام 👍 أقرب ميعاد متاح لبنداري بكرة الساعة 5"
        );
      }

      return res.sendStatus(200);
    }

    /* ===== No Clinic → AI Brain ===== */

    const aiReply = await askOpenAI(text);

    await sendWhatsApp(from, aiReply);

    res.sendStatus(200);
  } catch (err) {
    console.error(err.response?.data || err.message);
    res.sendStatus(200);
  }
});

/* ========================= */

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log("Sara running...");
});
