import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


class RegionClassifier(Protocol):
    """
    Provider-neutral interface.

    Any AI provider can be used as long as it implements:

        classify(pages) -> result

    Expected result:

        {
            "region": "...",
            "confidence": 0.0,
            "reason": "..."
        }

    The implementation can use:
        Gemini
        OpenAI
        Ollama
        Qwen
        Claude
        local transformers
        anything else
    """

    def classify(
        self,
        pages: List[dict],
    ) -> Any:
        ...


# ============================================================
# TEXT HELPERS
# ============================================================

def normalize_text(
    text: str,
) -> str:
    """
    Normalize text for comparisons only.

    Original source text is never modified.
    """

    text = str(
        text or ""
    )

    text = text.replace(
        "\u00a0",
        " ",
    )

    text = re.sub(
        r"^#{1,6}\s*",
        "",
        text.strip(),
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip().lower()


def block_text(
    block: dict,
) -> str:
    return str(
        block.get(
            "text",
            "",
        )
    )


def page_text(
    page: dict,
) -> str:
    return "\n".join(
        block_text(block)
        for block in page.get(
            "blocks",
            [],
        )
    )


def is_heading(
    block: dict,
) -> bool:
    return (
        block.get(
            "block_type"
        ) == "heading"
        or block.get(
            "markdown_level"
        ) is not None
    )


def heading_text(
    block: dict,
) -> str:
    return normalize_text(
        block_text(block)
    )


# ============================================================
# GENERIC STRUCTURAL SIGNALS
# ============================================================

def looks_like_contents_heading(
    text: str,
) -> bool:

    text = normalize_text(
        text
    )

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
    )

    patterns = (
        r"^book\s+(?:[ivxlcdm]+|\d+)"
        r"(?:\s*[-–—:].*)?$",

        r"^part\s+(?:[ivxlcdm]+|\d+)"
        r"(?:\s*[-–—:].*)?$",

        r"^chapter\s+(?:[ivxlcdm]+|\d+)"
        r"(?:\s*[-–—:].*)?$",

        r"^section\s+(?:[ivxlcdm]+|\d+)"
        r"(?:\s*[-–—:].*)?$",
    )

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
    )

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
    )

    return text in {
        "the end",
        "end",
        "fin",
    }


# ============================================================
# ITERATION
# ============================================================

def iter_blocks(
    document: dict,
):
    """
    Iterate through all document blocks
    in source order.
    """

    for page_index, page in enumerate(
        document.get(
            "pages",
            [],
        )
    ):

        for block_index, block in enumerate(
            page.get(
                "blocks",
                [],
            )
        ):

            yield (
                page_index,
                block_index,
                block,
            )


# ============================================================
# STRUCTURAL ANCHORS
# ============================================================

def make_anchor(
    document: dict,
    page_index: int,
    block_index: int,
    block: dict,
    kind: str,
) -> dict:

    page = document[
        "pages"
    ][page_index]

    return {
        "kind": kind,
        "page_index": page_index,
        "block_index": block_index,
        "source_page": page.get(
            "source_page"
        ),
        "block_id": block.get(
            "id"
        ),
        "text": heading_text(
            block
        ),
        "markdown_level": block.get(
            "markdown_level"
        ),
    }


def find_structural_anchors(
    document: dict,
) -> Dict[str, List[dict]]:
    """
    Find possible structural signals.

    Multiple candidates are preserved.

    We do NOT assume that the first matching heading
    is necessarily the correct boundary.
    """

    anchors = {
        "contents": [],
        "main_content": [],
        "back_matter": [],
        "end": [],
    }

    for (
        page_index,
        block_index,
        block,
    ) in iter_blocks(
        document
    ):

        if not is_heading(
            block
        ):
            continue

        text = heading_text(
            block
        )

        if looks_like_contents_heading(
            text
        ):

            anchors[
                "contents"
            ].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "contents",
                )
            )

        if looks_like_main_content_heading(
            text
        ):

            anchors[
                "main_content"
            ].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "main_content",
                )
            )

        if looks_like_back_matter_heading(
            text
        ):

            anchors[
                "back_matter"
            ].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "back_matter",
                )
            )

        if looks_like_end_marker(
            text
        ):

            anchors[
                "end"
            ].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "end",
                )
            )

    return anchors


