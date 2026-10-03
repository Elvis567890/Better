# BOAT Relay

Forwards Telegram messages to GitHub Actions (`boat-brain.yml`) via
repository_dispatch. All BOAT secrets stay in GitHub; this service
only needs two env vars.

## Deploy on Render

1. Render dashboard -> New + -> Web Service
2. Connect this repo (Elvis567890/Better)
3. Root Directory: `relay`
4. Build: `npm install`
5. Start: `node server.js`
6. Plan: Free
7. Add env vars:
   - BOAT_GH_TOKEN = ghp_...
   - GITHUB_REPO   = Elvis567890/Better
   - TELEGRAM_ALLOWED = 7683540555 (optional)
8. Deploy, then set the Telegram webhook:
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<your-app>.onrender.com/webhook
