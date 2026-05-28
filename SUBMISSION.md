# Pollinations App Submission Draft

## App Name
AI Mood

## App Description
AI Mood is a tiny emotional avatar demo powered by pollinations.ai. A user creates one base AI avatar, then each message in the conversation changes the avatar's facial expression using image editing rather than generating a totally new character.

The app supports Bring Your Own Pollen: users authorize the app with Pollinations and spend their own Pollen through a scoped user key, while the app's publishable `pk_` App Key attributes usage to the developer.

## App URL
TODO: Add deployed URL

## GitHub Repository
TODO: Add repository URL

## Main Pollinations Features Used

- BYOP authorization via `enter.pollinations.ai/authorize` with a publishable App Key.
- Image generation via `/v1/images/generations` for the initial avatar.
- Image editing via `/v1/images/edits` for expression changes.
- Optional key/profile/balance endpoints for debugging.
- Visible pollinations.ai attribution in the frontend and README, including a Built With pollinations.ai badge and links to pollinations.ai / enter.pollinations.ai.

## Why it is useful
Most AI avatar demos regenerate unrelated images each time. AI Mood demonstrates a more useful UX pattern: persistent visual identity + emotional state changes. It can be used for AI companions, game NPCs, streaming overlays, education assistants, chatbots, and agent interfaces.

## Technical Architecture

- Backend: FastAPI
- Frontend: static HTML/CSS/JS served by FastAPI
- Storage: local files for demo sessions
- Security: BYOP user key is stored in browser localStorage and sent to FastAPI per request; app owner `sk_` is optional fallback only
- Attribution: publishable `pk_` App Key is used as `client_id` in the BYOP consent flow; frontend and README credit pollinations.ai
- Consistency: first avatar is stored as the identity reference; each expression edit uses the base image by default to avoid identity drift

## Demo Flow

1. User clicks **Connect Pollinations**.
2. User authorizes AI Mood on Pollinations.
3. Pollinations redirects back with a scoped user key in the URL fragment.
4. User creates a base avatar.
5. User writes a message.
6. The app classifies the mood locally.
7. The app edits the avatar image with the new expression while preserving identity.
8. The updated expression appears in the UI.