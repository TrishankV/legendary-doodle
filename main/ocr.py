from azure.core.credentials import AzureKeyCredential as akc
from azure.ai.documentintelligence import DocumentIntelligenceClient as docai 
from azure.ai.documentintelligence import DocumentContentFormat as formatt 
from utils import logger 

logger = logger("OCRengine")

class DocumentAIOCR :
    def __init__(self , endpoint : str , key : str) : 
        self.client = docai(endpoint = endpoint , credential= akc(key))
        
    def extract_md(self, document_bytes : bytes ) -> str : 
        logger.info("Submitting pdf to Azure Document Ai engine ... ")
        poller = self.client.begin_analyze_document(
            model_id="prebuilt-layout" , 
            analyze_request = document_bytes ,
            content_type= "application/pdf" , 
            output_content_format= formatt.MARKDOWN
        )
        
        logger.info("wating for ocr processing to complete ")
        
        res = poller.result()
        
        if not res.content:
            raise ValueError("OCR is empty")
        return res.content
    
        