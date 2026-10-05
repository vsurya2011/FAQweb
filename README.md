# 🤖 FAQBot — Multi-Domain FAQ Chatbot (Python + Vercel)

A modern, NLP-powered FAQ chatbot that answers questions across **every domain** — technology, programming, science, health, finance, careers, travel, education and more. It matches questions against a built-in knowledge base using TF-IDF and cosine similarity, and falls back to **Google Gemini** for anything it doesn't know.

Built with a **Flask** backend, a **vanilla HTML/CSS/JS** frontend, and optional **Firebase Realtime Database** support. Deploys to **Vercel** in minutes.

---

## ✨ Features

- 🧠 **Custom NLP engine** — cleaning → tokenization → stop-word removal → stemming → TF-IDF → cosine similarity
- 🌍 **149 built-in FAQs** across 25+ domains (easy to extend)
- ✨ **Gemini AI fallback** for questions outside the knowledge base, with short chat memory
- 🎨 **Modern UI** — glassmorphism design, dark/light theme, topic filters, quick questions, copy button, mobile friendly
- 🔥 **Optional Firebase** — load extra FAQs from Realtime Database and log conversations
- 🔒 **Secure by design** — API keys stay on the server, input is validated and output is escaped
- ☁️ **Serverless** — zero-config deployment on Vercel

---

## 🏗️ How It Works

```
 User question
      │
      ▼
 ┌────────────────────┐   score ≥ 0.55    ┌──────────────────┐
 │ NLP matcher (TF-IDF│ ────────────────▶ │ Return FAQ answer │
 │ + cosine similarity)│                   └──────────────────┘
 └─────────┬──────────┘
           │ score < 0.55
           ▼
 ┌────────────────────┐   no AI / error   ┌──────────────────────────┐
 │ Gemini AI answer   │ ────────────────▶ │ Weak match or suggestions │
 └────────────────────┘                   └──────────────────────────┘
```

---

## 📁 Project Structure

```
faqbot-vercel/
├─ api/
│  └─ index.py         # Flask backend (NLP, Gemini, Firebase, routes)
├─ data/
│  └─ faqs.json        # Built-in FAQ knowledge base
├─ public/
│  └─ index.html       # Frontend UI
├─ requirements.txt    # Python dependencies
├─ vercel.json         # Vercel routing & function settings
├─ .env.example        # Environment variable template
└─ README.md
```

---

## 🚀 Quick Start (Local)

**Prerequisites:** Python 3.9+ and a Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey).

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your API key
export GEMINI_API_KEY="your_key_here"        # macOS / Linux
set GEMINI_API_KEY=your_key_here             # Windows (cmd)
$env:GEMINI_API_KEY="your_key_here"          # Windows (PowerShell)

