from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, Sequence


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)

UNKNOWN = "unknown"

# ---------------------------------------------------------------------------
# AI interface
# ---------------------------------------------------------------------------


class BoundaryClassifier(Protocol):
    """
    Provider-neutral interface for resolving uncertain document boundaries.

    The classifier receives a small amount of context around a candidate
    boundary and returns:

        {
            "decision": "boundary" | "no_boundary",
            "transition": "front_matter_to_contents"
                         | "contents_to_main_content"
                         | "main_content_to_back_matter"
                         | "none",
            "confidence": 0.0,
            "reason": "..."
        }
    """

    def classify_boundary(
        self,
        before_pages: List[dict],
        after_pages: List[dict],
        expected_transition: str,
    ) -> Any:
        ...


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def normalize_text(text: str) -> str:
    """
    Normalize text for structural comparisons only.

    The original source text is never modified.
    """
    text = str(text or "")
    text = text.replace("\u00a0", " ")

    # Remove markdown heading markers.
    text = re.sub(
        r"^#{1,6}\s*",
        "",
        text.strip(),
    )

    # Normalize whitespace.
    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip().lower()


def block_text(block: dict) -> str:
    return str(block.get("text", "") or "")


def page_text(page: dict) -> str:
    return "\n".join(
        block_text(block)
        for block in page.get("blocks", [])
    )


def is_heading(block: dict) -> bool:
    return (
        block.get("block_type") == "heading"
        or block.get("markdown_level") is not None
    )


def heading_text(block: dict) -> str:
    return normalize_text(
        block_text(block)
    )


def compact_text(text: str, max_chars: int = 1000) -> str:
    """
    Compact text before sending it to an AI provider.

    This prevents accidental token explosions when a page contains a very
    large paragraph, table, or OCR artifact.
    """
    text = str(text or "").strip()

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n[TRUNCATED]"


# ---------------------------------------------------------------------------
# Structural signals
# ---------------------------------------------------------------------------


def looks_like_contents_heading(text: str) -> bool:
    text = normalize_text(text)

    return text in {
        "contents",
        "table of contents",
        "contents page",
        "table contents",
        "contents and index",
    }


def looks_like_main_content_heading(text: str) -> bool:
    text = normalize_text(text)

    patterns = (
        r"^book\s+(?:[ivxlcdm]+|\d+)(?:\s*[-–—:].*)?$",
        r"^part\s+(?:[ivxlcdm]+|\d+)(?:\s*[-–—:].*)?$",
        r"^chapter\s+(?:[ivxlcdm]+|\d+)(?:\s*[-–—:].*)?$",
        r"^section\s+(?:[ivxlcdm]+|\d+)(?:\s*[-–—:].*)?$",
        r"^prologue$",
        r"^introduction$",
    )

    return any(
        re.match(pattern, text)
        for pattern in patterns
    )


def looks_like_back_matter_heading(text: str) -> bool:
    text = normalize_text(text)

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
        "about the author",
        "author's note",
        "authors note",
        "publisher's note",
        "publishers note",
        "advertisements",
        "advertisements",
    }


def looks_like_end_marker(text: str) -> bool:
    text = normalize_text(text)

    return text in {
        "the end",
        "end",
        "fin",
    }


# ---------------------------------------------------------------------------
# Contents heuristics
# ---------------------------------------------------------------------------


def looks_like_toc_entry(text: str) -> bool:
    """
    Detect common table-of-contents entries.

    This is deliberately conservative. It is evidence, not a final decision.
    """
    text = str(text or "").strip()

    if not text:
        return False

    patterns = (
        # Chapter I ........ 12
        r"^(?:chapter|part|book|section)\s+.+\.{2,}\s*\d+\s*$",

        # Chapter I    12
        r"^(?:chapter|part|book|section)\s+.+\s{2,}\d+\s*$",

        # I. Something ........ 12
        r"^[ivxlcdm]+\.\s+.+\.{2,}\s*\d+\s*$",

        # 1. Something ........ 12
        r"^\d+\.\s+.+\.{2,}\s*\d+\s*$",
    )

    return any(
        re.match(pattern, text, flags=re.IGNORECASE)
        for pattern in patterns
    )


