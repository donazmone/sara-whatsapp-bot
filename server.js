const express = require("express");
const OpenAI = require("openai");

const app = express();
app.use(express.json());

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

const VERIFY_TOKEN = process.env.VERIFY_TOKEN;
const WHATSAPP_TOKEN = process.env.WHATSAPP_TOKEN;
const PHONE_NUMBER_ID = process.env.PHONE_NUMBER_ID;

/* ===== Verify Webhook ===== */
app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode && token === VERIFY_TOKEN) {
    return res.status(200).send(challenge);
  }

  return res.sendStatus(403);
});

/* ===== Incoming Messages ===== */
app.post("/webhook", async (req, res) => {
  try {
    const entry = req.body.entry?.[0];
    const changes = entry?.changes?.[0];
    const message = changes?.value?.messages?.[0];

    if (!message) return res.sendStatus(200);

    const from = message.from;
    const text = message.text?.body;

    if (!text) return res.sendStatus(200);

    console.log("Incoming:", text);

    /* ===== AI Brain ===== */
    const completion = await client.chat.completions.create({
      model: "gpt-5-2",
      messages: [
        {
          role: "system",
          content: `
اسمك سارة.

أنتِ سكرتيرة خاصة لدكتور تقويم أسنان في مصر.
وظيفتك تنظيم المواعيد والرد على المرضى فقط.

أسلوبك:
- كلام مصري طبيعي جداً
- ردود قصيرة جداً
- هادئة وبشرية
- لا تكتبي رسائل طويلة
- لا تسألي أكثر من سؤال واحد في الرسالة
- لا تشرحي كثيراً
- لا تعرضي خدمات طبية
- لا تتحدثي كعيادة عامة

طريقة التعامل:

لو المريض يريد حجز:
→ اسألي سؤال واحد فقط لتحديد الفرع

الفروع المتاحة:
التجمع الخامس
المقطم
حدائق أكتوبر
السلام
كرداسة
المنيل
مدينة نصر
شيراتون
عيادة دكتور بنداري المنيل

بعد اختيار الفرع:

- أي فرع غير بنداري → أعطي رقم السكرتيرة فقط
- بنداري → كمّلي حجز

لو المريض يسأل عن السعر:
→ اسأليه في أنهي فرع أولاً

ممنوع:
- الأسئلة الكثيرة
- القوائم الطويلة
- الكلام الطبي
- الردود الرسمية
`
        },
        {
          role: "user",
          content: text,
        },
      ],
    });

    const reply = completion.choices[0].message.content;

    console.log("Sara:", reply);

    /* ===== Send WhatsApp Reply ===== */
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
          to: from,
          type: "text",
          text: { body: reply },
        }),
      }
    );

    res.sendStatus(200);
  } catch (error) {
    console.log("ERROR:", error.response?.data || error.message);
    res.sendStatus(200);
  }
});

/* ===== Health Check ===== */
app.get("/", (req, res) => {
  res.send("Sara server running");
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log("Server running on port", PORT));
