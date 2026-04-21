"""OpenAI API ranking for CV vs job requirements (no Azure required)."""

from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = (
    "You are an expert HR recruiter. Analyze this CV and score it against the job requirements. "
    "Respond with a JSON object only, no markdown, with keys: "
    '"score" (integer 1-10) and "reasoning" (string, 2-3 sentences explaining the score).'
)


def rank_cv(
    cv_text: str,
    job_title: str,
    job_requirements: str,
    api_key: str,
    model: str,
) -> dict[str, Any]:
    client = OpenAI(api_key=api_key)
    user_content = (
        f"Job title: {job_title}\n\n"
        f"Job requirements:\n{job_requirements}\n\n"
        f"CV text:\n{cv_text}\n"
    )
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        temperature=0.2,
        max_tokens=500,
    )
    raw = (completion.choices[0].message.content or "").strip()
    return _parse_response(raw)


def _parse_response(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    data = json.loads(raw)
    score = int(data.get("score", 0))
    score = max(1, min(10, score))
    reasoning = str(data.get("reasoning", "")).strip()
    if not reasoning:
        reasoning = "No reasoning provided by model."
    return {"score": score, "reasoning": reasoning}