# ============================================================
# PAGE WINDOWS
# ============================================================

def create_page_windows(
    document: dict,
    window_size: int = 5,
    overlap: int = 2,
) -> List[List[dict]]:
    """
    Create overlapping page windows.

    Example:

        pages 1-5
        pages 4-8
        pages 7-11

    Overlap gives the classifier context around boundaries.
    """

    pages = document.get(
        "pages",
        [],
    )

    if not pages:
        return []

    if window_size <= 0:
        raise ValueError(
            "window_size must be greater than zero."
        )

    if overlap < 0:
        raise ValueError(
            "overlap cannot be negative."
        )

    if overlap >= window_size:
        raise ValueError(
            "overlap must be smaller than window_size."
        )

    step = (
        window_size
        - overlap
    )

    windows = []

    start = 0

    while start < len(pages):

        window = pages[
            start:start + window_size
        ]

        if not window:
            break

        windows.append(
            window
        )

        if (
            start
            + window_size
            >= len(pages)
        ):
            break

        start += step

    return windows


# ============================================================
# AI RESULT HELPERS
# ============================================================

def extract_region(
    result: Any,
) -> Optional[str]:

    if result is None:
        return None

    if isinstance(
        result,
        dict,
    ):

        region = result.get(
            "region"
        )

    else:

        region = getattr(
            result,
            "region",
            None,
        )

    if region not in REGIONS:
        return None

    return region


def extract_confidence(
    result: Any,
) -> float:

    if result is None:
        return 0.0

    if isinstance(
        result,
        dict,
    ):

        value = result.get(
            "confidence",
            0.0,
        )

    else:

        value = getattr(
            result,
            "confidence",
            0.0,
        )

    try:

        value = float(
            value
        )

    except (
        TypeError,
        ValueError,
    ):

        value = 0.0

    return max(
        0.0,
        min(
            1.0,
            value,
        ),
    )


def extract_reason(
    result: Any,
) -> str:

    if result is None:
        return ""

    if isinstance(
        result,
        dict,
    ):

        return str(
            result.get(
                "reason",
                "",
            )
        )

    return str(
        getattr(
            result,
            "reason",
            "",
        )
    )


# ============================================================
# AI CLASSIFICATION
# ============================================================

def classify_window(
    ai_agent: RegionClassifier,
    pages: List[dict],
) -> Optional[dict]:
    """
    Call the injected AI classifier.

    The splitter has no knowledge of the provider.
    """

    result = ai_agent.classify(
        pages
    )

    region = extract_region(
        result
    )

    if region is None:
        return None

    return {
        "region": region,
        "confidence": extract_confidence(
            result
        ),
        "reason": extract_reason(
            result
        ),
    }


def classify_pages_with_ai(
    document: dict,
    ai_agent: RegionClassifier,
    window_size: int = 5,
    overlap: int = 2,
) -> Dict[int, List[dict]]:
    """
    Classify overlapping page windows.

    Each page may receive multiple predictions.
    """

    windows = create_page_windows(
        document=document,
        window_size=window_size,
        overlap=overlap,
    )

    predictions: Dict[
        int,
        List[dict],
    ] = {}

    total = len(
        windows
    )

    for (
        window_number,
        pages,
    ) in enumerate(
        windows,
        start=1,
    ):

        first_page = pages[
            0
        ].get(
            "source_page"
        )

        last_page = pages[
            -1
        ].get(
            "source_page"
        )

        print(
            f"AI window "
            f"{window_number}/{total}: "
            f"pages "
            f"{first_page}-"
            f"{last_page}"
        )

        try:

            result = classify_window(
                ai_agent,
                pages,
            )

        except Exception as exc:

            print(
                f"  AI error: {exc}"
            )

            continue

        if result is None:

            print(
                "  Invalid AI result."
            )

            continue

        print(
            f"  -> "
            f"{result['region']} "
            f"("
            f"{result['confidence']:.2f}"
            f")"
        )

        for page in pages:

            source_page = page.get(
                "source_page"
            )

            predictions.setdefault(
                source_page,
                [],
            ).append(
                {
                    **result,
                    "window_start": first_page,
                    "window_end": last_page,
                }
            )

    return predictions


