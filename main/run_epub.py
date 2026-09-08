from __future__ import annotations

import argparse
from pathlib import Path

from .exporter import convert_split_to_epub


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert split document JSON into clean Markdown "
            "and an EPUB using Pandoc."
        )
    )

    parser.add_argument(
        "input",
        help="Path to split.json",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="book.epub",
        help="Output EPUB path.",
    )

    parser.add_argument(
        "--markdown",
        default=None,
        help=(
            "Intermediate Markdown path. "
            "Defaults to the EPUB filename with .md extension."
        ),
    )

    parser.add_argument(
        "--title",
        default=None,
        help="Book title.",
    )

    parser.add_argument(
        "--author",
        default=None,
        help="Book author.",
    )

    args = parser.parse_args()

    epub_path = Path(
        args.output
    )

    markdown_path = (
        Path(args.markdown)
        if args.markdown
        else epub_path.with_suffix(".md")
    )

    print(
        f"Input split JSON: {args.input}"
    )

    print(
        f"Intermediate Markdown: {markdown_path}"
    )

    print(
        f"Output EPUB: {epub_path}"
    )

    result = convert_split_to_epub(
        split_json=args.input,
        markdown_output=markdown_path,
        epub_output=epub_path,
        title=args.title,
        author=args.author,
    )

    print()
    print(
        "EPUB successfully created:"
    )
    print(
        result
    )


if __name__ == "__main__":
    main()