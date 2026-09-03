import json
import re
from pathlib import Path


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


CONTENTS_PATTERN = re.compile(
    r"^contents$",
    re.IGNORECASE,
)

BOOK_PATTERN = re.compile(
    r"^book\s+(i|ii|1|2)\b",
    re.IGNORECASE,
)

THE_END_PATTERN = re.compile(
    r"^the\s+end\.?$",
    re.IGNORECASE,
)

BACK_MATTER_PATTERN = re.compile(
    r"^(mr\.\s+william\s+heinemann['’]s\s+autumn\s+announcements"
    r"|autumn\s+announcements)$",
    re.IGNORECASE,
)


def normalize_text(text: str) -> str:
    """
    Normalize text only for matching.

    The actual block text is never modified.
    """
    text = text.strip()

    # Remove Markdown heading markers.
    text = re.sub(r"^#{1,6}\s*", "", text)

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_contents_anchor(text: str) -> bool:
    return bool(CONTENTS_PATTERN.match(normalize_text(text)))


def is_book_anchor(text: str) -> bool:
    return bool(BOOK_PATTERN.match(normalize_text(text)))


def is_end_anchor(text: str) -> bool:
    return bool(THE_END_PATTERN.match(normalize_text(text)))


def is_back_matter_anchor(text: str) -> bool:
    return bool(BACK_MATTER_PATTERN.match(normalize_text(text)))


def iter_blocks(document: dict):
    """
    Yield blocks in source order.

    Returns:
        page_index, block_index, block
    """

    for page_index, page in enumerate(document.get("pages", [])):
        for block_index, block in enumerate(page.get("blocks", [])):
            yield page_index, block_index, block


def find_region_anchors(document: dict):
    """
    Find the major structural anchors.

    We are deliberately not detecting chapters here.
    """

    anchors = {
        "contents": None,
        "main_content": None,
        "the_end": None,
        "back_matter": None,
    }

    for page_index, block_index, block in iter_blocks(document):

        text = block.get("text", "")

        position = (page_index, block_index)

        if (
            anchors["contents"] is None
            and is_contents_anchor(text)
        ):
            anchors["contents"] = position
            continue

        if (
            anchors["main_content"] is None
            and is_book_anchor(text)
        ):
            anchors["main_content"] = position
            continue

        if (
            anchors["the_end"] is None
            and is_end_anchor(text)
        ):
            anchors["the_end"] = position
            continue

        if (
            anchors["back_matter"] is None
            and is_back_matter_anchor(text)
        ):
            anchors["back_matter"] = position

    return anchors


def classify_position(position, anchors):
    """
    Determine which major region a block belongs to.
    """

    contents = anchors["contents"]
    main_content = anchors["main_content"]
    the_end = anchors["the_end"]
    back_matter = anchors["back_matter"]

    # Before CONTENTS.
    if contents is None or position < contents:
        return "front_matter"

    # CONTENTS -> BOOK I.
    if main_content is None or position < main_content:
        return "contents"

    # THE END -> back matter.
    if the_end is not None and position >= the_end:
        return "back_matter"

    # Publisher catalogue / other back matter.
    if back_matter is not None and position >= back_matter:
        return "back_matter"

    # Everything between BOOK I and THE END.
    return "main_content"


def split_document(document: dict):
    """
    Split parsed.json into major document regions.

    Original pages and blocks are preserved.
    """

    anchors = find_region_anchors(document)

    regions = {
        region: {
            "source_file": document.get("source_file"),
            "region": region,
            "pages": [],
        }
        for region in REGIONS
    }

    for page_index, page in enumerate(document.get("pages", [])):

        page_regions = {}

        for block_index, block in enumerate(page.get("blocks", [])):

            position = (page_index, block_index)

            region_name = classify_position(
                position,
                anchors,
            )

            if region_name not in page_regions:
                page_regions[region_name] = {
                    "source_page": page.get("source_page"),
                    "printed_page": page.get("printed_page"),
                    "blocks": [],
                }

            page_regions[region_name]["blocks"].append(block)

        for region_name, region_page in page_regions.items():
            regions[region_name]["pages"].append(
                region_page
            )

    return regions


def split_json(input_path: str | Path):
    input_path = Path(input_path)

    if not input_path.exists():
        raise FileNotFoundError(
            f"File not found: {input_path}"
        )

    document = json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
    )

    return split_document(document)


def save_regions(
    regions: dict,
    output_path: str | Path,
):
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            regions,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def print_summary(regions: dict):

    for region_name, region in regions.items():

        pages = region["pages"]

        block_count = sum(
            len(page["blocks"])
            for page in pages
        )

        source_pages = [
            page["source_page"]
            for page in pages
        ]

        if source_pages:
            page_range = (
                f"{min(source_pages)}-"
                f"{max(source_pages)}"
            )
        else:
            page_range = "empty"

        print(
            f"{region_name:15} "
            f"pages={len(pages):3} "
            f"blocks={block_count:4} "
            f"source_pages={page_range}"
        )


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Split parsed Document AI Markdown "
            "into major document regions."
        )
    )

    parser.add_argument(
        "input",
        type=str,
        help="Path to parsed.json",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="split.json",
        help="Output JSON path",
    )

    args = parser.parse_args()

    regions = split_json(args.input)

    save_regions(
        regions,
        args.output,
    )

    print_summary(regions)

    print(f"Output: {args.output}")
