from utils import logger 
import os
from typing import Optional
from config import Config 
from storage import BlobStorageManager
from ocr import DocumentAIOCR

logger = logger.getLogger("Orchestrator")

class OCRPipeline : 
    def __init__(self , config : Config):
        self.config = config 
        self.storage = BlobStorageManager(config.AZURE_STORAGE_ACCOUNT_CONNECTION_STRING)
        self.ocr_engine = DocumentAIOCR(config.AZURE_DOCUMENT_AI_ENDPOINT , config.AZURE_DOCUMENT_AI_KEY)
        
    def process_doc(self, pdfname : str ) -> Optional[str] :
        logger.info(f"Initiaitng workflow of {pdfname}")
        
        base_name = os.path.splitext(pdfname)[0]
        markdown_name = f"{base_name}.md"

    # Fault check 
    
        if self.storage.ifblobexists(self.config.output_name , markdown_name ) : 
            logger.info(f"Fault backup triggered {markdown_name}  in cotnainer {self.config.output_name}") 
            return markdown_name 
        try : 
            pdf_bytes = self.storage.download_pdf_into_env(self.config.input_name  , pdfname ) 
            markdown_text  = self.ocr_engine.extract_md(pdf_bytes)
            self.storage.upload_artefact(self.config.output_name , markdown_name , markdown_text)
            logger.info("SUCCESSSS")
            return markdown_name
        except Exception as e : 
            logger.error("ERRROR OROROROOROR")
            raise 