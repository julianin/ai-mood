from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .mood import MOODS, classify_mood
from .pollinations import PollinationsClient, PollinationsError

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
DATA_DIR = ROOT / "data" / "sessions"
DATA_DIR.mkdir(parents=True, exist_ok=True)

REFERENCE_MODE = os.getenv("REFERENCE_MODE", "base").lower().strip()
if REFERENCE_MODE not in {"base", "current"}:
    REFERENCE_MODE = "base"

POLLINATIONS_APP_KEY = os.getenv("POLLINATIONS_APP_KEY", "").strip()
POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "").strip()
POLLINATIONS_AUTH_BASE_URL = os.getenv(
    "POLLINATIONS_AUTH_BASE_URL", "https://enter.pollinations.ai"
).rstrip("/")
BYOP_BUDGET = os.getenv("BYOP_BUDGET", "5").strip()
BYOP_EXPIRY_DAYS = os.getenv("BYOP_EXPIRY_DAYS", "7").strip()
BYOP_SCOPE = os.getenv("BYOP_SCOPE", "usage").strip()
BYOP_REDIRECT_PATH = os.getenv("BYOP_REDIRECT_PATH", "/auth/callback").strip() or "/auth/callback"

# Only expose publishable pk_ keys to the frontend. Never leak sk_ keys.
BYOP_CLIENT_ID = POLLINATIONS_APP_KEY if POLLINATIONS_APP_KEY.startswith("pk_") else None
BYOP_ENABLED = BYOP_CLIENT_ID is not None
SERVER_KEY_AVAILABLE = bool(POLLINATIONS_API_KEY)

app = FastAPI(title="AI Mood", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/media", StaticFiles(directory=DATA_DIR), name="media")

# Simple in-memory store for demo. For production: SQLite/Postgres.
SESSIONS: dict[str, dict] = {}


class StartRequest(BaseModel):
    persona: str = Field(
        default="a friendly gender-neutral AI companion, young adult, expressive face",
        max_length=500,
    )
    style: str = Field(
        default="cinematic 3D portrait, soft studio lighting, clean pastel background, polished app avatar",
        max_length=500,
    )


class StartResponse(BaseModel):
    session_id: str
    image_url: str
    reference_mode: str
    identity_prompt: str
    auth_mode: Literal["byop", "server"]


class MessageRequest(BaseModel):
    session_id: str
    text: str = Field(min_length=1, max_length=2000)
    force_mood: str | None = None


class MessageResponse(BaseModel):
    session_id: str
    mood: str
    mood_label: str
    emoji: str
    image_url: str
    edited_from: Literal["base", "current", "fallback_generation"]
    prompt_used: str
    auth_mode: Literal["byop", "server"]


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/auth/callback")
async def auth_callback() -> FileResponse:
    # Pollinations returns the scoped user key in the URL fragment:
    # /auth/callback#api_key=sk_...&state=...
    # The fragment is handled in the browser and never reaches this endpoint.
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict:
    return {
        "ok": True,
        "reference_mode": REFERENCE_MODE,
        "byop_enabled": BYOP_ENABLED,
        "server_key_available": SERVER_KEY_AVAILABLE,
    }


@app.get("/api/config")
async def config() -> dict:
    generate_model = os.getenv("POLLINATIONS_GENERATE_MODEL", "flux")
    edit_model = os.getenv("POLLINATIONS_EDIT_MODEL", "gptimage")
    models = sorted({generate_model, edit_model})
    return {
        "app_name": "AI Mood",
        "byop_enabled": BYOP_ENABLED,
        "client_id": BYOP_CLIENT_ID,
        "auth_base_url": POLLINATIONS_AUTH_BASE_URL,
        "redirect_path": BYOP_REDIRECT_PATH,
        "scope": BYOP_SCOPE,
        "models": models,
        "budget": BYOP_BUDGET,
        "expiry_days": BYOP_EXPIRY_DAYS,
        "server_key_available": SERVER_KEY_AVAILABLE,
        "reference_mode": REFERENCE_MODE,
        "image_size": os.getenv("IMAGE_SIZE", "768x768"),
        "mood_model": os.getenv("POLLINATIONS_MOOD_MODEL", "openai"),
    }


@app.get("/api/key-info")
async def key_info(authorization: str | None = Header(default=None)) -> dict:
    try:
        client, auth_mode = make_client(authorization)
        return {"auth_mode": auth_mode, "key": await client.key_info()}
    except PollinationsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/account")
async def account(authorization: str | None = Header(default=None)) -> dict:
    try:
        client, auth_mode = make_client(authorization)
        profile = await client.profile()
        balance = await client.balance()
        return {"auth_mode": auth_mode, "profile": profile, "balance": balance}
    except PollinationsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/start", response_model=StartResponse)
async def start(req: StartRequest, authorization: str | None = Header(default=None)) -> StartResponse:
    session_id = uuid.uuid4().hex[:12]
    folder = DATA_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)

    identity_prompt = build_identity_prompt(req.persona, req.style)
    base_path = folder / "base.png"

    try:
        client, auth_mode = make_client(authorization)
        image_bytes = await client.generate_avatar(identity_prompt)
        base_path.write_bytes(image_bytes)
    except PollinationsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    SESSIONS[session_id] = {
        "identity_prompt": identity_prompt,
        "persona": req.persona,
        "style": req.style,
        "base_path": str(base_path),
        "current_path": str(base_path),
        "turn": 0,
        "messages": [],
    }

    return StartResponse(
        session_id=session_id,
        image_url=media_url(base_path),
        reference_mode=REFERENCE_MODE,
        identity_prompt=identity_prompt,
        auth_mode=auth_mode,
    )


