import json
import re
from pathlib import Path
from typing import Optional

from .models import Block, Document, Page


PAGE_BREAK_PATTERN = "<!-- PageBreak -->"


def classify_block(text: str) -> str:
    """
    Classify a raw Markdown block using only deterministic syntax.

    Possible block types:
        blank
        metadata
        heading
        table
        paragraph
    """

    text = text.strip()

    if not text:
        return "blank"

    # Document AI metadata.
    # Examples:
    # <!-- PageNumber="3" -->
    # <!-- PageHeader="..." -->
    # <!-- PageFooter="..." -->
    if (
        text.startswith("<!--")
        and text.endswith("-->")
    ):
        return "metadata"

    # Markdown heading.
    if re.match(
        r"^#{1,6}(?:\s|$)",
        text,
    ):
        return "heading"

    # Markdown / HTML table.
    if (
        text.startswith("|")
        or text.startswith("<table")
    ):
        return "table"

    return "paragraph"


def extract_heading_level(
    text: str,
) -> Optional[int]:
    """
    Extract Markdown heading level.

    Returns:
        1-6 for a Markdown heading
        None otherwise
    """

    match = re.match(
        r"^(#{1,6})(?:\s+|$)",
        text.strip(),
    )

    if not match:
        return None

    return len(
        match.group(1)
    )


def parse_page(
    page_text: str,
    source_page: int,
) -> Page:
    """
    Parse one source page into structured blocks.
    """

    page = Page(
        source_page=source_page
    )

    raw_blocks = re.split(
        r"\n\s*\n",
        page_text,
    )

    block_number = 0

    for raw_block in raw_blocks:

        text = raw_block.strip()

        if not text:
            continue

        block_number += 1

        block_id = (
            f"p{source_page:04d}"
            f"_b{block_number:03d}"
        )

        block = Block(
            id=block_id,
            text=text,
            block_type=classify_block(
                text
            ),
            markdown_level=extract_heading_level(
                text
            ),
        )

        page.blocks.append(
            block
        )

    return page


def parse_markdown(
    path: str | Path,
) -> Document:
    """
    Parse the complete Document AI Markdown file.

    PageBreak markers define source pages.
    """

    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(
            f"Input file not found: {path}"
        )

    text = path.read_text(
        encoding="utf-8",
        errors="replace",
    )

    raw_pages = text.split(
        PAGE_BREAK_PATTERN
    )

    document = Document(
        source_file=str(path)
    )

    for (
        source_page,
        page_text,
    ) in enumerate(
        raw_pages,
        start=1,
    ):

        document.pages.append(
            parse_page(
                page_text,
                source_page,
            )
        )

    return document


def document_to_dict(
    document: Document,
) -> dict:
    """
    Convert Document dataclasses into JSON-compatible data.
    """

    return {
        "source_file": document.source_file,
        "page_count": document.page_count,
        "block_count": document.block_count,
        "pages": [
            {
                "source_page": page.source_page,
                "printed_page": page.printed_page,
                "blocks": [
                    {
                        "id": block.id,
                        "text": block.text,
                        "block_type": block.block_type,
                        "markdown_level": block.markdown_level,
                    }
                    for block in page.blocks
                ],
            }
            for page in document.pages
        ],
    }


def save_json(
    document: Document,
    output_path: str | Path,
) -> None:
    """
    Save parsed document to JSON.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            document_to_dict(
                document
            ),
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Parse Document AI Markdown "
            "into a page-aware JSON structure."
        )
    )

    parser.add_argument(
        "input",
        help="Input Markdown file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="parsed.json",
        help="Output JSON file.",
    )

    args = parser.parse_args()

    document = parse_markdown(
        args.input
    )

    save_json(
        document,
        args.output,
    )

    print(
        f"Parsed document saved to {args.output}"
    )

    print(
        f"Pages: {document.page_count}"
    )

    print(
        f"Blocks: {document.block_count}"
    )