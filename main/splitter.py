import json
import re
from pathlib import Path
from typing import Dict, List, Optional


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


# ---------------------------------------------------------------------------
# TEXT NORMALIZATION
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize text for comparison only.

    The original block text is never changed.
    """

    text = text.strip()

    # Remove Markdown heading markers.
    text = re.sub(r"^#{1,6}\s*", "", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ---------------------------------------------------------------------------
# BLOCK HELPERS
# ---------------------------------------------------------------------------

def is_heading(block: dict) -> bool:
    """
    Check whether the parser classified this block as a heading.
    """

    return block.get("block_type") == "heading"


def is_metadata(block: dict) -> bool:
    """
    Check whether the parser classified this block as metadata.
    """

    return block.get("block_type") == "metadata"


def heading_text(block: dict) -> str:
    """
    Return normalized heading text.
    """

    return normalize_text(
        block.get("text", "")
    )


def block_text(block: dict) -> str:
    """
    Return normalized block text.
    """

    return normalize_text(
        block.get("text", "")
    )


# ---------------------------------------------------------------------------
# GENERIC STRUCTURAL DETECTION
# ---------------------------------------------------------------------------

def looks_like_contents_heading(text: str) -> bool:
    """
    Detect common table-of-contents headings.

    This is intentionally generic.
    """

    text = normalize_text(text).lower()

    contents_names = {
        "contents",
        "table of contents",
        "contents page",
        "table contents",
    }

    return text in contents_names


def looks_like_main_content_heading(text: str) -> bool:
    """
    Detect headings that commonly mark the beginning
    of the main document content.

    This is deliberately broad rather than document-specific.
    """

    text = normalize_text(text).lower()

    patterns = [
        r"^book\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)$",
        r"^part\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)$",
        r"^chapter\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)$",
        r"^chapter\s+\d+$",
        r"^section\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)$",
    ]

    return any(
        re.match(pattern, text)
        for pattern in patterns
    )


def looks_like_back_matter_heading(text: str) -> bool:
    """
    Detect common headings that usually indicate
    material after the main document.
    """

    text = normalize_text(text).lower()

    back_matter_names = {
        "appendix",
        "appendices",
        "references",
        "bibliography",
        "index",
        "glossary",
        "notes",
        "endnotes",
        "acknowledgements",
        "acknowledgments",
        "afterword",
        "postscript",
        "about the author",
        "author's note",
        "authors note",
    }

    return text in back_matter_names


def looks_like_end_marker(text: str) -> bool:
    """
    Detect common document-ending markers.
    """

    text = normalize_text(text).lower()

    end_markers = {
        "the end",
        "end",
        "fin",
    }

    return text in end_markers


# ---------------------------------------------------------------------------
# BLOCK ITERATION
# ---------------------------------------------------------------------------

def iter_blocks(document: dict):
    """
    Iterate through blocks in source order.

    Yields:
        page_index
        block_index
        block
    """

    for page_index, page in enumerate(
        document.get("pages", [])
    ):

        for block_index, block in enumerate(
            page.get("blocks", [])
        ):

            yield (
                page_index,
                block_index,
                block,
            )


# ---------------------------------------------------------------------------
# ANCHOR DETECTION
# ---------------------------------------------------------------------------

def find_structural_anchors(
    document: dict,
) -> Dict[str, Optional[dict]]:
    """
    Find generic structural boundaries.

    The splitter looks for:
        - contents
        - beginning of main content
        - beginning of back matter
        - document ending

    The actual text is preserved.
    """

    anchors = {
        "contents": None,
        "main_content": None,
        "back_matter": None,
        "end": None,
    }

    for (
        page_index,
        block_index,
        block,
    ) in iter_blocks(document):

        if not is_heading(block):
            continue

        text = heading_text(block)

        position = {
            "page_index": page_index,
            "block_index": block_index,
            "source_page": document[
                "pages"
            ][page_index].get(
                "source_page"
            ),
            "block_id": block.get(
                "id"
            ),
            "text": text,
            "markdown_level": block.get(
                "markdown_level"
            ),
        }

        # First contents heading.
        if (
            anchors["contents"] is None
            and looks_like_contents_heading(text)
        ):
            anchors["contents"] = position
            continue

        # First heading that strongly resembles
        # the beginning of the main content.
        if (
            anchors["main_content"] is None
            and looks_like_main_content_heading(text)
        ):
            anchors["main_content"] = position
            continue

        # First heading that strongly resembles
        # back matter.
        if (
            anchors["back_matter"] is None
            and looks_like_back_matter_heading(text)
        ):
            anchors["back_matter"] = position
            continue

        # First explicit end marker.
        if (
            anchors["end"] is None
            and looks_like_end_marker(text)
        ):
            anchors["end"] = position

    return anchors


# ---------------------------------------------------------------------------
# POSITION COMPARISON
# ---------------------------------------------------------------------------

def position_of(
    page_index: int,
    block_index: int,
):
    """
    Return a comparable source-order position.
    """

    return (
        page_index,
        block_index,
    )


def anchor_position(
    anchor: Optional[dict],
):
    """
    Return the position of an anchor.
    """

    if anchor is None:
        return None

    return (
        anchor["page_index"],
        anchor["block_index"],
    )


# ---------------------------------------------------------------------------
# REGION CLASSIFICATION
# ---------------------------------------------------------------------------

def classify_position(
    page_index: int,
    block_index: int,
    anchors: Dict[str, Optional[dict]],
) -> str:
    """
    Determine which broad region a block belongs to.
    """

    position = position_of(
        page_index,
        block_index,
    )

    contents = anchor_position(
        anchors["contents"]
    )

    main_content = anchor_position(
        anchors["main_content"]
    )

    back_matter = anchor_position(
        anchors["back_matter"]
    )

    end = anchor_position(
        anchors["end"]
    )

    # -------------------------------------------------------
    # FRONT MATTER
    # -------------------------------------------------------

    if (
        contents is not None
        and position < contents
    ):
        return "front_matter"

    # If there is no contents section but main content
    # exists, everything before main content is front matter.
    if (
        contents is None
        and main_content is not None
        and position < main_content
    ):
        return "front_matter"

    # -------------------------------------------------------
    # CONTENTS
    # -------------------------------------------------------

    if contents is not None:

        contents_end = main_content

        if (
            contents_end is not None
            and contents <= position < contents_end
        ):
            return "contents"

        # If no main-content anchor exists,
        # use the contents region until back matter/end.
        if contents_end is None:

            if (
                back_matter is not None
                and contents <= position < back_matter
            ):
                return "contents"

            if (
                end is not None
                and contents <= position < end
            ):
                return "contents"

    # -------------------------------------------------------
    # BACK MATTER
    # -------------------------------------------------------

    if (
        back_matter is not None
        and position >= back_matter
    ):
        return "back_matter"

    if (
        end is not None
        and position >= end
    ):
        return "back_matter"

    # -------------------------------------------------------
    # MAIN CONTENT
    # -------------------------------------------------------

    if main_content is not None:

        if position >= main_content:
            return "main_content"

    # -------------------------------------------------------
    # FALLBACK
    # -------------------------------------------------------

    # If we cannot determine the region,
    # preserve the block as main content rather
    # than silently deleting it.
    return "main_content"


# ---------------------------------------------------------------------------
# REGION CREATION
# ---------------------------------------------------------------------------

def create_empty_regions(
    source_file: str,
) -> Dict[str, dict]:
    """
    Create empty region containers.
    """

    return {
        region: {
            "source_file": source_file,
            "region": region,
            "pages": [],
        }
        for region in REGIONS
    }


def get_or_create_region_page(
    region: dict,
    page: dict,
):
    """
    Get the page representation for a region.

    A page can appear in more than one region if a
    structural boundary occurs in the middle of a page.
    """

    source_page = page.get(
        "source_page"
    )

    for region_page in region["pages"]:

        if (
            region_page["source_page"]
            == source_page
        ):
            return region_page

    region_page = {
        "source_page": source_page,
        "printed_page": page.get(
            "printed_page"
        ),
        "blocks": [],
    }

    region["pages"].append(
        region_page
    )

    return region_page


def add_block_to_region(
    region: dict,
    page: dict,
    block: dict,
) -> None:
    """
    Add a block to the appropriate region page.
    """

    region_page = get_or_create_region_page(
        region,
        page,
    )

    region_page["blocks"].append(
        block
    )


# ---------------------------------------------------------------------------
# MAIN SPLITTER
# ---------------------------------------------------------------------------

def split_document(
    document: dict,
) -> dict:
    """
    Split a parsed document into broad semantic regions.

    This is still deterministic.

    It does NOT:
        - identify individual chapters
        - repair OCR
        - rewrite text
        - remove running headers
        - build the final hierarchy

    Those jobs belong to later stages.
    """

    source_file = document.get(
        "source_file",
        "",
    )

    regions = create_empty_regions(
        source_file
    )

    anchors = find_structural_anchors(
        document
    )

    for (
        page_index,
        block_index,
        block,
    ) in iter_blocks(document):

        page = document[
            "pages"
        ][page_index]

        region_name = classify_position(
            page_index,
            block_index,
            anchors,
        )

        add_block_to_region(
            regions[region_name],
            page,
            block,
        )

    return {
        "source_file": source_file,
        "regions": regions,
        "anchors": anchors,
    }


# ---------------------------------------------------------------------------
# JSON INPUT / OUTPUT
# ---------------------------------------------------------------------------

def split_json(
    input_path: str | Path,
) -> dict:
    """
    Load parsed.json and split it.
    """

    input_path = Path(
        input_path
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"File not found: {input_path}"
        )

    document = json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
    )

    return split_document(
        document
    )


def save_split(
    split_data: dict,
    output_path: str | Path,
) -> None:
    """
    Save the split representation.
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
            split_data,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# DEBUGGING / SUMMARY
