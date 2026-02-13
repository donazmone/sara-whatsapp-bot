const express = require("express");
const axios = require("axios");

const app = express();
app.use(express.json());

/* ================= ENV ================= */

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;
const DOCTOR_NUMBER = process.env.DOCTOR_NUMBER;

/* ================= HELPERS ================= */

async function sendText(to, body) {
    try {
        await axios.post(
            `https://graph.facebook.com/v18.0/${PHONE_NUMBER_ID}/messages`,
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
                }
            }
        );
    } catch (err) {
        console.error("SEND ERROR:", err.response?.data || err.message);
    }
}

function detectIntent(text) {
    text = text.toLowerCase();

    if (text.includes("حجز") || text.includes("ميعاد") || text.includes("موعد"))
        return "booking";

    if (text.includes("تعديل") || text.includes("تأجيل") || text.includes("تغيير"))
        return "reschedule";

    if (text.includes("متابعة"))
        return "followup";

    if (text.includes("ألم") || text.includes("وجع") || text.includes("طارئ"))
        return "urgent";

    return "unknown";
}

/* ================= WEBHOOK VERIFY ================= */

app.get("/webhook", (req, res) => {
    const mode = req.query["hub.mode"];
    const token = req.query["hub.verify_token"];
    const challenge = req.query["hub.challenge"];

    if (mode && token === VERIFY_TOKEN) {
        return res.status(200).send(challenge);
    }

    res.sendStatus(403);
});

/* ================= WEBHOOK RECEIVE ================= */

app.post("/webhook", async (req, res) => {
    try {
        const entry = req.body.entry?.[0];
        const changes = entry?.changes?.[0];
        const value = changes?.value;
        const message = value?.messages?.[0];

        if (!message) return res.sendStatus(200);

        const from = message.from;
        const text = message.text?.body;

        if (!text) return res.sendStatus(200);

        console.log("INCOMING:", text);

        const intent = detectIntent(text);

        let reply;

        switch (intent) {
            case "booking":
                reply = "تمام يا فندم ✅ تحب أحجز لحضرتك في أنهي عيادة؟";
                break;

            case "reschedule":
                reply = "حاضر يا فندم 👌 ابعتلي اسم العيادة والميعاد القديم.";
                break;

            case "followup":
                reply = "تمام ✅ ابعتلي اسم العيادة عشان أشوف أقرب متابعة.";
                break;

            case "urgent":
                reply = "ثانية واحدة يا فندم ⚠️ هبلغ الدكتور حالًا.";
                await sendText(DOCTOR_NUMBER, `⚠️ حالة طارئة من رقم ${from}\n\n${text}`);
                break;

            default:
                reply = "تمام يا فندم ✅ تحت أمرك.";
        }

        await sendText(from, reply);

        res.sendStatus(200);
    } catch (err) {
        console.error("WEBHOOK ERROR:", err.message);
        res.sendStatus(200);
    }
});

/* ================= ROOT ================= */

app.get("/", (req, res) => {
    res.send("Sara is running");
});

/* ================= START ================= */

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log("Server running on", PORT));
