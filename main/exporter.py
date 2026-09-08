from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List


REGIONS = (
    "front_matter",
    "contents",
    "main_content",
    "back_matter",
)


class EPUBExporter:
    """
    Convert split document JSON into clean Markdown and EPUB.

    Pipeline:

        split.json
            ↓
        clean Markdown
            ↓
        Pandoc
            ↓
        EPUB
    """

    def __init__(
        self,
        pandoc_command: str = "pandoc",
    ) -> None:
        self.pandoc_command = pandoc_command

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    def check_pandoc(self) -> None:
        """
        Verify that Pandoc is installed.
        """

        if shutil.which(self.pandoc_command) is None:
            raise RuntimeError(
                f"Pandoc was not found: {self.pandoc_command}\n"
                "Install Pandoc and make sure it is available on PATH."
            )

    # ---------------------------------------------------------
    # Loading
    # ---------------------------------------------------------

    def load_split(
        self,
        path: str | Path,
    ) -> dict:
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"Split file not found: {path}"
            )

        try:
            return json.loads(
                path.read_text(
                    encoding="utf-8"
                )
            )
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON: {path}"
            ) from exc

    # ---------------------------------------------------------
    # Markdown cleanup
    # ---------------------------------------------------------

    def clean_block(
        self,
        block: dict,
    ) -> str:
        """
        Convert one parsed block into Markdown.

        Metadata blocks are omitted because they are Document AI
        implementation details, not book content.
        """

        block_type = block.get(
            "block_type",
            "paragraph",
        )

        text = str(
            block.get(
                "text",
                "",
            )
            or ""
        ).strip()

        if not text:
            return ""

        # Document AI metadata should not enter the EPUB.
        if block_type == "metadata":
            return ""

        # Already valid Markdown heading.
        if block_type == "heading":
            if text.startswith("#"):
                return text

            level = block.get(
                "markdown_level"
            )

            if level is None:
                level = 1

            level = max(
                1,
                min(
                    6,
                    int(level),
                ),
            )

            return (
                "#" * level
                + " "
                + text
            )

        # Tables are already emitted by Document AI as Markdown/HTML.
        if block_type == "table":
            return text

        return text

    def clean_page(
        self,
        page: dict,
    ) -> str:
        blocks: List[str] = []

        for block in page.get(
            "blocks",
            [],
        ):
            cleaned = self.clean_block(
                block
            )

            if cleaned:
                blocks.append(
                    cleaned
                )

        return "\n\n".join(
            blocks
        )

    # ---------------------------------------------------------
    # Region rendering
    # ---------------------------------------------------------

    def render_region(
        self,
        region: dict,
    ) -> str:
        pages = region.get(
            "pages",
            [],
        )

        rendered_pages: List[str] = []

        for page in pages:
            page_text = self.clean_page(
                page
            )

            if page_text:
                rendered_pages.append(
                    page_text
                )

        return "\n\n".join(
            rendered_pages
        )

    # ---------------------------------------------------------
    # Full book rendering
    # ---------------------------------------------------------

    def build_markdown(
        self,
        split_data: dict,
    ) -> str:
        """
        Build one clean Markdown document.

        The regions are emitted in canonical book order:

            front matter
            contents
            main content
            back matter
        """

        regions = split_data.get(
            "regions",
            {},
        )

        sections: List[str] = []

        for region_name in REGIONS:
            region = regions.get(
                region_name
            )

            if not region:
                continue

            text = self.render_region(
                region
            )

            if text:
                sections.append(
                    text
                )

        markdown = "\n\n".join(
            sections
        )

        # Normalize excessive blank lines.
        while "\n\n\n" in markdown:
            markdown = markdown.replace(
                "\n\n\n",
                "\n\n",
            )

        return markdown.strip() + "\n"

    # ---------------------------------------------------------
    # Write Markdown
    # ---------------------------------------------------------

    def write_markdown(
        self,
        markdown: str,
        output_path: str | Path,
    ) -> Path:
        output_path = Path(
            output_path
        )

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            markdown,
            encoding="utf-8",
        )

        return output_path

    # ---------------------------------------------------------
    # EPUB generation
    # ---------------------------------------------------------

    def build_epub(
        self,
        markdown_path: str | Path,
        epub_path: str | Path,
        title: str | None = None,
        author: str | None = None,
    ) -> Path:
        """
        Convert Markdown to EPUB using Pandoc.
        """

        self.check_pandoc()

        markdown_path = Path(
            markdown_path
        )

        epub_path = Path(
            epub_path
        )

        if not markdown_path.exists():
            raise FileNotFoundError(
                f"Markdown file not found: {markdown_path}"
            )

        epub_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        command = [
            self.pandoc_command,
            str(markdown_path),
            "-o",
            str(epub_path),
            "--from=markdown",
            "--to=epub3",
        ]

        if title:
            command.extend(
                [
                    "--metadata",
                    f"title={title}",
                ]
            )

        if author:
            command.extend(
                [
                    "--metadata",
                    f"author={author}",
                ]
            )

        print(
            "Running Pandoc:"
        )
        print(
            " ".join(command)
        )

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                "Pandoc failed.\n\n"
                f"STDOUT:\n{result.stdout}\n\n"
                f"STDERR:\n{result.stderr}"
            )

        if not epub_path.exists():
            raise RuntimeError(
                "Pandoc completed successfully "
                "but the EPUB file was not created."
            )

        return epub_path


def convert_split_to_epub(
    split_json: str | Path,
    markdown_output: str | Path,
    epub_output: str | Path,
    title: str | None = None,
    author: str | None = None,
) -> Path:
    """
    Convenience function for the complete:

        split.json → Markdown → EPUB

    operation.
    """

    exporter = EPUBExporter()

    split_data = exporter.load_split(
        split_json
    )

    markdown = exporter.build_markdown(
        split_data
    )

    exporter.write_markdown(
        markdown,
        markdown_output,
    )

    return exporter.build_epub(
        markdown_path=markdown_output,
        epub_path=epub_output,
        title=title,
        author=author,
    )