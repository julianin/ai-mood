# Ready-to-copy GitHub issue

## Issue title

[App Submission] AI Mood — Mood Avatar Generator

## App Name

AI Mood

## App Description

AI Mood is a tiny emotional avatar web app powered by pollinations.ai. A user creates one base AI avatar, then each message in the conversation changes the avatar's facial expression using image editing rather than generating a totally new character.

The app uses pollinations.ai in three ways:

- Bring Your Own Pollen authorization through `enter.pollinations.ai/authorize` using a publishable `pk_` App Key.
- Image generation through `/v1/images/generations` to create the initial base avatar.
- Image editing through `/v1/images/edits` to update the facial expression while preserving the same character identity.

The app is intentionally simple: FastAPI backend, static HTML/CSS/JS frontend, and local demo session storage. The user's scoped BYOP key is sent to the backend per request, so users spend their own Pollen instead of the app owner's balance. A server-side `POLLINATIONS_API_KEY` can be configured only as an optional development fallback.

AI Mood also includes visible pollinations.ai credit in both the frontend and README:

- Link to https://pollinations.ai
- Link to https://enter.pollinations.ai
- Link to the official https://github.com/pollinations/pollinations repository
- Official pollinations.ai logo reference
- “Built With pollinations.ai” badge

This demonstrates a useful multimodal UX pattern: persistent visual identity + emotional state changes. It can be used as a foundation for AI companions, game NPCs, streaming overlays, education assistants, chatbots, and agent interfaces.

## App URL

TODO: paste your deployed URL here, for example:
https://YOUR-APP.onrender.com

## GitHub Open Source Repository URL

TODO: paste your public repository URL here, for example:
https://github.com/julian.ania91/ai-mood

## Discord Username

No response

## App Language

No response — the app is in English.

## Email / Other Contact

julian.ania91@gmail.com

---

## Final checklist before submitting

- [ ] You created a Pollinations account with the same GitHub username that will submit this issue.
- [ ] You created a publishable Pollinations App Key (`pk_...`).
- [ ] Your deployed domain is registered as a redirect URI for the App Key.
- [ ] Your deployed app has `POLLINATIONS_APP_KEY=pk_...` configured.
- [ ] The app works with “Connect Pollinations”.
- [ ] The README includes the pollinations.ai attribution and badge.
- [ ] The frontend visibly links to pollinations.ai.
