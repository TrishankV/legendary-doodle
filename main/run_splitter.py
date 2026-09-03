import argparse
from pathlib import Path

from .region_agent import GeminiRegionAgent
from .splitter import (
    load_document,
    save_split,
    split_document,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the document region splitter "
            "with an AI provider."
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
        help="Path to the output split JSON.",
    )

    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="AI model used by the selected provider.",
    )

    parser.add_argument(
        "--config",
        default="configuration.json",
        help="Path to configuration.json.",
    )

    parser.add_argument(
        "--window-size",
        type=int,
        default=5,
        help="Number of pages sent to the AI at once.",
    )

    parser.add_argument(
        "--overlap",
        type=int,
        default=2,
        help="Number of overlapping pages between windows.",
    )

    args = parser.parse_args()

    input_path = Path(
        args.input
    )

    if not input_path.exists():
        raise FileNotFoundError(
            f"Input file not found: {input_path}"
        )

    # ------------------------------------------------------------
    # Create the provider.
    #
    # This is the ONLY place where we currently choose Gemini.
    # splitter.py remains provider-independent.
    # ------------------------------------------------------------

    agent = GeminiRegionAgent(
        model=args.model,
        config_path=args.config,
    )

    print(
        f"AI provider: {type(agent).__name__}"
    )

    print(
        f"AI model: {args.model}"
    )

    print()

    # ------------------------------------------------------------
    # Load parsed Document AI JSON
    # ------------------------------------------------------------

    document = load_document(
        input_path
    )

    # ------------------------------------------------------------
    # Run the generic splitter with the injected AI provider
    # ------------------------------------------------------------

    result = split_document(
        document=document,
        ai_agent=agent,
        use_ai=True,
        window_size=args.window_size,
        overlap=args.overlap,
    )

    # ------------------------------------------------------------
    # Save result
    # ------------------------------------------------------------

    save_split(
        result,
        args.output,
    )

    print()
    print(
        f"Split document saved to: "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()