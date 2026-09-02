import os 
from utils import logger 
import logging 
from config import Config 
from pipeline import OCRPipeline
import tqdm 

logging.basicConfig(level=logging.INFO , format = "%(asctime)s - [%(levelname)s] - %(message)s" )

def main() :
    config = Config("configuration.json")
    ocr_pipeline = OCRPipeline(config)
    
    local_pdf_path = "TESTING/wall of the world.pdf"
    if not os.path.exists(local_pdf_path) : 
        logging.error(f"Could not find a file named {local_pdf_path}")
        return 
        
    filename_to_process = os.path.basename(local_pdf_path)
    
    # Uploading into storage account / container 
    
    ocr_pipeline.storage.upload_local(
        container_name = config.input_name , 
        local_file_path = local_pdf_path , 
        blob_name = filename_to_process
    )
    
    # checking up the progress 
    
    print()
    
    with tqdm.tqdm(total = 100 , desc =  "OCR Processing" , bar_format = "{desc}:{percentage:3.0f}|{bar}| [{elapsed} elapsed]") as pbar : 
        def update_bar():
            if pbar.n <98 : 
                increment = 2 if pbar.n < 80 else 0.5
                pbar.update(increment)
                
        res = ocr_pipeline.process_doc(filename_to_process)
        
        if res : 
            pbar.n = 100 
            pbar.refresh()
            print(" SUCCESSSSJSJJSJJSJJJS")
            
if __name__ == "__main__" : 
    main()

