import os
import whisper
from fastapi import FastAPI, UploadFile, File, HTTPException

app = FastAPI()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_CONTENT_TYPES = {
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "video/mp4",
    "video/quicktime",
}

MAX_FILE_SIZE_MB = 200
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

print("Loading Whisper model... (this happens once at startup)")
whisper_model = whisper.load_model("base")
print("Whisper model loaded.")


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def chunk_segments(segments, max_tokens_per_chunk=1500):
    chunks = []
    current_chunk_segments = []
    current_chunk_tokens = 0

    for segment in segments:
        segment_tokens = estimate_tokens(segment["text"])

        if current_chunk_tokens + segment_tokens > max_tokens_per_chunk and current_chunk_segments:
            chunks.append(current_chunk_segments)
            current_chunk_segments = []
            current_chunk_tokens = 0

        current_chunk_segments.append(segment)
        current_chunk_tokens += segment_tokens

    if current_chunk_segments:
        chunks.append(current_chunk_segments)

    return chunks


@app.get("/")
def read_root():
    return {"message": "Meeting Summarizer API is running"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
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

    result = whisper_model.transcribe(file_path)

    segments = [
        {
            "start": segment["start"],
            "end": segment["end"],
            "text": segment["text"].strip()
        }
        for segment in result["segments"]
    ]

    chunks = chunk_segments(segments, max_tokens_per_chunk=1500)

    chunk_summaries_preview = [
        {
            "chunk_number": i + 1,
            "segment_count": len(chunk),
            "estimated_tokens": sum(estimate_tokens(s["text"]) for s in chunk),
            "combined_text": " ".join(s["text"] for s in chunk)
        }
        for i, chunk in enumerate(chunks)
    ]

    return {
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "transcript_text": result["text"],
        "segments": segments,
        "chunks_preview": chunk_summaries_preview
    }