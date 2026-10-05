"""FAQBot backend — Flask on Vercel.

NLP pipeline: clean -> tokenize -> stop-words -> stem -> TF-IDF -> cosine similarity.
Low-confidence questions are answered by Gemini. Firebase is optional (extra FAQs + chat logs).
"""
import json
import math
import os
import re
import time
from collections import Counter
from pathlib import Path

from flask import Flask, jsonify, request

app = Flask(__name__)
ROOT = Path(__file__).resolve().parent.parent

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FAQ_THRESHOLD = 0.55     # confident FAQ match -> answer directly
WEAK_THRESHOLD = 0.30    # used only when AI is unavailable
CACHE_TTL = 300          # seconds to cache FAQs

SYSTEM = (
    "You are FAQBot, a friendly general-purpose assistant that answers questions across ALL domains "
    "(technology, science, math, health, finance, career, travel, education, daily life, etc.). "
    "Be accurate, concise and easy to understand. Never invent private or institution-specific facts "
    "(policies, dates, fees, contacts); say when you don't know. For medical, legal or financial topics "
    "give general information and suggest consulting a professional."
)

STOP = set("""a an and are as at be been being but by can could did do does doing for from had has have
having he her here hers him his how i if in into is it its just me more most my no nor not of on once only
or our ours out over own same she should so some such than that the their theirs them then there these they
this those through to too under until up very was we were what when where which while who whom why will with
would you your yours""".split())


# ---------------- NLP ----------------
def stem(w: str) -> str:
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    elif len(w) > 4 and w.endswith("ed"):
        w = w[:-2]
    elif len(w) > 4 and re.search(r"(ch|sh|x|z|ss)es$", w):
        return w[:-2]
    elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    if len(w) > 3 and w[-1] == w[-2] and w[-1] not in "lsz":   # resetting -> reset
        w = w[:-1]
    return w


def preprocess(text: str) -> list:
    words = re.sub(r"[^a-z0-9\s]", " ", str(text).lower()).split()
    return [stem(w) for w in words if w not in STOP]


def cosine(a: dict, b: dict) -> float:
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class Index:
    def __init__(self, faqs: list):
        self.faqs = faqs
        toks = [preprocess(f["question"]) for f in faqs]
        n = len(toks) or 1
        df = Counter(t for ts in toks for t in set(ts))
        self.idf = {t: math.log((n + 1) / (c + 1)) + 1 for t, c in df.items()}
        self.vecs = [self._vec(ts) for ts in toks]
        self.sets = [set(ts) for ts in toks]

    def _vec(self, toks: list) -> dict:
        tf, d = Counter(toks), (len(toks) or 1)
        return {t: (c / d) * self.idf[t] for t, c in tf.items() if t in self.idf}

    def rank(self, query: str, limit: int = 3) -> list:
        qt = preprocess(query)
        qv = self._vec(qt)
        if not qv:                      # no known words -> no fake match
            return []
        qs = set(qt)
        scored = []
        for f, v, s in zip(self.faqs, self.vecs, self.sets):
            score = min(cosine(qv, v) + 0.12 * len(qs & s) / len(qs), 1.0)
            scored.append((f, score))
        scored.sort(key=lambda x: -x[1])
        return scored[:limit]


# ---------------- Firebase (optional) ----------------
_fb = None


def get_db():
    """Realtime Database via firebase-admin, only if env vars are set."""
    global _fb
    if _fb is not None:
        return _fb or None
    sa, url = os.getenv("FIREBASE_SERVICE_ACCOUNT"), os.getenv("FIREBASE_DATABASE_URL")
    if not (sa and url):
        _fb = False
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, db
        firebase_admin.initialize_app(credentials.Certificate(json.loads(sa)), {"databaseURL": url})
        _fb = db
    except Exception as e:
        print("Firebase init failed:", e)
        _fb = False
    return _fb or None


_cache = {"t": 0.0, "idx": None}


