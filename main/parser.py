import json 
import re 
from pathlib import Path 
from .models import Block , Document , Page 

PAGE_BREAK_PATTERN = "<!-- PageBreak -->"


# classifying the type of block with regards to the classes made . 
def classify_block(text:str) -> str : 
    strip_text = text.strip()
    
    if not strip_text : 
        return "blank"
    if strip_text.startswith("#") :
        return "heading"
    if strip_text.startswith("<table") or strip_text.startswith("|") : 
        return "table"
    if strip_text.startswith("<!--") and strip_text.endswith("-->") :
        return "metadata"
    return "paragraph"

# Heading in the markdown 
def extract_heading_level(text:str) -> int : 
    match = re.match(r"^(#{1,6})\s+" , text.strip())
    
    if not match : 
        return None
    
    return len(match.group(1))


# function to parse the page and return the page object with the blocks in it.
def parse_page(page_text:str , source_page: int, ) -> Page:
    page = Page(source_page=source_page)
    raw_blocks = re.split(r"\n\s*\n" , page_text)
    
    block_number = 0 
    for raw_block in raw_blocks : 
        text = raw_block.strip()
        
        if not text : 
            continue
        block_number += 1
        block_id = f"p{source_page:04d}_b{block_number:03d}"
        
        block_type = classify_block(text)
        markdown_level = extract_heading_level(text) 
        
        block = Block(id=block_id , text=text , block_type=block_type , markdown_level=markdown_level)
        page.blocks.append(block)
    return page

# function to parse the entire MARKDOWN document and return the document object with the pages in it.
def parse_markdown(path: str | Path) -> Document:
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    text = path.read_text(encoding="utf-8" , errors="replace")
    raw_pages = text.split(PAGE_BREAK_PATTERN)
    document = Document(source_file=str(path))
    
    for source_page , page_text in enumerate(raw_pages , start = 1 ):
        page = parse_page(
            page_text=page_text,
            source_page=source_page
        )
        document.pages.append(page)
    return document

# turning the document into dictionary top have a proper sturcture 
def document_to_dict(document: Document) -> dict:
    return {
        "source_file": document.source_file,
        "block_count": document.block_count,
        "page_count": document.page_count,
        "pages": [
            {
                "source_page": page.source_page,
                "printed_page": page.printed_page,
                "blocks": [
                    {
                        "id": block.id,
                        "text": block.text,
                        "block_type": block.block_type,
                        "markdown_level": block.markdown_level
                    }
                    for block in page.blocks
                ]
            }
            for page in document.pages
        ]
    }

def save_json(document: Document, output_path: str| Path):
    output_path = Path(output_path)
    data = document_to_dict(document)
    output_path.parent.mkdir(
        parents=True , exist_ok=True
    )
    
    output_path.write_text(
        json.dumps(
            data , 
            indent = 2 , 
            ensure_ascii=False,
        ) , 
        encoding="utf-8"
    )       

if __name__ == "__main__":
    import argparse 
    parser = argparse.ArgumentParser(
        description="Parse a markdown file into a structured JSON representation."
    )
    parser.add_argument(
        "input",
        type=str,
        help="Path to the input markdown file."
    )
    parser.add_argument(
        "-o" , 
        "--output",
        default = "parsed.json" , 
        help="Output JSON path." , 
    )
    args = parser.parse_args()
    
    document = parse_markdown(args.input)
    save_json(document , args.output)
    
    print(f"Parsed document saved to {args.output}")
    print(f"Pages: {document.page_count}")
    print(f"Blocks: {document.block_count}")
    print(f"Output: {args.output}")