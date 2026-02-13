import express from "express";
import fetch from "node-fetch";

const app = express();
app.use(express.json());

const OPENAI_KEY = process.env.OPENAI_KEY;

async function askAI(message) {
  const response = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${OPENAI_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "أنتِ سكرتيرة مواعيد مصرية اسمها سارة. أسلوبك بسيط، ودود، طبيعي جدًا. ردودك قصيرة ومش رسمية. لا تكرري الكلام.",
        },
        {
          role: "user",
          content: message,
        },
      ],
    }),
  });

  const data = await response.json();
  return data.choices[0].message.content;
}

app.post("/webhook", async (req, res) => {
  try {
    const incomingMessage =
      req.body?.entry?.[0]?.changes?.[0]?.value?.messages?.[0]?.text?.body;

    if (!incomingMessage) return res.sendStatus(200);

    const reply = await askAI(incomingMessage);

    console.log("User:", incomingMessage);
    console.log("Sara:", reply);

    res.sendStatus(200);
  } catch (err) {
    console.log(err);
    res.sendStatus(200);
  }
});

app.get("/", (req, res) => {
  res.send("Sara server running");
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Server running"));
