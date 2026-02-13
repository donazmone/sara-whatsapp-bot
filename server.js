const express = require("express");
const axios = require("axios");

const app = express();
app.use(express.json());

const VERIFY_TOKEN = "sara_verify_token";
const WHATSAPP_TOKEN = "EAAKp8HUOhQABQuXXHfKUIAqzGZCOuaKdm0EzPHcD8GUJPvummnJVkmWdGzWrCr07lmflYo3YOGLkKZCrIyZBU2Q6m6vbkyZBahtPWPO1BlTZC1C7oSqnWS1j910ZCkHiMmwLlnrE76Y3a0t6p2lych7HTWRFZBZAuKRm7VG2hMbxwZAsgbAFUQZCStPgbLwfMiyRkXCzZBjPmqqK0vLVbCPpoXZA2124pIsUXS1VkPnkboTaHB4OuYtZB3XDxXDvXdJPVa4lioo9wmBxSF3nZAoGNztLxZCfAKyJ2tfusIZD";

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
        console.log(JSON.stringify(req.body, null, 2));
        res.sendStatus(200);
    } catch (e) {
        res.sendStatus(500);
    }
});

app.get("/", (req, res) => {
    res.send("Sara server running");
});

app.listen(3000, () => console.log("Server running"));
