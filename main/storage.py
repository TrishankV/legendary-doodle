from google.cloud import storage 
import os 

# Uploading 

def upload_pdf(bucket_name , pdf_path ) -> None :
    client = storage.Client()
    filename = os.path.basename(pdf_path)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    blob.upload_from_filename(pdf_path)
    print(f"Uploaded {pdf_path} to {bucket_name}.")

# Checking 

def chek(bucket_name , pdf_path ) -> bool : 
    client = storage.Client()
    filename = os.path.basename(pdf_path)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(filename)
    return blob.exists()

# Test run 
if __name__ == "__main__":
    if chek("pdfs-012", "TESTING/wall of the world.pdf"):
        print("File already exists in the bucket.")
    else:
        upload_pdf("pdfs-012", "TESTING/wall of the world.pdf")
