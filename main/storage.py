import logging 
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceNotFoundError 
from config import Config
from utils import logger

logger = logger("Storage")

class BlobStorageManager : 
    
    def __init__(self, connection_string: str ) -> None :
        self.blobclient = BlobServiceClient.from_connection_string(connection_string)
        
        # blob_client = self.blobclient.get_blob_client(container = container_anme , blob =  blob_name )

    def ifblobexists(self, container_anme : str , blob_name : str ) -> bool : 
        blob_client = self.blobclient.get_blob_client(container = container_anme , blob =  blob_name )

        try : 
            blob_client.get_blob_properties()
            return True 
        except ResourceNotFoundError:
            return False 

    def upload_local(self , container_name : str , local_file_path : str , blob_name : str ) -> None : 
        logger.info(f"Uploading localfile into the '{blob_name}' in '{container_name}' ")
        blob_client = self.blobclient.get_blob_client(container = container_name , blob =  blob_name )
        with open(local_file_path, "rb") as f :
            blob_client.upload_blob(f, overwrite = True )

    def download_pdf_into_env(self, container_name : str , blob_name : str  ) -> bytes : 
        logger.info(f"Downloading '{blob_name}' from '{container_name}' ")
        blob_client = self.blobclient.get_blob_client(container = container_name , blob =  blob_name )
        return blob_client.download_blob().readall()

    def upload_artefact(self, container_name : str , blob_name : str , data : str ) -> None : 
        logger.info(f"Uploading text artefact {blob_name} into {container_name}")
        blob_client = self.blobclient.get_blob_client(container = container_name , blob =  blob_name )
        blob_client.upload_blob(data, overwrite = True )