def page_has_contents_signals(page: dict) -> bool:
    """
    Return True when a page contains strong TOC evidence.
    """
    blocks = page.get("blocks", [])

    heading_found = False
    entry_count = 0

    for block in blocks:
        text = block_text(block).strip()

        if is_heading(block) and looks_like_contents_heading(text):
            heading_found = True

        if looks_like_toc_entry(text):
            entry_count += 1

    # A contents heading is strong evidence by itself.
    if heading_found:
        return True

    # Multiple TOC-looking entries are stronger than a single accidental one.
    return entry_count >= 2


# ---------------------------------------------------------------------------
# Document iteration
# ---------------------------------------------------------------------------


def iter_blocks(document: dict):
    """
    Iterate over all blocks in source order.
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
# Structural anchors
# ---------------------------------------------------------------------------


def make_anchor(
    document: dict,
    page_index: int,
    block_index: int,
    block: dict,
    kind: str,
) -> dict:
    page = document["pages"][page_index]

    return {
        "kind": kind,
        "page_index": page_index,
        "block_index": block_index,
        "source_page": page.get("source_page"),
        "block_id": block.get("id"),
        "text": heading_text(block),
        "markdown_level": block.get("markdown_level"),
    }


def find_structural_anchors(
    document: dict,
) -> Dict[str, List[dict]]:
    """
    Find possible structural signals.

    Multiple candidates are preserved. No candidate is blindly treated as
    authoritative.
    """
    anchors: Dict[str, List[dict]] = {
        "contents": [],
        "main_content": [],
        "back_matter": [],
        "end": [],
    }

    for (
        page_index,
        block_index,
        block,
    ) in iter_blocks(document):

        if not is_heading(block):
            continue

        text = heading_text(block)

        if looks_like_contents_heading(text):
            anchors["contents"].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "contents",
                )
            )

        if looks_like_main_content_heading(text):
            anchors["main_content"].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "main_content",
                )
            )

        if looks_like_back_matter_heading(text):
            anchors["back_matter"].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "back_matter",
                )
            )

        if looks_like_end_marker(text):
            anchors["end"].append(
                make_anchor(
                    document,
                    page_index,
                    block_index,
                    block,
                    "end",
                )
            )

    return anchors


# ---------------------------------------------------------------------------
# Page evidence
# ---------------------------------------------------------------------------


def page_signal_score(page: dict) -> Dict[str, float]:
    """
    Produce cheap deterministic evidence for a page.

    This does NOT assign the final region. It merely estimates which regions
    the page resembles.
    """
    scores = {
        "front_matter": 0.0,
        "contents": 0.0,
        "main_content": 0.0,
        "back_matter": 0.0,
    }

    blocks = page.get("blocks", [])

    if not blocks:
        return scores

    texts = [
        block_text(block).strip()
        for block in blocks
        if block_text(block).strip()
    ]

    normalized = [
        normalize_text(text)
        for text in texts
    ]

    # Contents evidence.
    if any(
        looks_like_contents_heading(text)
        for text in normalized
    ):
        scores["contents"] += 10.0

    toc_entries = sum(
        1
        for text in texts
        if looks_like_toc_entry(text)
    )

    scores["contents"] += min(
        toc_entries * 2.0,
        8.0,
    )

    # Main-content evidence.
    for block in blocks:
        if not is_heading(block):
            continue

        text = heading_text(block)

        if looks_like_main_content_heading(text):
            scores["main_content"] += 8.0

    # Back-matter evidence.
    for block in blocks:
        if not is_heading(block):
            continue

        text = heading_text(block)

        if looks_like_back_matter_heading(text):
            scores["back_matter"] += 10.0

        if looks_like_end_marker(text):
            scores["back_matter"] += 6.0

    # Front matter evidence is intentionally weaker. Anything before the
    # primary content can be front matter, but we do not want to misclassify
    # arbitrary pages simply because they appear early.
    for text in normalized:
        if text in {
            "title page",
            "copyright",
            "copyright page",
            "dedication",
            "dedications",
            "preface",
            "foreword",
            "acknowledgements",
            "acknowledgments",
        }:
            scores["front_matter"] += 7.0

    return scores


def page_has_strong_signal(page: dict) -> bool:
    scores = page_signal_score(page)

    return max(scores.values(), default=0.0) >= 8.0


# ---------------------------------------------------------------------------
# Boundary candidates
# ---------------------------------------------------------------------------


BOUNDARY_TRANSITIONS = (
    "front_matter_to_contents",
    "contents_to_main_content",
    "main_content_to_back_matter",
)


def make_boundary_candidate(
    page_index: int,
    source_page: int,
    transition: str,
    score: float,
    reason: str,
) -> dict:
    return {
        "page_index": page_index,
        "source_page": source_page,
        "transition": transition,
        "score": round(score, 3),
        "reason": reason,
    }


def detect_boundary_candidates(
    document: dict,
    anchors: Dict[str, List[dict]],
) -> List[dict]:
    """
    Generate likely boundary locations without using AI.

    The returned page index represents the FIRST page of the region AFTER
    the boundary.

    Example:

        contents_to_main_content at page_index=14

    means page 14 is the first page believed to belong to main_content.
    """
    pages = document.get("pages", [])

    if not pages:
        return []

    candidates: List[dict] = []

    contents_pages = {
        anchor.get("page_index")
        for anchor in anchors["contents"]
    }

    main_pages = {
        anchor.get("page_index")
        for anchor in anchors["main_content"]
    }

    back_pages = {
        anchor.get("page_index")
        for anchor in anchors["back_matter"]
    }

    end_pages = {
        anchor.get("page_index")
        for anchor in anchors["end"]
    }

    # -----------------------------------------------------------------------
    # Contents -> Main
    # -----------------------------------------------------------------------

    for page_index in sorted(main_pages):
        if page_index <= 0:
            continue

        source_page = pages[page_index].get(
            "source_page",
            page_index + 1,
        )

        candidates.append(
            make_boundary_candidate(
                page_index=page_index,
                source_page=source_page,
                transition="contents_to_main_content",
                score=10.0,
                reason="main-content heading detected",
            )
        )

    # If a contents section exists, look for the first page after the last
    # strong TOC page.
    if contents_pages:
        last_contents_page = max(contents_pages)

        for page_index in range(
            last_contents_page + 1,
            min(
                len(pages),
                last_contents_page + 6,
            ),
        ):
            if page_index in main_pages:
                continue

            if page_has_strong_signal(
                pages[page_index]
            ):
                continue

            scores = page_signal_score(
                pages[page_index]
            )

            if scores["main_content"] > scores["contents"]:
                candidates.append(
                    make_boundary_candidate(
                        page_index=page_index,
                        source_page=pages[page_index].get(
                            "source_page",
                            page_index + 1,
                        ),
                        transition="contents_to_main_content",
                        score=5.0,
                        reason=(
                            "post-contents page resembles main content"
                        ),
                    )
                )
                break

    # -----------------------------------------------------------------------
    # Main -> Back
    # -----------------------------------------------------------------------

    for page_index in sorted(back_pages):
        source_page = pages[page_index].get(
            "source_page",
            page_index + 1,
        )

        candidates.append(
            make_boundary_candidate(
                page_index=page_index,
                source_page=source_page,
                transition="main_content_to_back_matter",
                score=10.0,
                reason="back-matter heading detected",
            )
        )

    for page_index in sorted(end_pages):
        next_index = page_index + 1

        if next_index >= len(pages):
            continue

        source_page = pages[next_index].get(
            "source_page",
            next_index + 1,
        )

        candidates.append(
            make_boundary_candidate(
                page_index=next_index,
                source_page=source_page,
                transition="main_content_to_back_matter",
                score=8.0,
                reason="page follows end marker",
            )
        )

    # -----------------------------------------------------------------------
    # Front -> Contents
    # -----------------------------------------------------------------------

    for page_index in sorted(contents_pages):
        source_page = pages[page_index].get(
            "source_page",
            page_index + 1,
        )

        candidates.append(
            make_boundary_candidate(
                page_index=page_index,
                source_page=source_page,
                transition="front_matter_to_contents",
                score=10.0,
                reason="contents heading detected",
            )
        )

    return candidates


def group_boundary_candidates(
    candidates: Sequence[dict],
) -> Dict[str, List[dict]]:
    grouped: Dict[str, List[dict]] = {
        transition: []
        for transition in BOUNDARY_TRANSITIONS
    }

    for candidate in candidates:
        transition = candidate.get("transition")

        if transition not in grouped:
            continue

        grouped[transition].append(candidate)

    for transition in grouped:
        grouped[transition].sort(
            key=lambda item: (
                -float(item.get("score", 0.0)),
                int(item.get("page_index", 0)),
            )
        )

    return grouped


# ---------------------------------------------------------------------------
# Boundary context
# ---------------------------------------------------------------------------


def make_context_pages(
    pages: List[dict],
    boundary_index: int,
    context_size: int = 2,
) -> tuple[List[dict], List[dict]]:
    """
    Return pages immediately before and after a candidate boundary.
    """
    context_size = max(
        1,
        context_size,
    )

    before_start = max(
        0,
        boundary_index - context_size,
    )

    after_end = min(
        len(pages),
        boundary_index + context_size,
    )

    before_pages = pages[
        before_start:boundary_index
    ]

    after_pages = pages[
        boundary_index:after_end
    ]

    return (
        before_pages,
        after_pages,
    )


# ---------------------------------------------------------------------------
# AI boundary resolution
# ---------------------------------------------------------------------------


def extract_value(
    result: Any,
    key: str,
    default: Any = None,
) -> Any:
    if result is None:
        return default

    if isinstance(result, dict):
        return result.get(
            key,
            default,
        )

    return getattr(
        result,
        key,
        default,
    )


def extract_confidence(
    result: Any,
) -> float:
    value = extract_value(
        result,
        "confidence",
        0.0,
    )

    try:
        value = float(value)
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


def normalize_ai_transition(
    value: Any,
) -> str:
    value = str(value or "").strip()

    if value in BOUNDARY_TRANSITIONS:
        return value

    if value == "none":
        return "none"

    return "none"


def normalize_ai_decision(
    value: Any,
) -> str:
    value = str(value or "").strip().lower()

    if value in {
        "boundary",
        "yes",
        "true",
    }:
        return "boundary"

    return "no_boundary"


def resolve_boundary_with_ai(
    ai_agent: BoundaryClassifier,
    document: dict,
    candidate: dict,
    context_size: int = 2,
) -> dict:
    """
    Ask AI about ONE candidate boundary.

    This is intentionally much narrower than classifying an entire document.
    """
    pages = document.get("pages", [])

    boundary_index = int(
        candidate["page_index"]
    )

    before_pages, after_pages = make_context_pages(
        pages,
        boundary_index,
        context_size=context_size,
    )

    transition = candidate["transition"]

    try:
        raw_result = ai_agent.classify_boundary(
            before_pages=before_pages,
            after_pages=after_pages,
            expected_transition=transition,
        )

    except Exception as exc:
        return {
            **candidate,
            "ai": {
                "enabled": True,
                "decision": "no_boundary",
                "transition": "none",
                "confidence": 0.0,
                "reason": f"AI error: {exc}",
            },
            "accepted": False,
        }

    decision = normalize_ai_decision(
        extract_value(
            raw_result,
            "decision",
            "no_boundary",
        )
    )

    ai_transition = normalize_ai_transition(
        extract_value(
            raw_result,
            "transition",
            "none",
        )
    )

    confidence = extract_confidence(
        raw_result
    )

    reason = str(
        extract_value(
            raw_result,
            "reason",
            "",
        )
        or ""
    )

    accepted = (
        decision == "boundary"
        and ai_transition == transition
        and confidence >= 0.65
    )

    return {
        **candidate,
        "ai": {
            "enabled": True,
            "decision": decision,
            "transition": ai_transition,
            "confidence": confidence,
            "reason": reason,
        },
        "accepted": accepted,
    }


# ---------------------------------------------------------------------------
# Deterministic boundary selection
# ---------------------------------------------------------------------------


def choose_best_candidate(
    candidates: List[dict],
) -> Optional[dict]:
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda item: (
            float(item.get("score", 0.0)),
            -int(item.get("page_index", 0)),
        ),
    )


def resolve_boundary(
    document: dict,
    transition: str,
    candidates: List[dict],
    ai_agent: Optional[BoundaryClassifier],
    ai_score_threshold: float = 7.0,
    ai_context_size: int = 2,
) -> Optional[dict]:
    """
    Resolve one transition.

    Strong deterministic candidates are accepted directly.

    Only ambiguous candidates are sent to AI.
    """
    if not candidates:
        return None

    ranked = sorted(
        candidates,
        key=lambda item: (
            -float(item.get("score", 0.0)),
            int(item.get("page_index", 0)),
        ),
    )

    best = ranked[0]

    # Very strong deterministic evidence.
    if (
        float(best.get("score", 0.0))
        >= ai_score_threshold
    ):
        return {
            **best,
            "resolution": "deterministic",
            "accepted": True,
        }

    # No AI available.
    if ai_agent is None:
        return {
            **best,
            "resolution": "deterministic",
            "accepted": True,
        }

    # Only send a small number of ambiguous candidates to AI.
    # This prevents the AI from becoming the default classifier.
    for candidate in ranked[:3]:
        resolved = resolve_boundary_with_ai(
            ai_agent=ai_agent,
            document=document,
            candidate=candidate,
            context_size=ai_context_size,
        )

        if resolved.get("accepted"):
            resolved["resolution"] = "ai"
            return resolved

    return None


# ---------------------------------------------------------------------------
# Boundary ordering / monotonicity
# ---------------------------------------------------------------------------


def enforce_boundary_order(
    document: dict,
    boundaries: Dict[str, Optional[dict]],
) -> Dict[str, Optional[dict]]:
    """
    Enforce:

        front_matter
            ↓
        contents
            ↓
        main_content
            ↓
        back_matter

    A later boundary can never occur before an earlier one.
    """
    result = dict(boundaries)

    front = result.get(
        "front_matter_to_contents"
    )

    contents = result.get(
        "contents_to_main_content"
    )

    back = result.get(
        "main_content_to_back_matter"
    )

    if front and contents:
        if (
            int(contents["page_index"])
            <= int(front["page_index"])
        ):
            result[
                "contents_to_main_content"
            ] = None

    contents = result.get(
        "contents_to_main_content"
    )

    if contents and back:
        if (
            int(back["page_index"])
            <= int(contents["page_index"])
        ):
            result[
                "main_content_to_back_matter"
            ] = None

    front = result.get(
        "front_matter_to_contents"
    )

    back = result.get(
        "main_content_to_back_matter"
    )

    if front and back:
        if (
            int(back["page_index"])
            <= int(front["page_index"])
        ):
            result[
                "main_content_to_back_matter"
            ] = None

    return result


# ---------------------------------------------------------------------------
# Region assignment
# ---------------------------------------------------------------------------


def assign_regions_from_boundaries(
    document: dict,
    boundaries: Dict[str, Optional[dict]],
) -> Dict[int, str]:
    """
    Convert ordered boundaries into exactly one region per page.

    Region sequence is always monotonic:

        front_matter -> contents -> main_content -> back_matter
    """
    pages = document.get("pages", [])

    front_boundary = boundaries.get(
        "front_matter_to_contents"
    )

    contents_boundary = boundaries.get(
        "contents_to_main_content"
    )

    back_boundary = boundaries.get(
        "main_content_to_back_matter"
    )

    front_index = (
        int(front_boundary["page_index"])
        if front_boundary
        else None
    )

    contents_index = (
        int(contents_boundary["page_index"])
        if contents_boundary
        else None
    )

    back_index = (
        int(back_boundary["page_index"])
        if back_boundary
        else None
    )

    result: Dict[int, str] = {}

    for page_index, page in enumerate(pages):
        source_page = page.get(
            "source_page",
            page_index + 1,
        )

        if (
            front_index is not None
            and page_index < front_index
        ):
            region = "front_matter"

        elif (
            contents_index is not None
            and page_index < contents_index
        ):
            region = "contents"

        elif (
            back_index is not None
            and page_index >= back_index
        ):
            region = "back_matter"

        else:
            region = "main_content"

        result[source_page] = region

    return result


# ---------------------------------------------------------------------------
# Region assembly
# ---------------------------------------------------------------------------


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
    Preserve the original page and all blocks.
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


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------


def split_document(
    document: dict,
    ai_agent: Optional[BoundaryClassifier] = None,
    use_ai: bool = True,
    ai_score_threshold: float = 7.0,
    ai_context_size: int = 2,
) -> dict:
    """
    Split a parsed document into broad semantic regions.

    Strategy:

        1. Find deterministic structural anchors.
        2. Generate boundary candidates.
        3. Accept strong deterministic boundaries immediately.
        4. Ask AI only about weak/ambiguous candidates.
        5. Enforce monotonic region ordering.
        6. Assign every page exactly once.

    This replaces the previous "classify every overlapping page window"
    strategy.
    """
    source_file = str(
        document.get(
            "source_file",
            "",
        )
    )

    regions = create_empty_regions(
        source_file
    )

    pages = document.get(
        "pages",
        [],
    )

    anchors = find_structural_anchors(
        document
    )

    candidates = detect_boundary_candidates(
        document=document,
        anchors=anchors,
    )

    grouped = group_boundary_candidates(
        candidates
    )

    boundaries: Dict[
        str,
        Optional[dict],
    ] = {
        transition: None
        for transition in BOUNDARY_TRANSITIONS
    }

    ai_enabled = bool(
        use_ai
        and ai_agent is not None
    )

    for transition in BOUNDARY_TRANSITIONS:
        transition_candidates = grouped.get(
            transition,
            [],
        )

        boundaries[transition] = resolve_boundary(
            document=document,
            transition=transition,
            candidates=transition_candidates,
            ai_agent=ai_agent if ai_enabled else None,
            ai_score_threshold=ai_score_threshold,
            ai_context_size=ai_context_size,
        )

    boundaries = enforce_boundary_order(
        document=document,
        boundaries=boundaries,
    )

    page_regions = assign_regions_from_boundaries(
        document=document,
        boundaries=boundaries,
    )

    # Assemble final regions.
    for page in pages:
        source_page = page.get(
            "source_page"
        )

        region_name = page_regions.get(
            source_page,
            "main_content",
        )

        add_page_to_region(
            regions[region_name],
            page,
        )

    return {
        "source_file": source_file,
        "regions": regions,
        "anchors": anchors,
        "boundary_candidates": candidates,
        "boundaries": boundaries,
        "page_regions": page_regions,
        "ai": {
            "enabled": ai_enabled,
            "provider": (
                type(ai_agent).__name__
                if ai_agent is not None
                else None
            ),
            "strategy": "deterministic_first_boundary_resolution",
            "ai_score_threshold": ai_score_threshold,
            "ai_context_size": ai_context_size,
        },
    }


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


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

    try:
        return json.loads(
            input_path.read_text(
                encoding="utf-8"
            )
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON: {input_path}"
        ) from exc


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


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


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
        f"Source: {split_data['source_file']}"
    )

    print()
    print("Boundaries:")

    boundaries = split_data.get(
        "boundaries",
        {},
    )

    for transition in BOUNDARY_TRANSITIONS:
        boundary = boundaries.get(
            transition
        )

        if not boundary:
            print(
                f"  {transition:35}: NONE"
            )
            continue

        print(
            f"  {transition:35}: "
            f"page={boundary.get('source_page')} "
            f"resolution={boundary.get('resolution')}"
        )

    print()
    print("Regions:")

    regions = split_data.get(
        "regions",
        {},
    )

    for region_name in REGIONS:
        region = regions.get(
            region_name,
            {},
        )

        page_count = len(
            region.get(
                "pages",
                [],
            )
        )

        block_count = count_blocks(
            region
        )

        print(
            f"  {region_name:15}: "
            f"{page_count:5} pages, "
            f"{block_count:6} blocks"
        )

    print()
    print(
        f"AI enabled: "
        f"{split_data['ai']['enabled']}"
    )

    if split_data["ai"]["enabled"]:
        print(
            f"AI provider: "
            f"{split_data['ai']['provider']}"
        )

        print(
            "AI strategy: "
            f"{split_data['ai']['strategy']}"
        )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Split parsed Document AI JSON into "
            "front matter, contents, main content, "
            "and back matter."
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
        help="Path to output split JSON.",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI boundary resolution.",
    )

    parser.add_argument(
        "--ai-score-threshold",
        type=float,
        default=7.0,
        help=(
            "Deterministic candidate score at which "
            "AI is skipped."
        ),
    )

    parser.add_argument(
        "--ai-context-size",
        type=int,
        default=2,
        help=(
            "Number of pages on each side of an "
            "ambiguous boundary sent to AI."
        ),
    )

    args = parser.parse_args()

    document = load_document(
        args.input
    )

    ai_agent = None

    if not args.no_ai:
        try:
            from .region_agent import GeminiBoundaryAgent

            ai_agent = GeminiBoundaryAgent()

        except ImportError:
            print(
                "Warning: AI agent could not be imported. "
                "Continuing without AI."
            )

    result = split_document(
        document=document,
        ai_agent=ai_agent,
        use_ai=not args.no_ai,
        ai_score_threshold=args.ai_score_threshold,
        ai_context_size=args.ai_context_size,
    )

    save_split(
        result,
        args.output,
    )

    print_summary(
        result
    )

    print()
    print(
        f"Split document saved to: {args.output}"
    )


if __name__ == "__main__":
    main()