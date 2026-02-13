import express from "express";
import axios from "axios";
import stringSimilarity from "string-similarity";
import { google } from "googleapis";

const app = express();
app.use(express.json());

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;

const creds = JSON.parse(process.env.GOOGLE_CREDS);

const auth = new google.auth.GoogleAuth({
  credentials: creds,
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

const sheets = google.sheets({ version: "v4", auth });

const SHEET_ID = "1hI5My8jrH-4W8dX7UCaWCFCjImevDjfoQ-0N0cfRBSk";

async function sendMessage(to, text) {
  await axios.post(
    `https://graph.facebook.com/v18.0/${PHONE_NUMBER_ID}/messages`,
    {
      messaging_product: "whatsapp",
      to,
      text: { body: text },
    },
    {
      headers: {
        Authorization: `Bearer ${WHATSAPP_TOKEN}`,
        "Content-Type": "application/json",
      },
    }
  );
}

const INTENTS = {
  greeting: ["مساء الخير", "صباح الخير", "السلام", "هاي"],
  booking: ["معاد", "ميعاد", "احجز", "عايز معاد"],
};

function detectIntent(text) {
  let bestMatch = { rating: 0, intent: null };

  for (const intent in INTENTS) {
    const match = stringSimilarity.findBestMatch(text, INTENTS[intent]);
    if (match.bestMatch.rating > bestMatch.rating) {
      bestMatch = {
        rating: match.bestMatch.rating,
        intent,
      };
    }
  }

  if (bestMatch.rating < 0.35) return "unknown";

  return bestMatch.intent;
}

function reply(intent) {
  switch (intent) {
    case "greeting":
      return "مساء النور 🌸 تحت أمرك";

    case "booking":
      return "تمام 👍 تحب أنهي يوم؟";

    default:
      return "ممكن توضّحلي أكتر؟ 😊";
  }
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
    const msg =
      req.body.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

    if (!msg) return res.sendStatus(200);

    const from = msg.from;
    const text = msg.text?.body;

    if (!text) return res.sendStatus(200);

    const intent = detectIntent(text);

    await sendMessage(from, reply(intent));

    res.sendStatus(200);
  } catch (err) {
    console.log(err.message);
    res.sendStatus(200);
  }
});

app.listen(3000, () => console.log("Sara running"));
