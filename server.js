const express = require("express");
const OpenAI = require("openai");

const app = express();
app.use(express.json());

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;

const CLINICS = {
  "التجمع الخامس": "PerlaDent",
  "المقطم": "Smile",
  "حدائق اكتوبر": "Paradise",
  "السلام": "Elsalam",
  "كرداسة": "Kerdasa",
  "مدينة نصر": "Alaa Eldeen",
  "شيراتون": "Cornerstone",
  "المنيل": "SDC",
  "بنداري": "Bandari"
};

const SECRETARY_NUMBERS = {
  PerlaDent: "0100XXXXXXX",
  Smile: "0101XXXXXXX",
  Paradise: "0102XXXXXXX",
  Elsalam: "0103XXXXXXX",
  Kerdasa: "0104XXXXXXX",
  Alaa_Eldeen: "0105XXXXXXX",
  Cornerstone: "0106XXXXXXX",
  SDC: "0107XXXXXXX",
};

async function detectIntent(message) {
  const completion = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      { role: "system", content: "Extract intent: booking / question / other" },
      { role: "user", content: message }
    ],
  });

  return completion.choices[0].message.content.toLowerCase();
}

async function generateReply(userMessage) {
  const completion = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: `
أنتِ سارة، سكرتيرة عيادات تقويم أسنان في مصر.

أسلوبك:
- مصري طبيعي جداً
- ردود قصيرة
- ودودة وهادية
- مفيش كلام رسمي
- مفيش رسايل طويلة
- سؤال واحد فقط في كل رد

مهمتك:
- لو المريض عايز يحجز → اسأليه عن المنطقة
- المناطق المتاحة:
التجمع الخامس - المقطم - حدائق اكتوبر - السلام - كرداسة - المنيل - مدينة نصر - شيراتون - عيادة دكتور بنداري المنيل

القواعد:
- لو اختار أي فرع غير بنداري → ابعتي رقم السكرتيرة فقط
- لو بنداري → قولي له هظبط أقرب ميعاد

ممنوع:
- شروحات طويلة
- اختيارات كثيرة
- أسئلة متعددة
`
      },
      { role: "user", content: userMessage }
    ],
  });

  return completion.choices[0].message.content;
}

async function sendWhatsAppMessage(to, text) {
  await fetch(`https://graph.facebook.com/v18.0/${PHONE_NUMBER_ID}/messages`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${WHATSAPP_TOKEN}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      messaging_product: "whatsapp",
      to,
      type: "text",
      text: { body: text },
    }),
  });
}

app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode && token === VERIFY_TOKEN) {
    res.status(200).send(challenge);
  } else {
    res.sendStatus(403);
  }
});

app.post("/webhook", async (req, res) => {
  try {
    const message =
      req.body.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

    if (!message) return res.sendStatus(200);

    const from = message.from;
    const text = message.text?.body;

    if (!text) return res.sendStatus(200);

    console.log("Incoming:", text);

    const reply = await generateReply(text);

    await sendWhatsAppMessage(from, reply);

    res.sendStatus(200);
  } catch (err) {
    console.error(err);
    res.sendStatus(200);
  }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => {
  console.log("Server running on port", PORT);
});