const express = require('express');
const app = express();

app.use(express.json());

// Log every incoming request so we can see what Telegram sends
app.use((req, res, next) => {
  console.log(`${new Date().toISOString()} ${req.method} ${req.path}`);
  next();
});

// Root — health check + sanity
app.get('/', (req, res) => res.send('BOAT Relay is alive.'));

// Webhook — accept both GET (for testing) and POST (for Telegram)
app.all('/webhook', async (req, res) => {
  console.log('WEBHOOK HIT', req.method);
  const msg = (req.body && (req.body.message || req.body.channel_post)) || null;

  if (msg && msg.text) {
    const chatId = String(msg.chat.id);
    const text = msg.text.trim();

    const allowed = (process.env.TELEGRAM_ALLOWED || '')
      .split(',').map(s => s.trim()).filter(Boolean);
    if (!allowed.length || allowed.includes(chatId)) {
      try {
        const r = await fetch(
          `https://api.github.com/repos/${process.env.GITHUB_REPO}/dispatches`,
          {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${process.env.BOAT_GH_TOKEN}`,
              'Accept': 'application/vnd.github+json',
              'Content-Type': 'application/json',
              'User-Agent': 'boat-relay'
            },
            body: JSON.stringify({
              event_type: 'boat-command',
              client_payload: { command: text, chat_id: chatId }
            })
          }
        );
        console.log('dispatched', r.status);
      } catch (e) {
        console.error('dispatch failed:', e.message);
      }
    }
  }

  res.sendStatus(200);
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`BOAT relay listening on ${PORT}`));
