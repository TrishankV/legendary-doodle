from dataclasses import dataclass, field
from typing import List, Optional 

@dataclass 
class Block : 
    id : str 
    text : str 
    block_type : str 
    markdown_level: Optional[int] = None
    
@dataclass 
class Page:
    source_page : int 
    printed_page: Optional[str] = None
    blocks : List[Block] = field(default_factory=list)
    
@dataclass 
class Document:
    source_file: str 
    pages : List[Page] = field(default_factory=list)
    
    @property 
    def block_count(self) -> int : 
        return sum(len(page.blocks) for page in self.pages)
    
    @property
    def page_count(self) -> int : 
        return len(self.pages)