# ============================================================
# RECONCILIATION
# ============================================================

def choose_region(
    predictions: List[dict],
) -> str:
    """
    Confidence-weighted vote among overlapping
    AI predictions.
    """

    if not predictions:
        return "main_content"

    scores = {
        region: 0.0
        for region in REGIONS
    }

    for prediction in predictions:

        region = prediction.get(
            "region"
        )

        if region not in scores:
            continue

        confidence = float(
            prediction.get(
                "confidence",
                0.0,
            )
        )

        scores[
            region
        ] += max(
            0.0,
            confidence,
        )

    return max(
        scores,
        key=scores.get,
    )


def deterministic_region(
    source_page: int,
    anchors: Dict[str, List[dict]],
) -> str:
    """
    Fallback when no AI prediction exists.
    """

    contents = [
        item["source_page"]
        for item in anchors[
            "contents"
        ]
    ]

    main = [
        item["source_page"]
        for item in anchors[
            "main_content"
        ]
    ]

    back = [
        item["source_page"]
        for item in anchors[
            "back_matter"
        ]
    ]

    ends = [
        item["source_page"]
        for item in anchors[
            "end"
        ]
    ]

    contents_start = (
        min(contents)
        if contents
        else None
    )

    main_start = (
        min(main)
        if main
        else None
    )

    back_start = (
        min(back)
        if back
        else None
    )

    end_page = (
        min(ends)
        if ends
        else None
    )

    if (
        contents_start is not None
        and source_page < contents_start
    ):

        return "front_matter"

    if (
        contents_start is not None
        and main_start is not None
        and contents_start
        <= source_page
        < main_start
    ):

        return "contents"

    if (
        back_start is not None
        and source_page >= back_start
    ):

        return "back_matter"

    if (
        end_page is not None
        and source_page > end_page
    ):

        return "back_matter"

    if (
        main_start is not None
        and source_page >= main_start
    ):

        return "main_content"

    return "main_content"


def reconcile_page_regions(
    document: dict,
    predictions: Dict[int, List[dict]],
) -> Dict[int, str]:
    """
    Produce exactly one region assignment per page.
    """

    anchors = find_structural_anchors(
        document
    )

    result = {}

    for page in document.get(
        "pages",
        [],
    ):

        source_page = page.get(
            "source_page"
        )

        page_predictions = predictions.get(
            source_page,
            [],
        )

        if page_predictions:

            result[
                source_page
            ] = choose_region(
                page_predictions
            )

        else:

            result[
                source_page
            ] = deterministic_region(
                source_page,
                anchors,
            )

    return result


def smooth_page_regions(
    page_regions: Dict[int, str],
) -> Dict[int, str]:
    """
    Remove isolated A-B-A classification spikes.

    This is intentionally conservative.
    """

    pages = sorted(
        page_regions
    )

    result = dict(
        page_regions
    )

    if len(pages) < 3:
        return result

    for index in range(
        1,
        len(pages) - 1,
    ):

        previous_page = pages[
            index - 1
        ]

        current_page = pages[
            index
        ]

        next_page = pages[
            index + 1
        ]

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
            previous_region
            == next_region
            and current_region
            != previous_region
        ):

            result[
                current_page
            ] = previous_region

    return result


# ============================================================
# REGION ASSEMBLY
# ============================================================

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


