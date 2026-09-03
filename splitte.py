import json
from pathlib import Path
from typing import Dict, List


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


def normalize_text(text: str) -> str:
    """
    Normalize text for structural analysis.

    This function never modifies the original block.
    """

    text = text.strip()

    # Remove Markdown heading markers.
    text = text.lstrip("#")

    # Normalize whitespace.
    text = " ".join(text.split())

    return text.strip()


def is_heading(block: dict) -> bool:
    """
    Check whether a block was classified as a heading
    by the parser.
    """

    return block.get("block_type") == "heading"


def get_heading_text(block: dict) -> str:
    """
    Return normalized heading text for analysis.
    """

    return normalize_text(
        block.get("text", "")
    )


def iter_blocks(document: dict):
    """
    Iterate through every block in source order.

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


def find_structural_anchors(
    document: dict,
) -> List[dict]:
    """
    Find headings that may represent structural
    boundaries within the document.

    This function does not decide what the headings mean.
    It only records them for later stages.
    """

    anchors = []

    for (
        page_index,
        block_index,
        block,
    ) in iter_blocks(document):

        if not is_heading(block):
            continue

        page = document["pages"][page_index]

        anchors.append(
            {
                "position": [
                    page_index,
                    block_index,
                ],
                "source_page": page.get(
                    "source_page"
                ),
                "block_id": block.get(
                    "id"
                ),
                "text": get_heading_text(
                    block
                ),
                "markdown_level": block.get(
                    "markdown_level"
                ),
            }
        )

    return anchors


def create_empty_regions(
    source_file: str,
) -> Dict[str, dict]:
    """
    Create the broad document regions.

    They are initially empty because semantic
    region detection happens in a later stage.
    """

    return {
        region: {
            "source_file": source_file,
            "region": region,
            "pages": [],
        }
        for region in REGIONS
    }


def add_page_to_region(
    region: dict,
    page: dict,
) -> None:
    """
    Add a page while preserving its original
    source-page information and blocks.
    """

    region["pages"].append(
        {
            "source_page": page.get(
                "source_page"
            ),
            "printed_page": page.get(
                "printed_page"
            ),
            "blocks": page.get(
                "blocks",
                [],
            ),
        }
    )


def split_document(
    document: dict,
) -> dict:
    """
    Create the generic structural representation
    of a parsed document.

    The splitter deliberately does not make
    document-specific assumptions.

    It:
        1. Preserves all pages and blocks.
        2. Finds structural heading candidates.
        3. Creates broad region containers.
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

    # Until semantic region detection is performed,
    # preserve the complete document under main_content.
    for page in document.get(
        "pages",
        [],
    ):

        add_page_to_region(
            regions["main_content"],
            page,
        )

    return {
        "source_file": source_file,
        "regions": regions,
        "anchors": anchors,
    }


def split_json(
    input_path: str | Path,
) -> dict:
    """
    Load parsed JSON and create the split representation.
    """

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

    return split_document(
        document
    )


def save_split(
    split_data: dict,
    output_path: str | Path,
) -> None:
    """
    Save the split representation to JSON.
    """

    output_path = Path(output_path)

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


def count_blocks(
    region: dict,
) -> int:
    """
    Count all blocks inside a region.
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


def print_summary(
    split_data: dict,
) -> None:
    """
    Print a summary of the generated structure.
    """

    print(
        f"Source: "
        f"{split_data['source_file']}"
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

    print()

    print(
        "Structural anchors: "
        f"{len(split_data['anchors'])}"
    )


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Create a generic structural "
            "representation from parsed "
            "Document AI Markdown JSON."
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
        help="Path for the output JSON",
    )

    args = parser.parse_args()

    split_data = split_json(
        args.input
    )

    save_split(
        split_data,
        args.output
    )

    print_summary(
        split_data
    )

    print(
        f"\nOutput: {args.output}"
    )
