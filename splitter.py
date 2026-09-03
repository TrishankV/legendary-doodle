import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .region_agent import (
    RegionAgent,
    RegionPrediction,
)


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


# =====================================================================
# TEXT NORMALIZATION
# =====================================================================

def normalize_text(text: str) -> str:
    """
    Normalize text for comparison only.

    Original block text is never changed.
    """

    text = text.strip()

    text = re.sub(
        r"^#{1,6}\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


# =====================================================================
# BLOCK HELPERS
# =====================================================================

def is_heading(block: dict) -> bool:
    return block.get(
        "block_type"
    ) == "heading"


def heading_text(block: dict) -> str:
    return normalize_text(
        block.get("text", "")
    )


def block_text(block: dict) -> str:
    return normalize_text(
        block.get("text", "")
    )


# =====================================================================
# DETERMINISTIC DETECTION
# =====================================================================

def looks_like_contents_heading(
    text: str,
) -> bool:

    text = normalize_text(
        text
    ).lower()

    return text in {
        "contents",
        "table of contents",
        "contents page",
        "table contents",
    }


def looks_like_main_content_heading(
    text: str,
) -> bool:

    text = normalize_text(
        text
    ).lower()

    patterns = [
        r"^book\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)(\s*[-–—:].*)?$",
        r"^part\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)(\s*[-–—:].*)?$",
        r"^chapter\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)(\s*[-–—:].*)?$",
        r"^chapter\s+\d+(\s*[-–—:].*)?$",
        r"^section\s+(i|ii|iii|iv|v|vi|vii|viii|ix|x|\d+)(\s*[-–—:].*)?$",
    ]

    return any(
        re.match(
            pattern,
            text,
        )
        for pattern in patterns
    )


def looks_like_back_matter_heading(
    text: str,
) -> bool:

    text = normalize_text(
        text
    ).lower()

    return text in {
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


def looks_like_end_marker(
    text: str,
) -> bool:

    text = normalize_text(
        text
    ).lower()

    return text in {
        "the end",
        "end",
        "fin",
    }


# =====================================================================
# ITERATION
# =====================================================================

def iter_blocks(document: dict):

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


# =====================================================================
# DETERMINISTIC ANCHORS
# =====================================================================

def find_structural_anchors(
    document: dict,
) -> Dict[str, Optional[dict]]:

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

        text = heading_text(
            block
        )

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

        if (
            anchors["contents"] is None
            and looks_like_contents_heading(text)
        ):
            anchors["contents"] = position
            continue

        if (
            anchors["main_content"] is None
            and looks_like_main_content_heading(text)
        ):
            anchors["main_content"] = position
            continue

        if (
            anchors["back_matter"] is None
            and looks_like_back_matter_heading(text)
        ):
            anchors["back_matter"] = position
            continue

        if (
            anchors["end"] is None
            and looks_like_end_marker(text)
        ):
            anchors["end"] = position

    return anchors


# =====================================================================
# POSITION
# =====================================================================

def position_of(
    page_index: int,
    block_index: int,
) -> Tuple[int, int]:

    return (
        page_index,
        block_index,
    )


def anchor_position(
    anchor: Optional[dict],
):

    if anchor is None:
        return None

    return (
        anchor["page_index"],
        anchor["block_index"],
    )


# =====================================================================
# AI CHUNKING
# =====================================================================

def create_page_windows(
    document: dict,
    window_size: int = 5,
    overlap: int = 1,
) -> List[List[dict]]:
    """
    Create overlapping page windows.

    Example:

        pages 1-5
        pages 5-9
        pages 9-13
        ...

    This gives the model surrounding context without
    sending the entire book.
    """

    pages = document.get(
        "pages",
        [],
    )

    if not pages:
        return []

    if window_size <= 0:
        raise ValueError(
            "window_size must be > 0"
        )

    if overlap >= window_size:
        raise ValueError(
            "overlap must be smaller than window_size"
        )

    step = window_size - overlap

    windows = []

    for start in range(
        0,
        len(pages),
        step,
    ):

        window = pages[
            start:start + window_size
        ]

        if window:
            windows.append(
                window
            )

        if start + window_size >= len(
            pages
        ):
            break

    return windows


# =====================================================================
# AI PAGE CLASSIFICATION
# =====================================================================

def classify_pages_with_ai(
    document: dict,
    agent: RegionAgent,
    window_size: int = 5,
    overlap: int = 1,
) -> Dict[int, List[RegionPrediction]]:
    """
    Classify page windows with the local model.

    Returns:

        {
            source_page: [
                prediction,
                prediction,
            ]
        }

    Because windows overlap, a page can receive
    multiple predictions.
    """

    predictions = {}

    windows = create_page_windows(
        document,
        window_size=window_size,
        overlap=overlap,
    )

    total = len(windows)

    for index, pages in enumerate(
        windows,
        start=1,
    ):

        first_page = pages[0][
            "source_page"
        ]

        last_page = pages[-1][
            "source_page"
        ]

        print(
            f"AI window "
            f"{index}/{total}: "
            f"pages {first_page}-{last_page}"
        )

        prediction = agent.analyze(
            pages
        )

        print(
            f"  -> {prediction.region} "
            f"({prediction.confidence:.2f})"
        )

        for page in pages:

            source_page = page[
                "source_page"
            ]

            predictions.setdefault(
                source_page,
                [],
            ).append(
                prediction
            )

    return predictions


# =====================================================================
# AI RECONCILIATION
# =====================================================================

def choose_page_region(
    predictions: List[RegionPrediction],
) -> str:
    """
    Choose the region for a page from overlapping
    AI predictions.

    Weighted voting is used:

        vote = confidence

    """

    if not predictions:
        return "main_content"

    scores = {
        region: 0.0
        for region in REGIONS
    }

    for prediction in predictions:

        scores[
            prediction.region
        ] += prediction.confidence

    return max(
        scores,
        key=scores.get,
    )


def ai_page_regions(
    document: dict,
    predictions: Dict[
        int,
        List[RegionPrediction],
    ],
) -> Dict[int, str]:
    """
    Convert overlapping predictions into
    one region per source page.
    """

    result = {}

    for page in document.get(
        "pages",
        [],
    ):

        source_page = page[
            "source_page"
        ]

        result[source_page] = (
            choose_page_region(
                predictions.get(
                    source_page,
                    [],
                )
            )
        )

    return result


# =====================================================================
# SMOOTH PAGE REGIONS
# =====================================================================

def smooth_regions(
    page_regions: Dict[int, str],
) -> Dict[int, str]:
    """
    Prevent isolated one-page AI mistakes.

    Example:

        main
        main
        back
        main
        main

    becomes:

        main
        main
        main
        main
        main

    Only very small isolated runs are corrected.
    """

    pages = sorted(
        page_regions.keys()
    )

    if len(pages) < 3:
        return page_regions

    result = dict(
        page_regions
    )

    for i in range(
        1,
        len(pages) - 1,
    ):

        previous_page = pages[i - 1]
        current_page = pages[i]
        next_page = pages[i + 1]

        previous_region = result[
            previous_page
        ]

        current_region = result[
            current_page
        ]

        next_region = result[
            next_page
        ]

        if (
            previous_region == next_region
            and current_region != previous_region
        ):
            result[
                current_page
            ] = previous_region

    return result


# =====================================================================
# REGION CREATION
# =====================================================================

def create_empty_regions(
    source_file: str,
) -> Dict[str, dict]:

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

    source_page = page.get(
        "source_page"
    )

    for region_page in region[
        "pages"
    ]:

        if (
            region_page[
                "source_page"
            ]
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

    region[
        "pages"
    ].append(
        region_page
    )

    return region_page


def add_block_to_region(
    region: dict,
    page: dict,
    block: dict,
) -> None:

    region_page = (
        get_or_create_region_page(
            region,
            page,
        )
    )

    region_page[
        "blocks"
    ].append(
        block
    )


# =====================================================================
# MAIN AI SPLITTER
# =====================================================================

def split_document(
    document: dict,
    use_ai: bool = True,
    model: str = "qwen3:4b",
    window_size: int = 5,
    overlap: int = 1,
) -> dict:
    """
    Split document into broad semantic regions.

    Deterministic anchors are used first.

    AI is then used to classify page windows.

    The original blocks are never modified.
    """

    source_file = document.get(
        "source_file",
        "",
    )

    regions = create_empty_regions(
        source_file
    )

    # -------------------------------------------------------------
    # Deterministic anchors
    # -------------------------------------------------------------

    anchors = (
        find_structural_anchors(
            document
        )
    )

    # -------------------------------------------------------------
    # AI page classification
    # -------------------------------------------------------------

    ai_regions = {}

    if use_ai:

        agent = RegionAgent(
            model=model
        )

        predictions = (
            classify_pages_with_ai(
                document=document,
                agent=agent,
                window_size=window_size,
                overlap=overlap,
            )
        )

        ai_regions = (
            ai_page_regions(
                document,
                predictions,
            )
        )

        ai_regions = (
            smooth_regions(
                ai_regions
            )
        )

    # -------------------------------------------------------------
    # Assign blocks
    # -------------------------------------------------------------

    for (
        page_index,
        block_index,
        block,
    ) in iter_blocks(document):

        page = document[
            "pages"
        ][page_index]

        source_page = page[
            "source_page"
        ]

        # ---------------------------------------------------------
        # AI decision
        # ---------------------------------------------------------

        if use_ai and source_page in ai_regions:

            region_name = ai_regions[
                source_page
            ]

        # ---------------------------------------------------------
        # Deterministic fallback
        # ---------------------------------------------------------

        else:

            region_name = (
                classify_position(
                    page_index,
                    block_index,
                    anchors,
                )
            )

        add_block_to_region(
            regions[
                region_name
            ],
            page,
            block,
        )

    return {
        "source_file": source_file,

        "regions": regions,

        "anchors": anchors,

        "ai": {
            "enabled": use_ai,
            "model": model,
            "window_size": window_size,
            "overlap": overlap,
            "page_regions": ai_regions,
        },
    }


# =====================================================================
# DETERMINISTIC FALLBACK CLASSIFIER
# =====================================================================

def classify_position(
    page_index: int,
    block_index: int,
    anchors: Dict[
        str,
        Optional[dict],
    ],
) -> str:

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

    if (
        contents is not None
        and position < contents
    ):
        return "front_matter"

    if (
        contents is None
        and main_content is not None
        and position < main_content
    ):
        return "front_matter"

    if contents is not None:

        if (
            main_content is not None
            and contents <= position < main_content
        ):
            return "contents"

        if (
            main_content is None
            and back_matter is not None
            and contents <= position < back_matter
        ):
            return "contents"

        if (
            main_content is None
            and end is not None
            and contents <= position < end
        ):
            return "contents"

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

    if (
        main_content is not None
        and position >= main_content
    ):
        return "main_content"

    return "main_content"


# =====================================================================
# JSON
# =====================================================================

def split_json(
    input_path: str | Path,
    **kwargs,
) -> dict:

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
        document,
        **kwargs,
    )


def save_split(
    split_data: dict,
    output_path: str | Path,
) -> None:

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


# =====================================================================
# SUMMARY
# =====================================================================

def count_blocks(
    region: dict,
) -> int:

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

    print()
    print(
        f"Source: "
        f"{split_data['source_file']}"
    )

    print()
    print(
        "Detected deterministic anchors:"
    )

    anchors = split_data[
        "anchors"
    ]

    for name in (
        "contents",
        "main_content",
        "back_matter",
        "end",
    ):

        anchor = anchors[
            name
        ]

        if anchor is None:

            print(
                f"  {name:15}: NOT FOUND"
            )

        else:

            print(
                f"  {name:15}: "
                f"page={anchor['source_page']} "
                f"block={anchor['block_id']} "
                f"text={anchor['text']!r}"
            )

    print()

    print(
        "AI classification:"
    )

    ai_data = split_data.get(
        "ai",
        {},
    )

    print(
        f"  enabled: "
        f"{ai_data.get('enabled')}"
    )

    print(
        f"  model: "
        f"{ai_data.get('model')}"
    )

    print()

    print("Regions:")

    for (
        region_name,
        region,
    ) in split_data[
        "regions"
    ].items():

        pages = region[
            "pages"
        ]

        block_count = count_blocks(
            region
        )

        if pages:

            source_pages = [
                page[
                    "source_page"
                ]
                for page in pages
            ]

            print(
                f"  {region_name:15} "
                f"pages={len(pages)} "
                f"blocks={block_count} "
                f"source_pages="
                f"{min(source_pages)}-"
                f"{max(source_pages)}"
            )

        else:

            print(
                f"  {region_name:15} "
                f"pages=0 "
                f"blocks=0"
            )


# =====================================================================
# CLI
# =====================================================================

def main():

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Split parsed Markdown into "
            "semantic regions using a "
            "local AI model."
        )
    )

    parser.add_argument(
        "input",
        help="Path to parsed.json",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="split.json",
        help="Output JSON path",
    )

    parser.add_argument(
        "--model",
        default="qwen3:4b",
        help="Ollama model",
    )

    parser.add_argument(
        "--window-size",
        type=int,
        default=5,
        help="Pages per AI window",
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=1,
        help="Overlapping pages",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI and use deterministic splitting",
    )

    args = parser.parse_args()

    split_data = split_json(
        args.input,
        use_ai=not args.no_ai,
        model=args.model,
        window_size=args.window_size,
        overlap=args.overlap,
    )

    save_split(
        split_data,
        args.output,
    )

    print_summary(
        split_data
    )


if __name__ == "__main__":
    main()
