# loading all the api endpoints and their respective functions
import json

# import os

class Config:
    def __init__(self , path = "configuration.json" ) -> None:
        self.path = path
        with open(path , "r") as f :
            data = json.load(f)

        azure = data.get("azure", {})
        
        search_service = azure.get("search_service", {})
        document_ai = azure.get("documentai", {})
        googleapi = data.get("google", {})
        storageacc = azure.get("azstorage", {})
        container = storageacc.get("containers" , {})

        self.GOOGLE_GEMINI_API = googleapi.get("api_key")
        self.AZURE_DOCUMENT_AI_ENDPOINT = document_ai.get("endpoint")
        self.AZURE_DOCUMENT_AI_KEY = document_ai.get("key")
        self.AZURE_SEARCH_ENDPOINT = search_service.get("endpoint")
        self.AZURE_SEARCH_KEY = search_service.get("key")
        self.AZURE_STORAGE_ACCOUNT_ENDPOINT = storageacc.get("endpoint")
        self.AZURE_STORAGE_ACCOUNT_KEY = storageacc.get("key")
        self.AZURE_STORAGE_ACCOUNT_CONNECTION_STRING = storageacc.get("connection_string")
        self.input_name = container.get("input")
        self.output_name = container.get("artefacts")


# con = Config()
# # print(con.AZURE_DOCUMENT_AI_ENDPOINT)
# # print(con.AZURE_DOCUMENT_AI_KEY)
# # print(con.AZURE_SEARCH_ENDPOINT)
# # print(con.AZURE_SEARCH_KEY)
# # print(con.GOOGLE_GEMINI_API)    
# # print(con.AZURE_STORAGE_ACCOUNT_CONNECTION_STRING)
# print(con.input_name)
        
