from google.cloud import storage 
import os 
import hashlib 
# Class to handle Google Cloud Storage operations 

class StorageHandle : 
    def __init__(self , bucket_name : str , pdf_path :str ) -> None :
        self.client = storage.Client()
        self.bucket_name = bucket_name
        self.bucket = self.client.bucket(bucket_name)
        self.pdf_path = pdf_path
        self.filename = os.path.basename(pdf_path)
        # self.blob = self.bucket.blob(self.filename)
            
    def calc(self) -> str : 
        self.sha256 = hashlib.sha256()
        with open(self.pdf_path , "rb") as f :
            while chunk := f.read(1024 * 1024) : 
                self.sha256.update(chunk)
        return self.sha256.hexdigest()
    
    def hashcheck(self) -> bool : 
        blobs = list(self.bucket.list_blobs())
    
        for i in blobs : 
            print(i.metadata)
            print(i.name)
            print(i)
            if i.metadata is None : 
                continue 
            if i.metadata.get("sha256") == self.pdf_hash :
                return i.name 
        return None
        
    def upload_pdf(self) -> None :
        self.pdf_hash = self.calc()
        self.book_id = self.pdf_hash
        object_name = f"books/{self.book_id}/source.pdf"
        self.blob = self.bucket.blob(object_name)
        existing_pdf = self.hashcheck()
        if existing_pdf : 
            print(f"Same pdf already exists in the bucket {self.bucket_name} with name {existing_pdf}.e")
            return
        self.blob.metadata = { 
                              "sha256": self.pdf_hash}
        if self.blob.exists():
            print(f"File {self.filename} already exists in the bucket {self.bucket_name}.")
        else :
            self.blob.upload_from_filename(self.pdf_path)
            print(f"File {self.filename}")

# Test run 



if __name__ == "__main__":
    s = StorageHandle(
        bucket_name="pdfs-012",
        pdf_path="TESTING/wqwe.pdf"
    )
    s.upload_pdf()
    
    pdf_hash = s.calc()           
    print(f"Hash value of the file is : {pdf_hash}")
    
    existing_pdf = s.hashcheck()   
    print(existing_pdf)            