_ALLOWED_IMAGE_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/jpg", "image/webp"}
)
_EXT_MAP: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/webp": "webp",
}
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


@app.post("/api/upload", response_model=StartResponse)
async def upload_avatar(
    file: UploadFile = File(...),
    persona: str = Form(default="uploaded avatar, expressive face"),
    style: str = Form(default="portrait, cinematic lighting, clean background, high quality"),
    authorization: str | None = Header(default=None),
) -> StartResponse:
    ct = (file.content_type or "").lower().split(";")[0].strip()
    if ct not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ct}'. Upload a PNG, JPEG, or WebP image.",
        )

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 10 MB.")

    # Basic magic-byte validation
    is_png = contents[:4] == b"\x89PNG"
    is_jpeg = contents[:2] == b"\xff\xd8"
    is_webp = contents[:4] == b"RIFF" and contents[8:12] == b"WEBP"
    if not (is_png or is_jpeg or is_webp):
        raise HTTPException(status_code=415, detail="File content does not match a supported image format.")

    session_id = uuid.uuid4().hex[:12]
    folder = DATA_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)

    ext = _EXT_MAP.get(ct, "png")
    base_path = folder / f"base.{ext}"
    base_path.write_bytes(contents)

    identity_prompt = build_identity_prompt(persona.strip() or "uploaded avatar", style.strip() or "portrait")
    SESSIONS[session_id] = {
        "identity_prompt": identity_prompt,
        "persona": persona,
        "style": style,
        "base_path": str(base_path),
        "current_path": str(base_path),
        "turn": 0,
        "messages": [],
    }

    user_key = key_from_authorization_header(authorization)
    auth_mode: Literal["byop", "server"] = "byop" if user_key else "server"

    return StartResponse(
        session_id=session_id,
        image_url=media_url(base_path),
        reference_mode=REFERENCE_MODE,
        identity_prompt=identity_prompt,
        auth_mode=auth_mode,
    )


