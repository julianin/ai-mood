from __future__ import annotations

import base64
import mimetypes
import os
from pathlib import Path
from typing import Any

import httpx


class PollinationsError(RuntimeError):
    pass


class PollinationsClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or "").strip()
        self.base_url = os.getenv("POLLINATIONS_BASE_URL", "https://gen.pollinations.ai").rstrip("/")
        self.generate_model = os.getenv("POLLINATIONS_GENERATE_MODEL", "flux")
        self.edit_model = os.getenv("POLLINATIONS_EDIT_MODEL", "gptimage")
        self.size = os.getenv("IMAGE_SIZE", "768x768")
        self.quality = os.getenv("IMAGE_QUALITY", "medium")

        if not self.api_key:
            raise PollinationsError(
                "Missing API key. Connect with Bring Your Own Pollen or set POLLINATIONS_API_KEY."
            )

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    async def profile(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{self.base_url}/account/profile", headers=self.headers)
            return self._json_or_raise(res)

    async def balance(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{self.base_url}/account/balance", headers=self.headers)
            return self._json_or_raise(res)

    async def key_info(self) -> dict[str, Any]:
        # Useful for BYOP keys because /account/key does not reveal the secret and
        # helps users see expiry/budget/model restrictions.
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(f"{self.base_url}/account/key", headers=self.headers)
            return self._json_or_raise(res)

    async def generate_avatar(self, prompt: str) -> bytes:
        payload = {
            "model": self.generate_model,
            "prompt": prompt,
            "n": 1,
            "size": self.size,
            "quality": self.quality,
            "response_format": "b64_json",
            "safe": "true",
        }
        async with httpx.AsyncClient(timeout=180) as client:
            res = await client.post(
                f"{self.base_url}/v1/images/generations",
                headers={**self.headers, "Content-Type": "application/json"},
                json=payload,
            )
            data = self._json_or_raise(res)
            return await self._image_bytes_from_response(data, client)

    async def edit_avatar(self, source_image: Path, prompt: str) -> bytes:
        """Edit an existing avatar.

        Pollinations documents POST /v1/images/edits as OpenAI-compatible and says it
        accepts multipart/form-data with file uploads. Some providers expect the file
        field to be named `image`, others `image[]`, so we try both.
        """
        mime = mimetypes.guess_type(source_image.name)[0] or "image/png"
        data = {
            "model": self.edit_model,
            "prompt": prompt,
            "n": "1",
            "size": self.size,
            "quality": self.quality,
            "response_format": "b64_json",
            "safe": "true",
        }

        last_error: str | None = None
        for field_name in ("image", "image[]"):
            async with httpx.AsyncClient(timeout=240) as client:
                with source_image.open("rb") as f:
                    files = {field_name: (source_image.name, f, mime)}
                    res = await client.post(
                        f"{self.base_url}/v1/images/edits",
                        headers=self.headers,
                        data=data,
                        files=files,
                    )
                if res.is_success:
                    payload = res.json()
                    return await self._image_bytes_from_response(payload, client)
                last_error = f"{res.status_code}: {res.text[:800]}"

        raise PollinationsError(f"Image edit failed. Last response: {last_error}")

    async def fallback_variation(self, prompt: str) -> bytes:
        """Fallback if /edits has an upstream model issue.

        This is not true editing, but it keeps the demo usable by generating a new
        image with the same identity prompt.
        """
        return await self.generate_avatar(prompt)

    async def classify_mood(self, text: str) -> str:
        """Use a cheap LLM call to classify the emotional tone of a message.

        Returns one of the valid mood names. Falls back to 'neutral' on any error.
        This uses the OpenAI-compatible chat completions endpoint with a minimal prompt.
        """
        import json

        valid_moods = "happy, sad, angry, anxious, surprised, calm, confused, tired, excited, neutral"
        system_msg = (
            f"You are an emotion classifier. Given a user message, respond with exactly one word "
            f"from this list: {valid_moods}. No explanation, no punctuation, just the mood word."
        )
        payload = {
            "model": os.getenv("POLLINATIONS_MOOD_MODEL", "openai"),
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": text},
            ],
            "max_tokens": 10,
            "temperature": 0.1,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={**self.headers, "Content-Type": "application/json"},
                    json=payload,
                )
                data = self._json_or_raise(res)
                content = data["choices"][0]["message"]["content"].strip().lower()
                # Extract just the mood word
                for word in content.split():
                    if word in {"happy", "sad", "angry", "anxious", "surprised", "calm", "confused", "tired", "excited", "neutral"}:
                        return word
                return "neutral"
        except Exception:
            return "neutral"

    async def _image_bytes_from_response(self, data: dict[str, Any], client: httpx.AsyncClient) -> bytes:
        try:
            item = data["data"][0]
        except Exception as exc:
            raise PollinationsError(f"Unexpected image response: {data}") from exc

        if item.get("b64_json"):
            return base64.b64decode(item["b64_json"])

        if item.get("url"):
            img = await client.get(item["url"], headers=self.headers)
            img.raise_for_status()
            return img.content

        raise PollinationsError(f"Image response had no b64_json or url: {data}")

    def _json_or_raise(self, res: httpx.Response) -> dict[str, Any]:
        if not res.is_success:
            raise PollinationsError(f"Pollinations error {res.status_code}: {res.text[:1000]}")
        try:
            return res.json()
        except Exception as exc:
            raise PollinationsError(f"Expected JSON but got: {res.text[:500]}") from exc
