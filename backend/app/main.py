import os
import json
import whisper
from dotenv import load_dotenv
from google import genai
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, joinedload

from app.database import engine, Base, get_db
from app.models import Meeting, TranscriptSegment, Summary, Topic, Decision, ActionItem, KeyPoint, User
from app.schemas import UserRegister, UserLogin, TokenResponse
from app.auth import hash_password, verify_password, create_access_token, decode_access_token
from app.utils import estimate_tokens, chunk_segments, merge_action_items, deduplicate_topics

load_dotenv()

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173","https://meeting-summarizer-1-myol.onrender.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/x-m4a"
    "video/mp4",
    "video/quicktime",
}

MAX_FILE_SIZE_MB = 200
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

print("Loading Whisper model... (this happens once at startup)")
whisper_model = whisper.load_model("tiny")
print("Whisper model loaded.")

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

SUMMARY_PROMPT_TEMPLATE = """You are analyzing a transcript segment from a meeting or lecture.

Read the transcript below and extract the following information. Respond ONLY with valid JSON, no other text, no markdown code fences.

{{
  "summary": "A 2-3 sentence summary of what was discussed in this segment",
  "key_points": ["list", "of", "key discussion points as short strings"],
  "decisions": ["list of any decisions that were made, as short strings"],
  "action_items": [
    {{
      "task": "description of the task",
      "assignee": "person's name if mentioned, otherwise 'Not specified'",
      "deadline": "deadline if mentioned, otherwise 'Not specified'",
      "source": "the exact sentence from the transcript this was extracted from"
    }}
  ],
  "topics": ["list", "of", "topic names mentioned"]
}}

Important rules:
- If no action items are mentioned, return an empty list for "action_items".
- Never invent an assignee or deadline that isn't explicitly stated in the transcript.
- If the speaker assigns a task to themselves (e.g. "I'll do it", "I will handle that", "I'm going to..."), set "assignee" to "Speaker (self-assigned)".
- If multiple people are assigned to one task, list all their names together in "assignee" (e.g. "Mark and Priya").
- Only extract genuine tasks or commitments as action items. Do not extract complaints, observations, or general statements that don't involve someone doing something (e.g. "the wifi has been down" is not an action item).
- Vague future intentions without a real commitment (e.g. "we should think about X at some point, no rush") may be omitted from action_items if there's no clear task or owner - use judgment.
- Keep "summary" concise, 2-3 sentences maximum.

Transcript:
{transcript_text}
"""

FINAL_SUMMARY_PROMPT_TEMPLATE = """You are combining several partial summaries from different segments of the same meeting/lecture into one coherent overall summary.

Here are the segment summaries, in order:

{combined_summaries}

Write ONE cohesive summary (3-5 sentences) of the entire meeting/lecture based on all the segments above. Respond with ONLY the summary text, no JSON, no extra formatting.
"""


def summarize_chunk(transcript_text: str) -> dict:
    prompt = SUMMARY_PROMPT_TEMPLATE.format(transcript_text=transcript_text)

    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt
    )

    raw_text = response.text.strip()

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        raw_text = raw_text.replace("json", "", 1).strip()

    return json.loads(raw_text)


def merge_chunk_results(chunk_results: list) -> dict:
    if len(chunk_results) == 1:
        return chunk_results[0]

    all_key_points = []
    all_decisions = []

    for result in chunk_results:
        all_key_points.extend(result.get("key_points", []))
        all_decisions.extend(result.get("decisions", []))

    all_action_items = merge_action_items(chunk_results)

    all_topics = []
    for result in chunk_results:
        all_topics.extend(result.get("topics", []))
    unique_topics = deduplicate_topics(all_topics)

    summaries_text = "\n".join(
        f"Segment {i + 1}: {result['summary']}"
        for i, result in enumerate(chunk_results)
    )
    final_summary_prompt = FINAL_SUMMARY_PROMPT_TEMPLATE.format(combined_summaries=summaries_text)

    response = gemini_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=final_summary_prompt
    )

    return {
        "summary": response.text.strip(),
        "key_points": all_key_points,
        "decisions": all_decisions,
        "action_items": all_action_items,
        "topics": unique_topics
    }


def get_current_user(authorization: str = Header(None), db: Session = Depends(get_db)) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.replace("Bearer ", "")
    user_id = decode_access_token(token)

    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


@app.get("/")
def read_root():
    return {"message": "Meeting Summarizer API is running"}