@app.post("/api/message", response_model=MessageResponse)
async def message(req: MessageRequest, authorization: str | None = Header(default=None)) -> MessageResponse:
    session = SESSIONS.get(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown session_id. Start a new session first.")

    # Determine mood and expression description
    if req.force_mood and MOODS.get(req.force_mood):
        mood = MOODS[req.force_mood]
        expression_description = mood.expression_prompt
    else:
        # Use LLM to get a rich expression description from the user's message
        try:
            client_for_mood, _ = make_client(authorization)
            llm_result = await client_for_mood.describe_expression(req.text)
            mood = MOODS.get(llm_result.get("mood"), MOODS["neutral"])
            expression_description = llm_result.get("expression", mood.expression_prompt)
        except (HTTPException, PollinationsError):
            mood = classify_mood(req.text)
            expression_description = mood.expression_prompt

    session["turn"] += 1
    session["messages"].append({"role": "user", "content": req.text, "mood": mood.name})

    if REFERENCE_MODE == "current":
        source_path = Path(session["current_path"])
        edited_from: Literal["base", "current", "fallback_generation"] = "current"
    else:
        source_path = Path(session["base_path"])
        edited_from = "base"

    edit_prompt = build_edit_prompt(session["identity_prompt"], expression_description)
    out_path = DATA_DIR / req.session_id / f"turn_{session['turn']:03d}_{mood.name}.png"

    try:
        client, auth_mode = make_client(authorization)
        try:
            image_bytes = await client.edit_avatar(source_path, edit_prompt)
        except PollinationsError as edit_err:
            import logging
            logging.getLogger("ai-mood").warning("Image edit failed, using fallback generation: %s", edit_err)
            fallback_prompt = build_fallback_generation_prompt(session["identity_prompt"], expression_description)
            image_bytes = await client.fallback_variation(fallback_prompt)
            edited_from = "fallback_generation"
            edit_prompt = fallback_prompt
        out_path.write_bytes(image_bytes)
    except PollinationsError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    session["current_path"] = str(out_path)

    return MessageResponse(
        session_id=req.session_id,
        mood=mood.name,
        mood_label=mood.label,
        emoji=mood.emoji,
        image_url=media_url(out_path),
        edited_from=edited_from,
        prompt_used=edit_prompt,
        auth_mode=auth_mode,
    )


@app.get("/api/moods")
async def moods() -> list[dict]:
    return [
        {"name": mood.name, "label": mood.label, "emoji": mood.emoji}
        for mood in MOODS.values()
    ]


def make_client(authorization: str | None) -> tuple[PollinationsClient, Literal["byop", "server"]]:
    user_key = key_from_authorization_header(authorization)
    if user_key:
        return PollinationsClient(api_key=user_key), "byop"
    if not POLLINATIONS_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="No API key available. Connect with Bring Your Own Pollen, or ask the app owner to set POLLINATIONS_API_KEY.",
        )
    return PollinationsClient(api_key=POLLINATIONS_API_KEY), "server"


def key_from_authorization_header(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    token = token.strip()
    # BYOP returns a scoped sk_ user key. Users can also paste pk_ or sk_ keys manually.
    if not token.startswith(("sk_", "pk_")):
        return None
    return token


def build_identity_prompt(persona: str, style: str) -> str:
    return f"""
Create the base avatar for an app called AI Mood.
Subject: {persona}.
Style: {style}.
Requirements:
- Single centered face portrait, shoulders visible.
- Neutral attentive expression.
- Same identity must be reusable for future edits.
- Distinctive but simple features: consistent hairstyle, eye shape, face shape, clothing, and color palette.
- No text, no logo, no watermark.
- Clean composition, app-ready avatar, high quality.
""".strip()


def build_edit_prompt(identity_prompt: str, expression_prompt: str) -> str:
    return f"""
Edit the provided source image.
Keep the exact same person/avatar identity from the source image.
Preserve face shape, hair, eyes, clothing, camera angle, framing, background, lighting, color palette, and overall art style.
Only change the facial expression and emotional micro-expression.
New expression: {expression_prompt}.
Do not change age, gender presentation, outfit, hairstyle, background, or art style.
Do not add text, logos, props, extra people, or watermark.
Make it look like the same avatar reacting naturally in the app.
Identity anchor: {identity_prompt}
""".strip()


def build_fallback_generation_prompt(identity_prompt: str, expression_prompt: str) -> str:
    return f"""
{identity_prompt}
Now render the same avatar identity with this expression: {expression_prompt}.
Keep the same face, hair, clothing, framing, background, lighting and visual style.
No text, no logo, no watermark.
""".strip()


def media_url(path: Path) -> str:
    # Path is inside data/sessions. Return a cache-busted local URL.
    rel = path.relative_to(DATA_DIR).as_posix()
    return f"/media/{rel}?v={uuid.uuid4().hex[:8]}"
