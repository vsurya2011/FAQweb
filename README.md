# FAQBot (Python + Vercel)

```
faqbot-vercel/
├─ api/index.py        Flask backend: /api/faqs, /api/chat, /api/health
├─ data/faqs.json      149 built-in FAQs (edit freely)
├─ public/index.html   Frontend UI
├─ requirements.txt
├─ vercel.json
└─ .env.example
```

## Run locally
```bash
pip install -r requirements.txt
export GEMINI_API_KEY=your_key      # Windows: set GEMINI_API_KEY=your_key
python api/index.py                 # open http://localhost:3000
```

## Deploy
1. Push this folder to GitHub.
2. Vercel -> Add New Project -> import the repo (Framework: Other).
3. Settings -> Environment Variables: add `GEMINI_API_KEY` (and the optional Firebase ones).
4. Deploy.