def add_page_to_region(
    region: dict,
    page: dict,
) -> None:
    """
    Preserve the original page and all its blocks.
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


# ============================================================
# PUBLIC API
# ============================================================

def split_document(
    document: dict,
    ai_agent: Optional[
        RegionClassifier
    ] = None,
    use_ai: bool = True,
    window_size: int = 5,
    overlap: int = 2,
) -> dict:
    """
    Split a parsed document into broad semantic regions.

    AI is optional and injected.

    This function has no dependency on a concrete AI provider.
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

    page_predictions = {}

    if (
        use_ai
        and ai_agent is not None
    ):

        page_predictions = (
            classify_pages_with_ai(
                document=document,
                ai_agent=ai_agent,
                window_size=window_size,
                overlap=overlap,
            )
        )

    page_regions = (
        reconcile_page_regions(
            document=document,
            predictions=page_predictions,
        )
    )

    if (
        use_ai
        and ai_agent is not None
    ):

        page_regions = smooth_page_regions(
            page_regions
        )

    for page in document.get(
        "pages",
        [],
    ):

        source_page = page.get(
            "source_page"
        )

        region_name = page_regions.get(
            source_page,
            "main_content",
        )

        add_page_to_region(
            regions[
                region_name
            ],
            page,
        )

    return {
        "source_file": source_file,
        "regions": regions,
        "anchors": anchors,
        "page_regions": page_regions,
        "ai": {
            "enabled": bool(
                use_ai
                and ai_agent is not None
            ),
            "provider": (
                type(
                    ai_agent
                ).__name__
                if ai_agent is not None
                else None
            ),
            "window_size": window_size,
            "overlap": overlap,
        },
    }


# ============================================================
# FILE HELPERS
# ============================================================

def load_document(
    input_path: str | Path,
) -> dict:

    input_path = Path(
        input_path
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"File not found: {input_path}"
        )

    return json.loads(
        input_path.read_text(
            encoding="utf-8"
        )
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


# ============================================================
# SUMMARY
# ============================================================

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
        "Structural candidates:"
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

        candidates = anchors[
            name
        ]

        if not candidates:

            print(
                f"  {name:15}: NONE"
            )

            continue

        preview = candidates[
            :3
        ]

        values = "; ".join(
            (
                f"page={item['source_page']} "
                f"block={item['block_id']} "
                f"text={item['text']!r}"
            )
            for item in preview
        )

        if len(candidates) > 3:

            values += (
                f" ... +"
                f"{len(candidates) - 3}"
                f" more"
            )

        print(
            f"  {name:15}: "
            f"{values}"
        )

    print()
    print(
        "AI:"
    )

    ai = split_data[
        "ai"
    ]

    print(
        f"  enabled: "
        f"{ai['enabled']}"
    )

    print(
        f"  provider: "
        f"{ai['provider']}"
    )

    print(
        f"  window_size: "
        f"{ai['window_size']}"
    )

    print(
        f"  overlap: "
        f"{ai['overlap']}"
    )

    print()
    print(
        "Final regions:"
    )

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

            page_range = (
                f"{min(source_pages)}-"
                f"{max(source_pages)}"
            )

        else:

            page_range = "empty"

        print(
            f"  {region_name:15} "
            f"pages={len(pages):3} "
            f"blocks={block_count:4} "
            f"source_pages={page_range}"
        )


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=(
            "Split parsed Document AI Markdown "
            "into broad semantic regions."
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
        help="Output split JSON.",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help=(
            "Disable AI and use deterministic "
            "fallback classification."
        ),
    )

    args = parser.parse_args()

    document = load_document(
        args.input
    )

    # The command-line interface intentionally does not
    # instantiate any particular AI provider.
    #
    # Provider-specific code belongs outside this module.
    result = split_document(
        document=document,
        ai_agent=None,
        use_ai=True,
    )

    save_split(
        result,
        args.output,
    )

    print_summary(
        result
    )

    print(
        f"\nOutput: {args.output}"
    )