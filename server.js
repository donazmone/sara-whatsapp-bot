const express = require("express");
const fetch = require("node-fetch");
const OpenAI = require("openai");

const app = express();
app.use(express.json());

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;

app.get("/", (req, res) => {
  res.send("Sara server running ✅");
});

app.get("/webhook", (req, res) => {
  res.send("Webhook working ✅");
});

// Meta verification
app.get("/webhook/verify", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode && token === VERIFY_TOKEN) {
    return res.status(200).send(challenge);
  }

  return res.sendStatus(403);
});

// Incoming messages
app.post("/webhook", async (req, res) => {
  try {
    const message =
      req.body?.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

    if (!message) return res.sendStatus(200);

    const from = message.from;
    const text = message.text?.body;

    if (!text) return res.sendStatus(200);

    console.log("Incoming:", text);

    const ai = await client.responses.create({
      model: "gpt-5-mini",
      input: `رد كمساعدة اسمها سارة، سكرتيرة عيادات أسنان في مصر. 
      كلامك يكون مصري طبيعي جداً وقصير.
      رسالة المريض: ${text}`,
    });

    const reply = ai.output[0].content[0].text;

    await fetch(
      `https://graph.facebook.com/v19.0/${PHONE_NUMBER_ID}/messages`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${WHATSAPP_TOKEN}`,
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
    console.log(err);
    res.sendStatus(200);
  }
});

const PORT = process.env.PORT || 3000;

app.listen(PORT, () => {
  console.log("Server running on port", PORT);
});
