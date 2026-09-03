import json
import urllib.request
from dataclasses import dataclass
from typing import Dict, List


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


@dataclass
class RegionPrediction:
    region: str
    confidence: float
    reason: str = ""


class RegionAgent:
    """
    Small local AI used only for broad document-region classification.

    The model does NOT:
        - rewrite text
        - modify blocks
        - determine chapter hierarchy
        - remove OCR
        - generate EPUB

    It only answers:

        "What kind of document region is this page window?"
    """

    def __init__(
        self,
        model: str = "qwen3:4b",
        base_url: str = "http://localhost:11434",
        timeout: int = 120,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def analyze(
        self,
        pages: List[dict],
    ) -> RegionPrediction:

        prompt = self._build_prompt(pages)

        schema = {
            "type": "object",
            "properties": {
                "region": {
                    "type": "string",
                    "enum": list(REGIONS),
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
                "reason": {
                    "type": "string",
                },
            },
            "required": [
                "region",
                "confidence",
                "reason",
            ],
            "additionalProperties": False,
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": self._system_prompt(),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            "stream": False,

            # Ask Ollama for structured JSON.
            "format": schema,

            # We do not need creative generation.
            "options": {
                "temperature": 0,
            },

            # Qwen3 can think, but we don't need its reasoning here.
            "think": False,
        }

        result = self._request(payload)

        try:
            prediction = json.loads(
                result["message"]["content"]
            )
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Invalid model response: {result}"
            ) from exc

        region = prediction.get("region")

        if region not in REGIONS:
            raise ValueError(
                f"Invalid region returned by model: {region}"
            )

        confidence = float(
            prediction.get("confidence", 0)
        )

        confidence = max(
            0.0,
            min(1.0, confidence),
        )

        return RegionPrediction(
            region=region,
            confidence=confidence,
            reason=prediction.get(
                "reason",
                "",
            ),
        )

    # ------------------------------------------------------------------
    # PROMPTS
    # ------------------------------------------------------------------

    @staticmethod
    def _system_prompt() -> str:
        return """
You are a document-structure classification model.

Your ONLY job is to classify a small window of pages from a document.

Choose exactly one:

front_matter
    Material before the main work.
    Examples:
    title pages, copyright pages, publisher information,
    dedications, introductory material.

contents
    Table of contents or contents listings.

main_content
    The actual primary work.
    Examples:
    book chapters, article body, novel text, report body.

back_matter
    Material after the primary work.
    Examples:
    appendices, references, indexes, advertisements,
    publisher catalogues, author information.

Important:

- OCR may be noisy.
- Markdown heading levels may be wrong.
- Running headers may appear.
- Do not trust heading levels blindly.
- Use the actual text and surrounding context.
- Do not rewrite the supplied text.
- Do not invent missing content.
- If uncertain, choose the most likely region and lower confidence.
- Return ONLY the requested structured result.
""".strip()

    @staticmethod
    def _build_prompt(
        pages: List[dict],
    ) -> str:

        parts = [
            "Classify the following page window.",
            "",
        ]

        for page in pages:

            parts.append(
                f"===== SOURCE PAGE "
                f"{page.get('source_page')} ====="
            )

            for block in page.get(
                "blocks",
                [],
            ):

                block_id = block.get(
                    "id",
                    "",
                )

                block_type = block.get(
                    "block_type",
                    "",
                )

                text = block.get(
                    "text",
                    "",
                )

                parts.append(
                    f"[{block_id}] "
                    f"{block_type}: "
                    f"{text}"
                )

            parts.append("")

        return "\n".join(parts)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    def _request(
        self,
        payload: dict,
    ) -> dict:

        url = (
            f"{self.base_url}/api/chat"
        )

        body = json.dumps(
            payload
        ).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type":
                    "application/json",
            },
            method="POST",
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:

                raw = response.read()

        except Exception as exc:

            raise RuntimeError(
                "Could not connect to Ollama.\n"
                "Make sure Ollama is running and "
                f"model '{self.model}' is available."
            ) from exc

        try:
            return json.loads(
                raw.decode("utf-8")
            )
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON."
            ) from exc
