const express = require("express");
const axios = require("axios");

const app = express();
app.use(express.json());

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;

app.get("/webhook", (req, res) => {
    const mode = req.query["hub.mode"];
    const token = req.query["hub.verify_token"];
    const challenge = req.query["hub.challenge"];

    if (mode && token === VERIFY_TOKEN) {
        return res.status(200).send(challenge);
    }

    res.sendStatus(403);
});

app.post("/webhook", async (req, res) => {
    try {
        const message =
            req.body.entry?.[0]?.changes?.[0]?.value?.messages?.[0];

        if (!message) {
            return res.sendStatus(200);
        }

        const from = message.from;
        const text = message.text?.body;

        console.log("Incoming:", text);

        await axios.post(
            `https://graph.facebook.com/v18.0/${PHONE_NUMBER_ID}/messages`,
            {
                messaging_product: "whatsapp",
                to: from,
                text: { body: "سارة شغالة 👍" }
            },
            {
                headers: {
                    Authorization: `Bearer ${WHATSAPP_TOKEN}`,
                    "Content-Type": "application/json"
                }
            }
        );

        res.sendStatus(200);
    } catch (err) {
        console.log("ERROR:", err.response?.data || err.message);
        res.sendStatus(200);
    }
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log("Server running on port", PORT));
