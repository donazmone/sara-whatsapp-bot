import express from "express";
import fetch from "node-fetch";
import OpenAI from "openai";

const app = express();
app.use(express.json());

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

/* ===== Memory Store ===== */
/* لكل مريض نحفظ آخر محادثة */
const conversations = new Map();

function getHistory(user) {
  if (!conversations.has(user)) {
    conversations.set(user, []);
  }
  return conversations.get(user);
}

function pushMessage(user, role, content) {
  const history = getHistory(user);
  history.push({ role, content });

  /* نحدد حد أقصى للذاكرة */
  if (history.length > 20) {
    history.shift();
  }
}

/* ===== Health Check ===== */
app.get("/", (req, res) => {
  res.send("Sara AI Brain Running");
});

/* ===== Webhook Verification ===== */
app.get("/webhook", (req, res) => {
  const verify_token = process.env.VERIFY_TOKEN;

  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode && token === verify_token) {
    return res.status(200).send(challenge);
  }

  res.sendStatus(403);
});

/* ===== Incoming WhatsApp Messages ===== */
app.post("/webhook", async (req, res) => {
  try {
    const message =
      req.body?.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

    if (!message) return res.sendStatus(200);

    const from = message.from;
    const text = message.text?.body;

    if (!text) return res.sendStatus(200);

    console.log("Incoming:", from, text);

    /* نحفظ رسالة المريض */
    pushMessage(from, "user", text);

    const history = getHistory(from);

    const completion = await client.chat.completions.create({
      model: "gpt-5-mini",
      messages: [
        {
          role: "system",
          content: `
اسمك سارة.
سكرتيرة عيادات أسنان في مصر.
شخصيتك بشرية جداً، مصرية طبيعية.
ردود قصيرة جداً.
ودودة، هادئة، مش رسمية.
لا تشرحي كثيراً.
لا تسألي نفس السؤال مرتين.
افهمي سياق الكلام السابق.
لو المريض يسأل عن سعر → ردي بشكل منطقي.
لو حجز → ساعديه.
لو لخبط → صححي بهدوء.
          `,
        },
        ...history,
      ],
    });

    const reply = completion.choices[0].message.content;

    /* نحفظ رد سارة */
    pushMessage(from, "assistant", reply);

    await fetch(
      `https://graph.facebook.com/v18.0/${process.env.PHONE_NUMBER_ID}/messages`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${process.env.WHATSAPP_TOKEN}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          messaging_product: "whatsapp",
          to: from,
          text: { body: reply },
        }),
      }
    );

    res.sendStatus(200);
  } catch (err) {
    console.error("ERROR:", err);
    res.sendStatus(200);
  }
});

const PORT = process.env.PORT || 10000;

app.listen(PORT, () => {
  console.log("Server running on port", PORT);
});
