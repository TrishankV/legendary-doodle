import json
from pathlib import Path
from typing import Any, Dict, List

from google import genai
from google.genai import types


class GeminiBoundaryAgent:
    """
    Gemini implementation of the boundary-classification interface.

    The agent does NOT classify every page.

    It is only asked to determine whether a candidate structural
    boundary exists between two regions, for example:

        front_matter -> contents
        contents -> main_content
        main_content -> back_matter
    """

    def __init__(
        self,
        model_name: str = "gemini-2.5-flash",
        config_path: str = "configuration.json",
    ):
        self.model_name = model_name
        self.config_path = config_path

        api_key = self._load_api_key(config_path)

        if not api_key:
            raise ValueError(
                f"Google API key not found in {config_path}"
            )

        self.client = genai.Client(api_key=api_key)

    # ---------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------

    def _load_api_key(self, config_path: str) -> str:
        """
        Load the Gemini API key from configuration.json.

        Expected structure:

        {
            "google": {
                "api_key": "YOUR_KEY"
            }
        }
        """

        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {path}"
            )

        with path.open("r", encoding="utf-8") as f:
            config = json.load(f)

        google_config = config.get("google", {})

        api_key = google_config.get("api_key")

        if not api_key:
            raise ValueError(
                f"No Google API key found under "
                f"'google.api_key' in {config_path}"
            )

        return api_key

    # ---------------------------------------------------------
    # Page formatting
    # ---------------------------------------------------------

    def _format_page(self, page: Dict[str, Any]) -> str:
        """
        Convert one parsed page into compact text for Gemini.
        """

        page_number = page.get("source_page", "?")

        blocks = page.get("blocks", [])

        lines = [
            f"--- SOURCE PAGE {page_number} ---"
        ]

        for block in blocks:
            block_type = block.get("block_type", "unknown")
            text = block.get("text", "")

            if not text:
                continue

            lines.append(
                f"[{block_type}] {text}"
            )

        return "\n".join(lines)

    def _format_pages(
        self,
        pages: List[Dict[str, Any]],
    ) -> str:
        """
        Convert a list of parsed pages into compact text.
        """

        return "\n\n".join(
            self._format_page(page)
            for page in pages
        )

    # ---------------------------------------------------------
    # Boundary classification
    # ---------------------------------------------------------

    def classify_boundary(
        self,
        before_pages: List[Dict[str, Any]],
        after_pages: List[Dict[str, Any]],
        expected_transition: str,
    ) -> Dict[str, Any]:
        """
        Determine whether the supplied page boundary represents
        the expected structural transition.

        Example:

            before_pages = pages before candidate
            after_pages  = pages after candidate

            expected_transition = "contents_to_main_content"
        """

        before_text = self._format_pages(before_pages)
        after_text = self._format_pages(after_pages)

        prompt = f"""
You are a document-structure boundary detector.

Your job is NOT to classify individual pages.

Your only task is to determine whether the boundary between
the supplied BEFORE pages and AFTER pages represents the
expected structural transition.

Expected transition:

{expected_transition}

Possible transitions:

- front_matter_to_contents
- contents_to_main_content
- main_content_to_back_matter
- none

Rules:

1. Look at the structural relationship between the BEFORE
   and AFTER material.

2. Do not assume that a single heading is sufficient unless
   the surrounding context supports it.

3. A table of contents may contain entries that look like
   chapter headings. Do not mistake TOC entries for actual
   chapter starts.

4. Actual main content normally contains substantial prose,
   sections, chapters, or body text rather than merely a list
   of titles and page numbers.

5. Back matter may contain references, bibliography, appendix,
   index, glossary, notes, acknowledgements, or similar
   material.

6. The candidate boundary may be imperfect. Use the surrounding
   pages to make the decision.

7. Return ONLY valid JSON.

BEFORE PAGES
============
{before_text}

AFTER PAGES
===========

{after_text}

Return this JSON structure:

{{
    "decision": "yes" | "no",
    "transition": "{expected_transition}" | "none",
    "confidence": 0.0,
    "reason": "short explanation"
}}

Confidence must be a number between 0.0 and 1.0.

Do not return Markdown.
Do not return code fences.
Return JSON only.
"""

        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema={
                    "type": "OBJECT",
                    "properties": {
                        "decision": {
                            "type": "STRING",
                            "enum": ["yes", "no"],
                        },
                        "transition": {
                            "type": "STRING",
                            "enum": [
                                "front_matter_to_contents",
                                "contents_to_main_content",
                                "main_content_to_back_matter",
                                "none",
                            ],
                        },
                        "confidence": {
                            "type": "NUMBER",
                        },
                        "reason": {
                            "type": "STRING",
                        },
                    },
                    "required": [
                        "decision",
                        "transition",
                        "confidence",
                        "reason",
                    ],
                },
            ),
        )

        if not response.text:
            raise ValueError(
                "Gemini returned an empty response"
            )

        result = json.loads(response.text)

        # -----------------------------------------------------
        # Validate response
        # -----------------------------------------------------

        decision = result.get("decision")

        if decision not in {"yes", "no"}:
            raise ValueError(
                f"Invalid Gemini decision: {decision}"
            )

        transition = result.get("transition", "none")

        allowed_transitions = {
            "front_matter_to_contents",
            "contents_to_main_content",
            "main_content_to_back_matter",
            "none",
        }

        if transition not in allowed_transitions:
            transition = "none"

        try:
            confidence = float(
                result.get("confidence", 0.0)
            )
        except (TypeError, ValueError):
            confidence = 0.0

        confidence = max(
            0.0,
            min(1.0, confidence),
        )

        reason = str(
            result.get("reason", "")
        ).strip()

        return {
            "decision": decision,
            "transition": transition,
            "confidence": confidence,
            "reason": reason,
        }


# -------------------------------------------------------------
# Manual test
# -------------------------------------------------------------

if __name__ == "__main__":
    agent = GeminiBoundaryAgent()

    result = agent.classify_boundary(
        before_pages=[
            {
                "source_page": 1,
                "blocks": [
                    {
                        "block_type": "heading",
                        "text": "Contents",
                    }
                ],
            }
        ],
        after_pages=[
            {
                "source_page": 2,
                "blocks": [
                    {
                        "block_type": "heading",
                        "text": "Chapter 1",
                    },
                    {
                        "block_type": "paragraph",
                        "text": "This is the beginning of the main text.",
                    },
                ],
            }
        ],
        expected_transition="contents_to_main_content",
    )

    print(json.dumps(result, indent=2))