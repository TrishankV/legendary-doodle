import argparse
from pathlib import Path

from .region_agent import GeminiBoundaryAgent
from .splitter import load_document, print_summary, save_split, split_document


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Split parsed Document AI JSON into front matter, contents, "
            "main content, and back matter."
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
        "--model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model name.",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="configuration.json",
        help="Path to configuration.json.",
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
            "Deterministic candidate score at which AI is skipped."
        ),
    )

    parser.add_argument(
        "--ai-context-size",
        type=int,
        default=2,
        help=(
            "Number of pages on each side of an ambiguous boundary "
            "sent to AI."
        ),
    )

    args = parser.parse_args()

    # ---------------------------------------------------------
    # Load parsed document
    # ---------------------------------------------------------

    document = load_document(args.input)

    # ---------------------------------------------------------
    # Create Gemini boundary agent
    # ---------------------------------------------------------

    ai_agent = None

    if not args.no_ai:
        ai_agent = GeminiBoundaryAgent(
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
        document=document,
        ai_agent=ai_agent,
        use_ai=not args.no_ai,
        ai_score_threshold=args.ai_score_threshold,
        ai_context_size=args.ai_context_size,
    )

    # ---------------------------------------------------------
    # Save result
    # ---------------------------------------------------------

    save_split(
        split_data=result,
        output_path=args.output,
    )

    # ---------------------------------------------------------
    # Print summary
    # ---------------------------------------------------------

    print_summary(result)

    print()
    print(f"Saved result to: {Path(args.output)}")


if __name__ == "__main__":
    main()