# 3. Run the server
python api/index.py
```

Open **http://localhost:3000** in your browser.

> 💡 Without `GEMINI_API_KEY` the bot still works — it answers from the built-in FAQs and shows "Did you mean…?" suggestions when nothing matches.

---

## ☁️ Deploy to Vercel

1. Push this project to a **GitHub** repository.
2. Go to [vercel.com](https://vercel.com) → **Add New → Project** and import the repo.
3. Set **Framework Preset** to **Other**.
4. Open **Settings → Environment Variables** and add:

   | Name | Required | Description |
   |------|----------|-------------|
   | `GEMINI_API_KEY` | Yes (for AI) | Your Google Gemini API key |
   | `GEMINI_MODEL` | No | Defaults to `gemini-2.5-flash` |
   | `FIREBASE_DATABASE_URL` | No | Realtime Database URL |
   | `FIREBASE_SERVICE_ACCOUNT` | No | Service account JSON on **one line** |

5. Click **Deploy** 🎉

Or use the CLI:

```bash
npm i -g vercel
vercel          # preview deployment
vercel --prod   # production deployment
```

---

## 🔥 Optional: Firebase Setup

Firebase lets you manage FAQs from the cloud and keep chat logs.

1. Create a Realtime Database in the [Firebase Console](https://console.firebase.google.com).
2. Go to **Project settings → Service accounts → Generate new private key**.
3. Add `FIREBASE_DATABASE_URL` and `FIREBASE_SERVICE_ACCOUNT` (paste the JSON as a single line) to your Vercel environment variables.
4. Lock the database rules — the server uses admin access, so browsers never connect directly:

   ```json
   { "rules": { ".read": false, ".write": false } }
   ```

5. Add FAQs in the console under `faqs`:

   ```json
   {
     "faqs": {
       "faq1": {
         "category": "Campus",
         "question": "What are the library timings?",
         "answer": "9 AM to 6 PM on working days."
       }
     }
   }
   ```

Cloud FAQs are merged with the built-in ones (duplicates are removed) and cached for 5 minutes. Chat logs are saved under `chat_logs/<session-id>`.

---

## ➕ Adding Your Own FAQs

Edit `data/faqs.json` and add an entry:

```json
{
  "id": "my-faq-1",
  "category": "Campus",
  "question": "Where is the placement cell?",
  "answer": "The placement cell is in the Admin Block, 2nd floor."
}
```

A new category name automatically creates a new topic chip in the UI.

---

## 🔌 API Reference

### `GET /api/faqs`
Returns the FAQ list (without answers) and server status.

```json
{ "count": 149, "ai": true, "firebase": false, "faqs": [{ "id": "s0", "category": "General", "question": "Hello" }] }
```

### `POST /api/chat`
**Request**
```json
{
  "message": "How do I reset my password?",
  "sid": "optional-session-id",
  "history": [{ "role": "user", "text": "Hi" }, { "role": "model", "text": "Hello!" }]
}
```

**Response**
```json
{
  "answer": "Use the Forgot Password option on the login page…",
  "score": 0.84,
  "mode": "faq",
  "faq": { "id": "s39", "category": "Education", "question": "How do I reset my LMS or portal password?" },
  "suggestions": []
}
```
`mode` is `"faq"` (knowledge-base answer) or `"ai"` (Gemini answer).

### `GET /api/health`
Returns `{ "ok": true }`.

---

## ⚙️ Configuration

Tunable constants at the top of `api/index.py`:

| Constant | Default | Meaning |
|----------|---------|---------|
| `FAQ_THRESHOLD` | `0.55` | Minimum score to answer directly from an FAQ |
| `WEAK_THRESHOLD` | `0.30` | Minimum score to show an FAQ when AI is unavailable |
| `CACHE_TTL` | `300` | Seconds to cache the FAQ index |
| `MODEL` | `gemini-2.5-flash` | Gemini model (or set `GEMINI_MODEL`) |

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| Status shows **"Backend unreachable"** | Check the `/api/*` rewrite in `vercel.json` and the Vercel function logs |
| Answers never come from AI | Make sure `GEMINI_API_KEY` is set in Vercel and you **redeployed** afterwards |
| `500` errors on Vercel | Open **Deployments → Functions → Logs** for the Python traceback |
| Firebase FAQs not appearing | Verify both Firebase variables, the JSON is on one line, and wait up to 5 minutes for the cache |
| Request timeout | Gemini was slow; raise `maxDuration` in `vercel.json` (plan limits apply) |

---

## 🔐 Security Notes

- Never commit your `.env` file or API keys (already in `.gitignore`).
- Anyone can call `/api/chat`, so set a **spending limit** on your Gemini key and enable **Vercel Firewall rate limiting**.
- The bot gives general information only; for medical, legal or financial decisions consult a qualified professional.
- Some built-in answers (dates, procedures, capitals) can change or vary by country — verify against official sources when accuracy matters.

---

## 🧰 Tech Stack

**Backend:** Python, Flask, google-genai, firebase-admin
**Frontend:** HTML, CSS, vanilla JavaScript
**Hosting:** Vercel Serverless Functions
**Database (optional):** Firebase Realtime Database

---

## 📄 License

Free to use and modify for personal and educational projects.
