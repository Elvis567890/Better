const express = require('express');
const app = express();
app.use(express.json());
const PORT = process.env.PORT || 10000;

app.post('/webhook', async (req, res) => {
  const msg = req.body.message || req.body.channel_post;
  if (!msg || !msg.text) return res.sendStatus(200);

  const chatId = String(msg.chat.id);
  const text = msg.text.trim();

  // Optional: restrict to allowed chats
  const allowed = (process.env.TELEGRAM_ALLOWED || '')
    .split(',').map(s => s.trim()).filter(Boolean);
  if (allowed.length && !allowed.includes(chatId)) {
    return res.sendStatus(200);
  }

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
    console.error('GitHub dispatch failed:', e);
  }

  res.sendStatus(200);
});

app.get('/', (req, res) => res.send('BOAT Relay is alive.'));

app.listen(PORT, () => console.log(`BOAT relay listening on ${PORT}`));
