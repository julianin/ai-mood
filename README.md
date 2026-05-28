# AI Mood FastAPI + BYOP

[![Built With pollinations.ai](https://img.shields.io/badge/Built%20with-Pollinations-8a2be2?labelColor=6a0dad&style=for-the-badge)](https://pollinations.ai)

<a href="https://pollinations.ai"><img src="https://raw.githubusercontent.com/pollinations/pollinations/main/assets/logo-text-white.svg" alt="pollinations.ai Logo Text White" height="32" /></a>


A simple but powerful mini app powered by [pollinations.ai](https://pollinations.ai): it generates **one base avatar**, then each new message edits that same image to change the facial expression without losing the character identity.

This version includes **Bring Your Own Pollen (BYOP)**:

- The user connects their Pollinations account.
- Pollinations returns a temporary scoped user key in `#api_key=...`.
- The browser stores that key in `localStorage`.
- FastAPI receives it through `Authorization: Bearer ...` and calls Pollinations using the user's balance.
- Your `POLLINATIONS_API_KEY=sk_...` is only an optional development/demo fallback.

## Architecture

```txt
Browser
  ├── Connect Pollinations -> enter.pollinations.ai/authorize
  ├── callback /auth/callback#api_key=sk_...
  ├── POST /api/start     Authorization: Bearer user_sk
  └── POST /api/message   Authorization: Bearer user_sk

FastAPI
  ├── /api/config      exposes only pk_ and BYOP settings
  ├── /api/start       creates the base avatar
  ├── /api/message     edits the expression using the base/current image
  ├── /api/key-info    validates the current key
  ├── /api/account     debug endpoint for profile/balance if the key has permission
  ├── /auth/callback   serves the same UI; the browser reads the URL fragment
  └── /media/...       serves generated images
```

## How image consistency works

1. `/api/start` creates the first image with `/v1/images/generations`.
2. It saves the image at `data/sessions/{session_id}/base.png`.
3. `/api/message` detects the mood locally.
4. FastAPI sends the base/current image to `/v1/images/edits` with a strict prompt:
   - same face
   - same hair
   - same outfit
   - same angle
   - only the facial expression changes

By default, `REFERENCE_MODE=base`, so every expression is edited from the first image. This avoids identity drift.

If you set `REFERENCE_MODE=current`, each turn edits the latest image. It feels more progressive, but the identity can slowly drift over time.

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```bash
# Optional server-side fallback. Never expose this in the frontend.
POLLINATIONS_API_KEY=sk_your_dev_or_fallback_key_here

# Public BYOP App Key.
POLLINATIONS_APP_KEY=pk_your_publishable_app_key_here

POLLINATIONS_GENERATE_MODEL=flux
POLLINATIONS_EDIT_MODEL=gptimage
IMAGE_SIZE=768x768
REFERENCE_MODE=base
```

Run:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open:

```txt
http://127.0.0.1:8000
```

## Create the BYOP App Key

Go to `enter.pollinations.ai` and create a **New App Key / publishable key**.

Configure:

```txt
Name: AI Mood
Local redirect URI: http://127.0.0.1:8000/auth/callback
Production redirect URI: https://YOUR-DOMAIN/auth/callback
```

Copy the `pk_...` key into:

```bash
POLLINATIONS_APP_KEY=pk_...
```

The `pk_` key is public. The `sk_` key is secret.

## BYOP flow in this app

The **Connect Pollinations** button builds a URL like this:

```txt
https://enter.pollinations.ai/authorize?redirect_uri=http://127.0.0.1:8000/auth/callback&client_id=pk_...&scope=usage&models=flux,gptimage&budget=5&expiry=7&state=random
```

Pollinations redirects the user back to:

```txt
http://127.0.0.1:8000/auth/callback#api_key=sk_...&state=random
```

Important: `api_key` comes in the URL **fragment** (`#`), not as a query parameter. That means it does not reach the server as part of the URL and does not normally appear in HTTP logs. The browser captures it and sends it to FastAPI only in generation requests.

## BYOP variables

```bash
POLLINATIONS_APP_KEY=pk_...
BYOP_REDIRECT_PATH=/auth/callback
BYOP_SCOPE=usage
BYOP_BUDGET=5
BYOP_EXPIRY_DAYS=7
```

- `BYOP_BUDGET=5`: the user authorizes up to 5 pollen for this temporary key, unless they change it on the consent screen.
- `BYOP_EXPIRY_DAYS=7`: the temporary key expires in 7 days.
- `models=flux,gptimage`: calculated from `POLLINATIONS_GENERATE_MODEL` and `POLLINATIONS_EDIT_MODEL`.

## API

### Start avatar

```bash
curl -X POST http://127.0.0.1:8000/api/start \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk_user_key_from_byop' \
  -d '{
    "persona": "a friendly AI companion with short dark hair",
    "style": "cinematic 3D portrait, soft studio lighting"
  }'
```

### Edit expression from message

```bash
curl -X POST http://127.0.0.1:8000/api/message \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk_user_key_from_byop' \
  -d '{
    "session_id": "PASTE_SESSION_ID",
    "text": "I am nervous about tomorrow's demo"
  }'
```

### Force a mood

```bash
curl -X POST http://127.0.0.1:8000/api/message \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer sk_user_key_from_byop' \
  -d '{
    "session_id": "PASTE_SESSION_ID",
    "text": "demo",
    "force_mood": "excited"
  }'
```

Allowed moods:

- happy
- sad
- angry
- anxious
- surprised
- calm
- confused
- tired
- excited
- neutral

## Deploy

### Render / Railway / Fly

Use:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Add environment variables:

```bash
POLLINATIONS_APP_KEY=pk_your_publishable_app_key_here
POLLINATIONS_API_KEY=sk_optional_fallback_key_here
POLLINATIONS_GENERATE_MODEL=flux
POLLINATIONS_EDIT_MODEL=gptimage
IMAGE_SIZE=768x768
REFERENCE_MODE=base
```

Then register the deployed callback URL in your Pollinations App Key:

```txt
https://your-app.onrender.com/auth/callback
```

### Docker

```bash
docker build -t ai-mood-fastapi .
docker run --env-file .env -p 8000:8000 ai-mood-fastapi
```


## Pollinations attribution

AI Mood uses the [pollinations.ai](https://pollinations.ai) API and includes visible credit in the frontend and this README.

Official assets referenced from the Pollinations repository / submission template:

- [pollinations.ai Logo White](https://raw.githubusercontent.com/pollinations/pollinations/main/assets/logo.svg)
- [pollinations.ai Logo Text White](https://raw.githubusercontent.com/pollinations/pollinations/main/assets/logo-text-white.svg)
- [Built With pollinations.ai badge](https://img.shields.io/badge/Built%20with-Pollinations-8a2be2?labelColor=6a0dad&style=for-the-badge)

Links included in the app:

- [pollinations.ai](https://pollinations.ai)
- [enter.pollinations.ai](https://enter.pollinations.ai)
- [pollinations/pollinations on GitHub](https://github.com/pollinations/pollinations)

## Production improvements

1. Replace in-memory sessions with SQLite/Postgres.
2. Encrypt or avoid storing user BYOP keys server-side. This demo does not persist them.
3. Add session cleanup for `data/sessions`.
4. Add a privacy page.
5. Add rate limiting per IP/session.
6. Add a gallery/timeline of expressions.
7. Add app analytics based on `/account/key/usage` or developer earnings endpoints.
