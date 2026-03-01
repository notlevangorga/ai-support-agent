import os
import time
import hmac
import hashlib
import requests
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from rag_engine import (
    ingest_into_vector_db,
    retrieve_context,
    generate_answer
)

# -----------------------------
# Initialize FastAPI
# -----------------------------
app = FastAPI()

# Load vector DB once on startup
@app.on_event("startup")
def startup_event():
    ingest_into_vector_db()

CONFIDENCE_THRESHOLD = 0.2

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")


# -----------------------------
# Health Check Route
# -----------------------------
@app.get("/")
def health():
    return {"status": "running"}


# -----------------------------
# Slack Signature Verification
# -----------------------------
def verify_slack_request(request: Request, body: bytes):
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    slack_signature = request.headers.get("X-Slack-Signature")

    if not timestamp or not slack_signature:
        raise HTTPException(status_code=400, detail="Missing Slack headers")

    # Prevent replay attacks (5 min window)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        raise HTTPException(status_code=400, detail="Request too old")

    basestring = f"v0:{timestamp}:{body.decode()}"

    computed_signature = (
        "v0=" +
        hmac.new(
            SLACK_SIGNING_SECRET.encode(),
            basestring.encode(),
            hashlib.sha256
        ).hexdigest()
    )

    if not hmac.compare_digest(computed_signature, slack_signature):
        raise HTTPException(status_code=403, detail="Invalid Slack signature")


# -----------------------------
# Background Slack Processing
# -----------------------------
def process_slack_event(event):
    user_text = event.get("text", "")

    retrieved, distances = retrieve_context(user_text)
    best_distance = distances[0]
    confidence = 1 - best_distance

    if confidence < CONFIDENCE_THRESHOLD:
        answer = "I'm not confident enough to answer that."
    else:
        answer = generate_answer(user_text, retrieved)

    requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "channel": event["channel"],
            "text": answer
        }
    )


# -----------------------------
# Slack Events Endpoint
# -----------------------------
@app.post("/slack/events")
async def slack_events(request: Request, background_tasks: BackgroundTasks):
    body = await request.body()

    verify_slack_request(request, body)

    data = await request.json()

    # Slack URL verification
    if data.get("type") == "url_verification":
        return JSONResponse(content={"challenge": data["challenge"]})

    if "event" in data:
        event = data["event"]

        if event.get("type") == "app_mention":
            # Immediately acknowledge Slack
            background_tasks.add_task(process_slack_event, event)

    return JSONResponse(content={"status": "ok"})