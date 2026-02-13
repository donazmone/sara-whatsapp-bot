const express = require("express");
const fetch = require("node-fetch");
const OpenAI = require("openai");

const app = express();
app.use(express.json());

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

app.get("/", (req, res) => {
  res.send("Sara server running ✅");
});

app.post("/webhook", async (req, res) => {
  try {
    const body = req.body;

    if (!body.entry) return res.sendStatus(200);

    const message =
      body.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

    if (!message) return res.sendStatus(200);

    const from = message.from;
    const text = message.text?.body;

    console.log("Incoming:", text);

    if (!text) return res.sendStatus(200);

    const ai = await client.responses.create({
      model: "gpt-5-mini",
      input: `رد كمساعدة اسمها سارة وبالعامية المصرية: ${text}`,
    });

    let reply = "تمام 👍";

    if (ai.output && ai.output.length > 0) {
      const content = ai.output[0].content;

      if (content && content.length > 0) {
        reply = content[0].text || reply;
      }
    }

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
    console.log("CRASH ERROR:", err.message);
    res.sendStatus(200);
  }
});

app.listen(process.env.PORT || 3000, () => {
  console.log("Server running");
});
