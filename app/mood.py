from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MoodName = Literal[
    "happy",
    "sad",
    "angry",
    "anxious",
    "surprised",
    "calm",
    "confused",
    "tired",
    "excited",
    "neutral",
]


@dataclass(frozen=True)
class Mood:
    name: MoodName
    emoji: str
    label: str
    expression_prompt: str
    intensity: float


MOODS: dict[MoodName, Mood] = {
    "happy": Mood(
        "happy",
        "😊",
        "Happy",
        "a warm genuine smile, relaxed cheeks, bright friendly eyes",
        0.72,
    ),
    "sad": Mood(
        "sad",
        "😔",
        "Sad",
        "sad expression, slightly downturned mouth, soft watery eyes, lowered eyebrows",
        0.68,
    ),
    "angry": Mood(
        "angry",
        "😠",
        "Angry",
        "angry expression, furrowed eyebrows, intense eyes, tight lips, controlled frustration",
        0.7,
    ),
    "anxious": Mood(
        "anxious",
        "😟",
        "Anxious",
        "anxious worried expression, raised inner eyebrows, tense mouth, uncertain eyes",
        0.66,
    ),
    "surprised": Mood(
        "surprised",
        "😮",
        "Surprised",
        "surprised expression, wide open eyes, raised eyebrows, slightly open mouth",
        0.75,
    ),
    "calm": Mood(
        "calm",
        "😌",
        "Calm",
        "calm peaceful expression, soft closed-mouth smile, relaxed eyes, serene face",
        0.62,
    ),
    "confused": Mood(
        "confused",
        "🤔",
        "Confused",
        "confused curious expression, one eyebrow slightly raised, thoughtful squint",
        0.64,
    ),
    "tired": Mood(
        "tired",
        "🥱",
        "Tired",
        "tired sleepy expression, heavy eyelids, soft slack face, gentle fatigue",
        0.6,
    ),
    "excited": Mood(
        "excited",
        "🤩",
        "Excited",
        "excited delighted expression, big smile, sparkling eyes, energetic face",
        0.82,
    ),
    "neutral": Mood(
        "neutral",
        "🙂",
        "Neutral",
        "neutral attentive expression, relaxed face, natural mouth, direct gaze",
        0.5,
    ),
}

_KEYWORDS: list[tuple[MoodName, tuple[str, ...]]] = [
    ("angry", ("hate", "fed up", "angry", "furious", "rage", "annoyed", "irritated", "pissed", "mad", "wtf", "screw this")),
    ("sad", ("sad", "bad", "cry", "depressed", "lonely", "empty", "grief", "discouraged", "hurt", "heartbroken", "down")),
    ("anxious", ("anxious", "anxiety", "nervous", "scared", "worried", "stressed", "overwhelmed", "panic", "i can't", "urgent", "afraid")),
    ("surprised", ("wow", "no way", "i can't believe", "surprise", "amazing", "unexpected", "shocked", "what do you mean")),
    ("excited", ("let's go", "awesome", "amazing", "i love", "hyped", "motivated", "excited", "can't wait", "so cool", "great")),
    ("happy", ("happy", "glad", "good", "thanks", "perfect", "lol", "haha", "smile", "joy", "cheerful")),
    ("confused", ("i don't understand", "confused", "question", "how", "what does", "explain", "lost", "unclear", "not sure")),
    ("tired", ("tired", "exhausted", "sleepy", "sleep", "fatigue", "burned out", "burnout", "drained")),
    ("calm", ("calm", "peaceful", "relaxed", "peace", "breathe", "serene", "steady")),
]


def classify_mood(text: str) -> Mood:
    """Small local classifier: cheap, fast, good enough for a demo.

    It avoids spending Pollen on mood detection. You can replace this with
    /v1/chat/completions later if you want deeper conversation analysis.
    """
    normalized = f" {text.lower().strip()} "
    scores: dict[MoodName, int] = {name: 0 for name in MOODS}

    for mood, words in _KEYWORDS:
        for word in words:
            if word in normalized:
                scores[mood] += 1

    # Tiny punctuation heuristics
    if "!" in text:
        scores["excited"] += 1
    if "?" in text:
        scores["confused"] += 1
    if text.isupper() and len(text) > 8:
        scores["angry"] += 1

    best = max(scores.items(), key=lambda kv: kv[1])
    if best[1] == 0:
        return MOODS["neutral"]
    return MOODS[best[0]]