def get_index() -> Index:
    if _cache["idx"] and time.time() - _cache["t"] < CACHE_TTL:
        return _cache["idx"]
    faqs = json.loads((ROOT / "data" / "faqs.json").read_text(encoding="utf-8"))
    fb = get_db()
    if fb:
        try:
            data = fb.reference("faqs").get() or {}
            remote = [{"id": k, **v} for k, v in data.items()
                      if isinstance(v, dict) and v.get("question") and v.get("answer")]
            faqs = remote + faqs
        except Exception as e:
            print("Firebase FAQ read failed:", e)
    seen, merged = set(), []
    for f in faqs:                       # merge cloud + built-in, no duplicates
        k = str(f["question"]).strip().lower()
        if k not in seen:
            seen.add(k)
            merged.append({"id": f.get("id", k), "category": f.get("category", "General"),
                           "question": f["question"], "answer": f["answer"]})
    _cache.update(t=time.time(), idx=Index(merged))
    return _cache["idx"]


def log_chat(sid: str, q: str, res: dict):
    fb = get_db()
    if not fb:
        return
    try:
        fb.reference(f"chat_logs/{sid}").push({
            "question": q, "answer": res["answer"], "score": res["score"],
            "matchedFaqId": (res.get("faq") or {}).get("id"), "mode": res["mode"],
            "createdAt": int(time.time() * 1000)})
    except Exception as e:
        print("Chat log failed:", e)


# ---------------- Gemini ----------------
def ask_gemini(q: str, top: list, history: list):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        from google.genai import types
        ctx = "\n\n".join(f"FAQ {i+1}: {f['question']}\nAnswer: {f['answer']}"
                          for i, (f, s) in enumerate(top) if s > 0.15) or "No related FAQ found."
        prompt = (f"User question: {q}\n\nRelated FAQ context (use only if relevant):\n{ctx}\n\n"
                  "Answer clearly and accurately. Cover any domain. Keep it concise and use short lists "
                  "when helpful. For private or institution-specific facts not in the context, say you "
                  "don't have that information instead of guessing.")
        contents = [types.Content(role=h["role"], parts=[types.Part(text=h["text"])]) for h in history]
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        client = genai.Client(api_key=key)
        resp = client.models.generate_content(
            model=MODEL, contents=contents,
            config=types.GenerateContentConfig(system_instruction=SYSTEM, temperature=0.6,
                                               max_output_tokens=900))
        return (resp.text or "").strip() or None
    except Exception as e:
        print("Gemini error:", e)
        return None


def clean_history(raw) -> list:
    out = []
    for h in (raw if isinstance(raw, list) else [])[-6:]:
        if isinstance(h, dict) and h.get("role") in ("user", "model") and isinstance(h.get("text"), str):
            out.append({"role": h["role"], "text": h["text"][:2000]})
    return out


def brief(f):
    return {"id": f["id"], "question": f["question"], "category": f["category"]}


# ---------------- Routes ----------------
@app.get("/api/health")
def health():
    return jsonify(ok=True)


@app.get("/api/faqs")
def faqs():
    idx = get_index()
    return jsonify(count=len(idx.faqs), faqs=[brief(f) for f in idx.faqs],
                   ai=bool(os.getenv("GEMINI_API_KEY")), firebase=bool(get_db()))


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    q = str(body.get("message", "")).strip()[:500]
    if not q:
        return jsonify(error="Please type a question"), 400
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(body.get("sid", "anon")))[:40] or "anon"

    top = get_index().rank(q, 3)
    best, score = top[0] if top else (None, 0.0)

    if best and score >= FAQ_THRESHOLD:
        res = {"answer": best["answer"], "score": score, "mode": "faq", "faq": brief(best)}
    else:
        text = ask_gemini(q, top, clean_history(body.get("history")))
        if text:
            res = {"answer": text, "score": score, "mode": "ai", "faq": None}
        elif best and score >= WEAK_THRESHOLD:
            res = {"answer": best["answer"], "score": score, "mode": "faq", "faq": brief(best)}
        else:
            res = {"answer": "I couldn't find a confident answer to that. Did you mean one of these?",
                   "score": score, "mode": "faq", "faq": None,
                   "suggestions": [brief(f) for f, _ in top]}
    log_chat(sid, q, res)
    return jsonify(res)


@app.get("/")
def local_index():            # only used for local dev; Vercel serves /public itself
    return (ROOT / "public" / "index.html").read_text(encoding="utf-8")


if __name__ == "__main__":
    app.run(debug=True, port=3000)
