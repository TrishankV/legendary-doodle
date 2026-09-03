import json
from pathlib import Path
from typing import List

from google import genai
from google.genai import types


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
    "unknown",
)


class GeminiRegionAgent:
    """
    Gemini implementation of the generic RegionClassifier interface.

    The splitter does not depend on Gemini directly.

    The splitter only expects an AI object with:

        classify(pages)

    This class implements that contract using Google's Gemini API.
    """

    def __init__(
        self,
        model: str = "gemini-2.5-flash",
        config_path: str | Path = "configuration.json",
    ):
        self.model = model
        self.config_path = Path(
            config_path
        )

        api_key = self._load_api_key()

        self.client = genai.Client(
            api_key=api_key
        )

    # ============================================================
    # CONFIGURATION
    # ============================================================

    def _load_api_key(self) -> str:
        """
        Load the Google API key from configuration.json.

        Expected structure:

        {
            "google": {
                "api_key": "YOUR_API_KEY"
            }
        }
        """

        if not self.config_path.exists():
            raise FileNotFoundError(
                "Configuration file not found: "
                f"{self.config_path}"
            )

        try:
            config = json.loads(
                self.config_path.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError as exc:
            raise ValueError(
                "Invalid JSON in configuration file: "
                f"{self.config_path}"
            ) from exc

        try:
            api_key = (
                config[
                    "google"
                ][
                    "api_key"
                ]
            )

        except (
            KeyError,
            TypeError,
        ) as exc:

            raise KeyError(
                'Expected configuration.json to contain:\n'
                '"google": {\n'
                '    "api_key": "..."\n'
                '}'
            ) from exc

        if (
            not isinstance(
                api_key,
                str,
            )
            or not api_key.strip()
        ):
            raise ValueError(
                '"google.api_key" must be a '
                "non-empty string."
            )

        return api_key.strip()

    # ============================================================
    # PAGE FORMATTING
    # ============================================================

    @staticmethod
    def _format_pages(
        pages: List[dict],
    ) -> str:
        """
        Convert structured page data into a compact textual
        representation for the model.
        """

        output = []

        for page in pages:

            source_page = page.get(
                "source_page",
                "unknown",
            )

            output.append(
                (
                    f"\n===== SOURCE PAGE "
                    f"{source_page} ====="
                )
            )

            blocks = page.get(
                "blocks",
                [],
            )

            if not blocks:

                output.append(
                    "[EMPTY PAGE]"
                )

                continue

            for block in blocks:

                block_id = block.get(
                    "id",
                    "unknown",
                )

                block_type = block.get(
                    "block_type",
                    "unknown",
                )

                markdown_level = block.get(
                    "markdown_level"
                )

                text = block.get(
                    "text",
                    "",
                )

                if markdown_level is not None:

                    output.append(
                        (
                            f"[{block_id}] "
                            f"type={block_type} "
                            f"markdown_level="
                            f"{markdown_level}\n"
                            f"{text}"
                        )
                    )

                else:

                    output.append(
                        (
                            f"[{block_id}] "
                            f"type={block_type}\n"
                            f"{text}"
                        )
                    )

        return "\n".join(
            output
        )

    # ============================================================
    # PROMPT
    # ============================================================

    @staticmethod
    def _build_prompt(
        pages: List[dict],
    ) -> str:
        """
        Build the classification prompt.

        The model is deliberately restricted to broad
        document regions. It is not asked to detect chapters.
        """

        page_numbers = [
            page.get("source_page")
            for page in pages
            if page.get("source_page") is not None
        ]

        if page_numbers:

            page_range = (
                f"Source pages "
                f"{min(page_numbers)}-"
                f"{max(page_numbers)}"
            )

        else:

            page_range = (
                "Source page numbers unavailable"
            )

        formatted_pages = (
            GeminiRegionAgent._format_pages(
                pages
            )
        )

        return f"""
You are a document-structure classification agent.

Your task is to classify the supplied page window into exactly
ONE high-level document region.

{page_range}

Allowed regions:

1. front_matter

Material that appears before the primary work.

Examples:
- title pages
- author information
- copyright pages
- publisher information
- dedications
- prefaces
- forewords
- introductory material
- preliminary pages

2. contents

Material that functions as a table of contents or navigation.

Examples:
- table of contents
- chapter listings
- book/part listings
- navigational page lists

3. main_content

The primary work contained in the document.

Examples:
- novel/story text
- chapters
- article body
- report body
- manual sections
- thesis chapters
- primary document content

4. back_matter

Material that occurs after the primary work.

Examples:
- appendices
- references
- bibliography
- indexes
- glossaries
- publisher catalogues
- advertisements
- author information
- additional publisher material

5. unknown

Use this only when there is genuinely insufficient information
to make a reliable classification.

IMPORTANT RULES:

- OCR may contain spelling errors and corrupted characters.
- Markdown heading levels may be incorrect.
- Do not trust heading levels by themselves.
- Running headers can look like real headings.
- A repeated title at the top of a page may be a running header,
  not a new section.
- A table-of-contents entry may look exactly like a chapter heading.
- Consider the surrounding pages in the window.
- Do not rewrite the supplied text.
- Do not correct OCR.
- Do not summarize the supplied text.
- Do not invent missing content.
- Do not identify individual chapters in this task.
- Only classify the broad document region.
- Confidence must be a number between 0 and 1.

Return ONLY this JSON structure:

{{
    "region": "front_matter | contents | main_content | back_matter | unknown",
    "confidence": 0.0,
    "reason": "brief explanation"
}}

PAGE WINDOW:

{formatted_pages}
""".strip()

    # ============================================================
    # CLASSIFICATION
    # ============================================================

    def classify(
        self,
        pages: List[dict],
    ) -> dict:
        """
        Classify a page window.

        This is the method required by splitter.py.
        """

        if not pages:
            raise ValueError(
                "Cannot classify an empty page window."
            )

        prompt = self._build_prompt(
            pages
        )

        try:

            response = (
                self.client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0,
                        response_mime_type="application/json",
                        response_schema={
                            "type": "OBJECT",
                            "properties": {
                                "region": {
                                    "type": "STRING",
                                    "enum": list(
                                        REGIONS
                                    ),
                                },
                                "confidence": {
                                    "type": "NUMBER",
                                },
                                "reason": {
                                    "type": "STRING",
                                },
                            },
                            "required": [
                                "region",
                                "confidence",
                                "reason",
                            ],
                        },
                    ),
                )
            )

        except Exception as exc:

            raise RuntimeError(
                "Gemini request failed: "
                f"{exc}"
            ) from exc

        if not response.text:

            raise RuntimeError(
                "Gemini returned an empty response."
            )

        try:

            result = json.loads(
                response.text
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "Gemini returned invalid JSON:\n"
                f"{response.text}"
            ) from exc

        region = result.get(
            "region"
        )

        if region not in REGIONS:

            raise ValueError(
                "Gemini returned invalid region: "
                f"{region}"
            )

        try:

            confidence = float(
                result.get(
                    "confidence",
                    0.0,
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            confidence = 0.0

        confidence = max(
            0.0,
            min(
                1.0,
                confidence,
            ),
        )

        reason = str(
            result.get(
                "reason",
                "",
            )
        )

        return {
            "region": region,
            "confidence": confidence,
            "reason": reason,
        }


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":

    agent = GeminiRegionAgent()

    test_pages = [
        {
            "source_page": 11,
            "blocks": [
                {
                    "id": "p0011_b001",
                    "block_type": "heading",
                    "markdown_level": 1,
                    "text": "CONTENTS",
                },
                {
                    "id": "p0011_b002",
                    "block_type": "paragraph",
                    "markdown_level": None,
                    "text": (
                        "Chapter I ........ 1\n"
                        "Chapter II ....... 12\n"
                        "Chapter III ...... 24"
                    ),
                },
            ],
        }
    ]

    result = agent.classify(
        test_pages
    )

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )
    )