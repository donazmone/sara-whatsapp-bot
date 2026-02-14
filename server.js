const express = require("express");
const fetch = require("node-fetch");
const OpenAI = require("openai");

const app = express();
app.use(express.json());

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

const openai = new OpenAI({ apiKey: OPENAI_API_KEY });

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

        if (!message) return res.sendStatus(200);

        const from = message.from;
        const text = message.text?.body;

        console.log("Incoming:", text);

        const aiReply = await askSara(text);

        await sendMessage(from, aiReply);

        res.sendStatus(200);
    } catch (err) {
        console.error(err);
        res.sendStatus(200);
    }
});

async function askSara(userMessage) {
    const response = await openai.responses.create({
        model: "gpt-5-mini",
        input: [
            {
                role: "system",
                content: `
أنت سكرتيرة عيادات أسنان اسمك سارة.
تتكلمي مصري طبيعي جدًا.
ردودك قصيرة وبشرية ومش رسمية.
وظيفتك:
- تفهمي المريض عايز ايه
- لو حجز → اسألي عن المنطقة
- المناطق المتاحة:
التجمع الخامس
المقطم
حدائق أكتوبر
السلام
كرداسة
المنيل
مدينة نصر
شيراتون
عيادة دكتور بنداري المنيل

لو المريض اختار أي عيادة غير بنداري → ادي رقم السكرتيرة فقط.

التوزيع:
التجمع → PerlaDent
المنيل → SDC
المقطم → Dr Smile
مدينة نصر → علاء الدين
أكتوبر → Paradise
شيراتون → Cornerstone
كرداسة → Kerdasa
السلام → Elsalam

مهم:
- ما تشرحيش كتير
- ما تفتحيش كلام خارج الحجز
- أسلوب بشري هادي
`
            },
            {
                role: "user",
                content: userMessage
            }
        ]
    });

    return response.output_text;
}

async function sendMessage(to, body) {
    await fetch(
        `https://graph.facebook.com/v18.0/${PHONE_NUMBER_ID}/messages`,
        {
            method: "POST",
            headers: {
                Authorization: `Bearer ${WHATSAPP_TOKEN}`,
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                messaging_product: "whatsapp",
                to,
                text: { body },
            }),
        }
    );
}

const PORT = process.env.PORT || 10000;
app.listen(PORT, () =>
    console.log("Server running on port", PORT)
);
