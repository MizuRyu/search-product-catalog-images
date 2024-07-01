import os
import datetime
import json

from datetime import timedelta
from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.search.documents import SearchClient

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from util import image_embedding
from logger import Logger

logger = Logger()
logger.remove_oldlog()

load_dotenv()

ai_search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
ai_search_key = os.getenv("AZURE_AI_SEARCH_KEY")
index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")

azure_blob_account_key = os.getenv("AZURE_BLOB_ACCOUNT_KEY")
blob_connection_string = os.getenv("AZURE_BLOB_CONNECTION_STRING")
container_name = os.getenv("AZURE_BLOB_CONTAINER_NAME")

blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
container_client = blob_service_client.get_container_client(container_name)

# 製品画像をロード
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBEDDINGS_DIR = os.path.join(root_dir, 'embeddings')

os.makedirs(EMBEDDINGS_DIR, exist_ok=True)
image_dir = os.path.join('images')
embedding_dir = os.path.join('embeddings')
output_json_file = os.path.join(embedding_dir, 'output.jsonl')

# Blob Storage に存在しない場合、画像をアップロード
for root, dirs, files in os.walk(image_dir):
    logger.info(f"Uploading images from {root}")
    for file in files:
        local_file_path = os.path.join(root, file)
        blob_client = container_client.get_blob_client(blob=file)

        try:
            blob_client.get_blob_properties()
            logger.info(f"Blob {blob_client.url} already exists. Skipping upload.")
            
        except ResourceNotFoundError:
            with open(local_file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)
                logger.info(f"Uploaded {local_file_path} to {blob_client.url}")
        
        except Exception as e:
            logger.error(f"Error uploading {local_file_path} to {blob_client.url}: {e}")

# 画像のembeddingを生成
with open(output_json_file, "w") as outfile:
    for idx, image_path in enumerate(os.listdir(image_dir)):
        if image_path:
            try:
                vector = image_embedding(os.path.join(image_dir, image_path))
            except Exception as e:
                logger.error(f"Error processing image at index {image_path}: {e}")
                vector = None

            filename, _ = os.path.splitext(os.path.basename(image_path))
            result = {
                "id": f'{idx}',
                "image_vector": vector,
                "description": filename,
                # TODO: 価格、商品名、購入リンクなどのメタデータを追加
            }

            outfile.write(json.dumps(result))
            outfile.write("\n")
            outfile.flush()

logger.info(f"Embeddings generated successfully. Output file: {output_json_file}")

# AI Searchのインデックスにファイルをアップロード
data = []
with open(output_json_file, "r") as file:
    for line in file:
        json_data = json.loads(line.strip())
        data.append(json_data)

search_client = SearchClient(endpoint=ai_search_endpoint, index_name=index_name, credential=AzureKeyCredential(ai_search_key))
results = search_client.upload_documents(documents=data)
for result in results:
    logger.info(f"Indexed {result.key} with status code {result.status_code}")
    