from __future__ import annotations

import json
import re
from typing import Optional

from app.core.config import settings

# ── Prompt templates ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are INSPECTRA, an industrial quality inspection AI assistant.
Your role is to help operators understand product defects and decide on corrective actions, \
based strictly on retrieved SOP and QA documents.

Rules you MUST follow:
1. NEVER state a definitive root cause unless the provided evidence explicitly confirms it.
2. Always use cautious, qualified language:
   - "possible root cause"
   - "likely inspection checkpoint"
   - "based on retrieved SOP evidence"
   - "further investigation may be needed"
3. If the retrieved evidence is weak, sparse, or absent, set human_review_required to true \
and recommend escalation to a qualified inspector.
4. Keep your response professional, concise, and grounded in the provided evidence.
5. Return ONLY valid JSON — no markdown, no code fences, no extra text — with exactly these fields:
   {
     "answer": "<clear explanation of the defect situation>",
     "possible_root_cause": "<qualified root cause statement>",
     "recommended_action": "<action drawn from SOP evidence, or escalation if unavailable>",
     "human_review_required": true | false
   }
"""

_USER_PROMPT_TEMPLATE = """\
## Inspection Context
Product category : {product_category}
Defect status    : {status}
Anomaly score    : {anomaly_score}
Severity         : {severity}
Defect type      : {defect_type}

## User Question
{question}

## Retrieved SOP / QA Evidence ({evidence_count} chunk(s))
{evidence_text}

Analyse the above and respond with valid JSON only.
"""

_FALLBACK_RESPONSE = {
    "answer": (
        "The AI explanation service encountered an issue. "
        "Please review the inspection result manually."
    ),
    "possible_root_cause": "Unable to determine — human review is required.",
    "recommended_action": "Escalate to a qualified inspector for manual evaluation.",
    "human_review_required": True,
}


# ── Service class ─────────────────────────────────────────────────────────────


class GroqService:
    """Calls the Groq LLM API to generate grounded defect explanations."""

    def _require_api_key(self) -> None:
        if not settings.groq_configured:
            raise ValueError(
                "GROQ_API_KEY is not configured. "
                "Add your key to backend/.env and restart the server."
            )

    def _get_client(self):
        from groq import Groq
        return Groq(api_key=settings.GROQ_API_KEY)

    def _format_evidence(self, rag_evidence: list[dict]) -> str:
        if not rag_evidence:
            return "No evidence retrieved."
        lines = []
        for i, chunk in enumerate(rag_evidence, start=1):
            doc = chunk.get("document_name", "Unknown")
            page = chunk.get("page_number", "?")
            text = chunk.get("text", "").strip()
            lines.append(f"[{i}] {doc} (page {page}):\n{text}")
        return "\n\n".join(lines)

    def _parse_llm_json(self, raw: str) -> dict:
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {}

    def _build_user_prompt(
        self,
        question: str,
        prediction: Optional[dict],
        rag_evidence: list[dict],
        product_category: str,
    ) -> str:
        pred = prediction or {}
        return _USER_PROMPT_TEMPLATE.format(
            product_category=product_category,
            status=pred.get("status", "unknown"),
            anomaly_score=pred.get("anomaly_score", "N/A"),
            severity=pred.get("severity", "N/A"),
            defect_type=pred.get("defect_type", "unknown"),
            question=question,
            evidence_count=len(rag_evidence),
            evidence_text=self._format_evidence(rag_evidence),
        )

    def generate_explanation(
        self,
        question: str,
        prediction: Optional[dict],
        rag_evidence: list[dict],
        product_category: str,
    ) -> dict:
        self._require_api_key()

        no_evidence = len(rag_evidence) == 0
        user_prompt = self._build_user_prompt(
            question, prediction, rag_evidence, product_category
        )

        client = self._get_client()
        try:
            completion = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            raw = completion.choices[0].message.content or ""
        except Exception as exc:
            raise RuntimeError(f"Groq API call failed: {exc}") from exc

        parsed = self._parse_llm_json(raw)

        result = {
            "answer": parsed.get("answer") or _FALLBACK_RESPONSE["answer"],
            "possible_root_cause": parsed.get("possible_root_cause")
                or _FALLBACK_RESPONSE["possible_root_cause"],
            "recommended_action": parsed.get("recommended_action")
                or _FALLBACK_RESPONSE["recommended_action"],
            "human_review_required": bool(
                parsed.get("human_review_required", no_evidence)
            ),
        }

        if no_evidence:
            result["human_review_required"] = True

        return result

    def is_configured(self) -> bool:
        return settings.groq_configured


groq_service = GroqService()