@app.post("/register", response_model=TokenResponse)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(email=user_data.email, hashed_password=hash_password(user_data.password))
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(new_user.id)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(user.id)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Please upload an audio or video file."
        )

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB}MB."
        )

    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        buffer.write(content)

    meeting = Meeting(filename=file.filename, status="processing", user_id=current_user.id)
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    result = whisper_model.transcribe(file_path)

    segments = [
        {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"].strip()
        }
        for segment in result["segments"]
    ]

    for seg in segments:
        db_segment = TranscriptSegment(
            meeting_id=meeting.id,
            start_time=seg["start"],
            end_time=seg["end"],
            text=seg["text"]
        )
        db.add(db_segment)

    chunks = chunk_segments(segments, max_tokens_per_chunk=1500)

    chunk_results = []
    for chunk in chunks:
        combined_text = " ".join(s["text"] for s in chunk)
        summary_data = summarize_chunk(combined_text)
        chunk_results.append(summary_data)

    final_result = merge_chunk_results(chunk_results)

    db_summary = Summary(meeting_id=meeting.id, summary_text=final_result["summary"])
    db.add(db_summary)

    for topic_name in final_result["topics"]:
        db.add(Topic(meeting_id=meeting.id, name=topic_name))

    for decision_text in final_result["decisions"]:
        db.add(Decision(meeting_id=meeting.id, text=decision_text))

    for point_text in final_result["key_points"]:
        db.add(KeyPoint(meeting_id=meeting.id, text=point_text))

    for item in final_result["action_items"]:
        db.add(ActionItem(
            meeting_id=meeting.id,
            task=item.get("task", ""),
            assignee=item.get("assignee", "Not specified"),
            deadline=item.get("deadline", "Not specified"),
            source=item.get("source", "")
        ))

    meeting.status = "done"
    db.commit()

    return {
        "meeting_id": meeting.id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "transcript_text": result["text"],
        "segments": segments,
        "summary": final_result["summary"],
        "key_points": final_result["key_points"],
        "decisions": final_result["decisions"],
        "action_items": final_result["action_items"],
        "topics": final_result["topics"]
    }


@app.get("/meetings")
def list_meetings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    meetings = (
        db.query(Meeting)
        .options(joinedload(Meeting.summary))
        .filter(Meeting.user_id == current_user.id)
        .order_by(Meeting.created_at.desc())
        .all()
    )

    return [
        {
            "id": m.id,
            "filename": m.filename,
            "status": m.status,
            "created_at": m.created_at.isoformat(),
            "summary": m.summary.summary_text if m.summary else None
        }
        for m in meetings
    ]


@app.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    meeting = (
        db.query(Meeting)
        .options(
            joinedload(Meeting.summary),
            joinedload(Meeting.segments),
            joinedload(Meeting.topics),
            joinedload(Meeting.decisions),
            joinedload(Meeting.action_items),
            joinedload(Meeting.key_points),
        )
        .filter(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
        .first()
    )

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "id": meeting.id,
        "filename": meeting.filename,
        "status": meeting.status,
        "created_at": meeting.created_at.isoformat(),
        "summary": meeting.summary.summary_text if meeting.summary else None,
        "segments": [
            {"start": s.start_time, "end": s.end_time, "text": s.text}
            for s in sorted(meeting.segments, key=lambda s: s.start_time)
        ],
        "topics": [t.name for t in meeting.topics],
        "decisions": [d.text for d in meeting.decisions],
        "key_points": [k.text for k in meeting.key_points],
        "action_items": [
            {
                "task": a.task,
                "assignee": a.assignee,
                "deadline": a.deadline,
                "source": a.source
            }
            for a in meeting.action_items
        ]
    }


@app.delete("/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id, Meeting.user_id == current_user.id)
        .first()
    )

    if meeting is None:
        raise HTTPException(status_code=404, detail="Meeting not found")

    file_path = os.path.join(UPLOAD_DIR, meeting.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.delete(meeting)
    db.commit()

    return {"message": "Meeting deleted successfully"}


@app.get("/search")
def search_transcripts(q: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not q or len(q.strip()) == 0:
        return []

    search_term = f"%{q.strip()}%"

    matching_segments = (
        db.query(TranscriptSegment)
        .join(Meeting)
        .filter(Meeting.user_id == current_user.id, TranscriptSegment.text.ilike(search_term))
        .order_by(Meeting.created_at.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "meeting_id": seg.meeting_id,
            "meeting_filename": seg.meeting.filename,
            "start_time": seg.start_time,
            "text": seg.text
        }
        for seg in matching_segments
    ]