# ---------------------------------------------------------------------------

def count_blocks(
    region: dict,
) -> int:
    """
    Count blocks in a region.
    """

    return sum(
        len(
            page.get(
                "blocks",
                [],
            )
        )
        for page in region.get(
            "pages",
            [],
        )
    )


def print_anchor(
    name: str,
    anchor: Optional[dict],
) -> None:
    """
    Print one detected anchor.
    """

    if anchor is None:
        print(
            f"  {name:15}: NOT FOUND"
        )
        return

    print(
        f"  {name:15}: "
        f"page={anchor['source_page']} "
        f"block={anchor['block_id']} "
        f"text={anchor['text']!r}"
    )


def print_summary(
    split_data: dict,
) -> None:
    """
    Print the results of the split.
    """

    print(
        f"Source: "
        f"{split_data['source_file']}"
    )

    print()

    print("Detected anchors:")

    anchors = split_data[
        "anchors"
    ]

    print_anchor(
        "contents",
        anchors["contents"],
    )

    print_anchor(
        "main_content",
        anchors["main_content"],
    )

    print_anchor(
        "back_matter",
        anchors["back_matter"],
    )

    print_anchor(
        "end",
        anchors["end"],
    )

    print()

    print("Regions:")

    for (
        region_name,
        region,
    ) in split_data[
        "regions"
    ].items():

        page_count = len(
            region["pages"]
        )

        block_count = count_blocks(
            region
        )

        if page_count:

            source_pages = [
                page["source_page"]
                for page in region["pages"]
            ]

            page_range = (
                f"{min(source_pages)}"
                f"-"
                f"{max(source_pages)}"
            )

        else:

            page_range = "empty"

        print(
            f"  {region_name:15}"
            f" pages={page_count:3}"
            f" blocks={block_count:4}"
            f" source_pages={page_range}"
        )


# ---------------------------------------------------------------------------
# COMMAND LINE INTERFACE
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Split parsed Markdown JSON "
            "into generic document regions."
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
        help="Path to output split JSON",
    )

    args = parser.parse_args()

    split_data = split_json(
        args.input
    )

    save_split(
        split_data,
        args.output,
    )

    print_summary(
        split_data
    )

    print()

    print(
        f"Output: {args.output}"
    )
