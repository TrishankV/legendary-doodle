import argparse
import json
from pathlib import Path

from .region_agent import GeminiBoundaryAgent
from .splitter import split_document


def load_parsed_document(path: str) -> dict:
    """Load the parsed document JSON."""
    input_path = Path(path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    with input_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_result(result: dict, path: str) -> None:
    """Save the split result as JSON."""
    output_path = Path(path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved result to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split a parsed document into front matter, contents, "
                    "main content, and back matter."
    )

    parser.add_argument(
        "input",
        type=str,
        help="Path to parsed.json",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="split.json",
        help="Path to output JSON file",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model name",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="configuration.json",
        help="Path to configuration.json",
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable Gemini and use deterministic boundary detection only",
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # Load parsed document
    # ---------------------------------------------------------

    document = load_parsed_document(args.input)

    # ---------------------------------------------------------
    # Create Gemini boundary agent
    # ---------------------------------------------------------

    agent = None

    if not args.no_ai:
        agent = GeminiBoundaryAgent(
            model_name=args.model,
            config_path=args.config,
        )

        print(f"AI model: {args.model}")
    else:
        print("AI disabled")

    # ---------------------------------------------------------
    # Split document
    # ---------------------------------------------------------

    result = split_document(
        document,
        ai_classifier=agent,
        use_ai=not args.no_ai,
    )

    # ---------------------------------------------------------
    # Save result
    # ---------------------------------------------------------

    save_result(result, args.output)

    # ---------------------------------------------------------
    # Print summary
    # ---------------------------------------------------------

    print()
    print("Document split complete.")

    if "page_regions" in result:
        page_regions = result["page_regions"]

        counts = {}

        for region in page_regions.values():
            counts[region] = counts.get(region, 0) + 1

        print()
        print("Page distribution:")

        for region, count in counts.items():
            print(f"  {region}: {count}")

    if "boundaries" in result:
        print()
        print("Boundaries:")

        for boundary_name, page in result["boundaries"].items():
            print(f"  {boundary_name}: {page}")


if __name__ == "__main__":
    main()