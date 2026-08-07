import os
from dotenv import load_dotenv
from appwrite.client import Client
from appwrite.query import Query  
from appwrite.services.databases import Databases
from appwrite.id import ID

# Force load the environment variables into memory immediately
load_dotenv()

# 1. Initialize the Appwrite Client
client = Client()
client.set_endpoint(os.getenv("APPWRITE_ENDPOINT", "https://sgp.cloud.appwrite.io/v1"))

# Fetch the Project ID and strictly apply it
project_id = os.getenv("APPWRITE_PROJECT_ID")
if not project_id:
    print("CRITICAL ERROR: APPWRITE_PROJECT_ID is empty. Check your .env file.")

client.set_project(project_id)
client.set_key(os.getenv("APPWRITE_API_KEY"))

# 2. Initialize the Databases Service
databases = Databases(client)

def push_to_appwrite(product_data: dict):
    """
    Pushes the AI generated product data to the Appwrite ProductsCatalog.
    Uses SKU to update existing records or creates a new one if it doesn't exist.
    """
    try:
        database_id = os.getenv("APPWRITE_DATABASE_ID")
        collection_id = os.getenv("APPWRITE_COLLECTION_ID")
        sku = product_data.get("sku")

        # 1. Search for existing document by SKU
        existing = databases.list_documents(
            database_id=database_id,
            collection_id=collection_id,
            queries=[Query.equal("sku", sku)]
        )

        if existing.total > 0:
            # 2. Update existing document
            doc_id = existing.documents[0].id
            result = databases.update_document(
                database_id=database_id,
                collection_id=collection_id,
                document_id=doc_id,
                data=product_data
            )
            print(f"Successfully updated product {sku} in Appwrite.")
        else:
            # 3. Create new document
            result = databases.create_document(
                database_id=database_id,
                collection_id=collection_id,
                document_id=sku, # Use SKU as ID for easy future lookups
                data=product_data
            )
            print(f"Successfully created product {sku} in Appwrite.")
            
        return result

    except Exception as e:
        print(f"Appwrite Insertion Error: {str(e)}")
        return None
    
def push_to_sync_queue(product_id: str, sku: str, marketplace_array: list):
    try:
        database_id = os.getenv("APPWRITE_DATABASE_ID")
        collection_id = os.getenv("APPWRITE_SYNC_COLLECTION_ID")
        
        # Ensure marketplace_array is definitely a list
        if not isinstance(marketplace_array, list):
            marketplace_array = [marketplace_array]
        
        sync_payload = {
            "product_id": product_id,
            "sku": str(sku),
            "marketplaces": marketplace_array, # This is the array
            "status": "Pending-Sync"
        }
        
        return databases.create_document(
            database_id=database_id,
            collection_id=collection_id,
            document_id=ID.unique(),
            data=sync_payload
        )
    except Exception as e:
        print(f"Appwrite Sync Queue Error: {str(e)}")
        return None