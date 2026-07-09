import warnings
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.id import ID

APPWRITE_ENDPOINT = "https://sgp.cloud.appwrite.io/v1"
APPWRITE_PROJECT_ID = "6a4cfba4003dab2e4e75"
APPWRITE_API_KEY = "standard_d0dfe984105bce7d3a48d947ddde48fc4f290a941adca4c3cd287c6d92253d848a71c5352b7cc4c2f0df0b6f6fbfd671eb16b2eb92949ab4ceb0569e159801524722269025d8a9aa3c50a84c27feae422865b0771807cd62eb8fec1b217fe80aa9f3469da0fef7d08e471744b5863927292e4847fccdfa791f96ff50b968872c"
DATABASE_ID = "6a4cfe93003921333e93"
COLLECTION_ID = "6a4cff4f001d99867db7"

# Initialize Client
client = Client()
client.set_endpoint(APPWRITE_ENDPOINT)
client.set_project(APPWRITE_PROJECT_ID)
client.set_key(APPWRITE_API_KEY)

databases = Databases(client)

def push_to_sync_queue(product_id: str, marketplace: str) -> dict:
    """
    Persists a new synchronization task in the Appwrite database, 
    which acts as an event trigger for the serverless cloud engine.
    
    Args:
        product_id (str): Unique identifier of the product to be synced.
        marketplace (str): Target marketplace(s) for synchronization.
        
    Returns:
        dict: The created database document payload containing the system-generated $id.
    """
    try:
        # Suppressing the misleading DeprecationWarning from the current SDK version
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=DeprecationWarning)
            
            # Reverting to the stable method that successfully executes the cloud trigger
            result = databases.create_document(
                database_id=DATABASE_ID,
                collection_id=COLLECTION_ID,
                document_id=ID.unique(),
                data={
                    "product_id": product_id,
                    "marketplace": marketplace,
                    "status": "Pending-Sync"
                }
            )
            return result
    except Exception as e:
        # Log critical persistence failures for debugging
        print(f"❌ [AppwriteService] Persistence Error: {str(e)}")
        raise e