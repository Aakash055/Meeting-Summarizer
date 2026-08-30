# NoteGrain — Meeting Summarizer

A full-stack AI web app that turns a raw meeting or lecture recording into a timestamped transcript, an AI-generated summary, key points, decisions, and action items (with assignee, deadline, and source quote) — automatically.

**🔗 Live demo:** [meeting-summarizer-1-myol.onrender.com](https://meeting-summarizer-1-myol.onrender.com)

> Note: the backend is hosted on Render's free tier, which spins down after 15 minutes of inactivity. The first request after idling can take 30–60 seconds to wake up — this is expected, not a bug.

---

## Features

- 🎙️ Upload an audio/video recording and get a full timestamped transcript
- 🧠 AI-generated summary, key points, decisions, and action items (with assignee + deadline)
- 🔍 Keyword search across all your past transcripts
- 🔐 JWT-based authentication with per-user data isolation
- 📊 Dashboard of all past meetings, with detail view per meeting
- 🗑️ Delete meetings with confirmation

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React (Vite), plain CSS |
| Backend | Python, FastAPI |
| Speech-to-text | OpenAI Whisper model, via `faster-whisper` (int8 quantized inference) |
| Summarization / extraction | Google Gemini API (`gemini-3.6-flash`) |
| Database | PostgreSQL (SQLAlchemy ORM) |
| Auth | JWT (`python-jose`) + `bcrypt` |
| Testing | `pytest` (unit + integration) |
| Deployment | Render.com |

## How it works

1. User uploads a recording → backend validates file type/size
2. `faster-whisper` transcribes it into timestamped segments
3. The transcript is chunked by token count (never splitting a segment mid-way)
4. Each chunk is sent to Gemini with a structured-JSON prompt to extract a summary, key points, decisions, action items, and topics
5. Multi-chunk results are merged (map-reduce) into one coherent meeting-level summary
6. Everything is persisted to PostgreSQL and shown in the dashboard

## Evaluation

Measured against a manually verified ground truth:

| Metric | Result |
|---|---|
| Word Error Rate (transcription) | 28% |
| Action item extraction — Precision | 1.00 |
| Action item extraction — Recall | 0.50 |
| Action item extraction — F1 | 0.667 |

High precision with lower recall means the system is conservative: everything it extracts is correct, but it misses some true action items — largely because errors in transcription (e.g. a mis-heard name or date) cascade into the extraction step downstream.

## Running locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
# create a .env file — see .env.example for required variables
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://127.0.0.1:8000` by default when run locally.

### Required environment variables (`backend/.env`)

See `backend/.env.example` for the full list, including `GEMINI_API_KEY`, `JWT_SECRET_KEY`, and `DATABASE_URL`.

## Known Limitations

- Uses the smallest Whisper model (`tiny`) in production to fit the hosting tier's memory limit — a deliberate trade-off, not an oversight
- No speaker diarization — self-assigned tasks are labeled generically rather than attributed to a guessed name
- Upload processing is synchronous (the request blocks until the full pipeline completes)
- Search is keyword-based (SQL `ILIKE`), not semantic/embedding-based
- JWT is stored in `localStorage`, which carries a known XSS trade-off vs. HTTP-only cookies

## License

This project was built as a final-year B.Tech CSE (AI/ML) academic project.
