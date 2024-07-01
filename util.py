import datetime
import json
import mimetypes
import os
import sys
from datetime import timedelta

import requests
from dotenv import load_dotenv
from tenacity import (
    Retrying,
    retry_if_exception_type,
    wait_random_exponential,
    stop_after_attempt
)

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI


import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import Logger

logger = Logger()
logger.remove_oldlog()

load_dotenv()

azure_openai_key = os.getenv("AZURE_OPENAI_KEY")
azure_openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
azure_openai_api_type = os.getenv("AZURE_OPENAI_API_TYPE")
azure_openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION")

ai_search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
ai_search_key = os.getenv("AZURE_AI_SEARCH_KEY")

ai_vision_endpoint = os.getenv("AZURE_AI_VISION_ENDPOINT")
ai_vision_key = os.getenv("AZURE_AI_VISION_KEY")

blob_connection_string = os.getenv("AZURE_BLOB_CONNECTION_STRING")
container_name = os.getenv("AZURE_BLOB_CONTAINER_NAME")

index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")
api_version = "2023-02-01-preview"

params = {  
        "api-version": "2023-02-01-preview",
        "overload": "stream",
        "modelVersion": "latest"
}

client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_KEY"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
)

def text_embedding(prompt):
    """
    Azure Computer Vision 4.0 を使用して、テキストのEmbeddingを取得
    """
    logger.info("Generationg embeddings from text...")
    vec_txt_url = f"{ai_vision_endpoint}/computervision/retrieval:vectorizeText"
    headers = {
        "Content-type": "application/json",
        "Ocp-Apim-Subscription-Key": ai_vision_key
        }
    payload = {
        "text": prompt
        }
    
    response = requests.post(url=vec_txt_url, params=params, headers=headers, json=payload)

    if response.status_code == 200:
        logger.info("Embeddings generated successfully.")
        text_emb = response.json().get("vector")
        return text_emb
    
    else:
        logger.error(f"Error generating embeddings: {response.status_code}: {response.text}")
        return None
    

def image_embedding(image_path):
    logger.info("Generating embeddings from image...")
    url = f"{ai_vision_endpoint}/computervision/retrieval:vectorizeImage"
    mime_type = mimetypes.guess_type(image_path)[0]
    headers = {
        "Content-type": mime_type,
        "Ocp-Apim-Subscription-Key": ai_vision_key
    }
    for attempt in Retrying(
        retry=retry_if_exception_type(requests.HTTPError),
        wait=wait_random_exponential(min=15, max=60),
        stop=stop_after_attempt(15)
    ):
        with attempt:
            with open(image_path, 'rb') as image_data:
                response = requests.post(url, params=params, headers=headers, data=image_data)
                if response.status_code != 200:
                    logger.info(f"Error generating embeddings: {response.status_code}: {response.text}")
                    response.raise_for_status()
    logger.info("Embeddings generated successfully.")
    image_emb = response.json()["vector"]
    return image_emb


def get_translation(text, lang, max_retires=3, retry_delay=1):
    """
    AOAIを使用してテキスト翻訳する
    """
    logger.info(f"Get Translation | Translating text to {lang}...")
    sentence = f"Translate the following text to {lang}: {text}"

    try:
        response =client.completions.create(
            model="gpt-35-turbo",
            prompt=sentence,
            max_tokens=800,
            top_p=1.0,
            frequency_penalty=0,
            presence_penalty=0,
            best_of=1,
            stop=None,
        )
        resp = response.choices[0].text

        return resp

    except Exception as e:
        logger.error(f"Error translating text: {e}")
        return None


def index_stats(index_name):
    """
    Azure AI Search でインデックスの統計情報を取得
    """
    url = (
        ai_search_endpoint
        + "/indexes/"
        + index_name
        + "/stats"
    )
    headers = {
        "Content-Type": "application/json",
        "api-key": ai_search_key
    }
    params = {
        "api-version": "2021-04-30-Preview"
    }
    response = requests.get(url, headers=headers, params=params)
    logger.info(f"Azure AI Search Index status for: {index_name} \n")

    if response.status_code == 200:
        res = response.json()
        logger.info(json.dumps(res, indent=2))
    
    else:
        logger.error(f"Error getting index status: {response.status_code}: {response.text}")
        return None


def index_status(index_name):
    """
    Azure AI Search でインデックスのステータスを取得
    """
    logger.info(f"Azure AI Search Index: {index_name} status \n")

    url = ai_search_endpoint + "/indexes/" + index_name
    headers = {
        "Content-Type": "application/json",
        "api-key": ai_search_key
    }
    params = {
        "api-version": "2021-04-30-Preview"
    }
    index_status = requests.get(url, headers=headers, params=params)
    
    try:
        logger.info(json.dumps(index_status.json(), indent=4))
    except Exception as e:
        logger.error(f"Error getting index status: {e}")
        return None


def prompt_search(prompt, topn=5, disp=False):
    """
    Azure AI Search で Prompt を使用して検索
    """

    logger.info("Searching for prompt...")
    results_list = []

    search_client = SearchClient(endpoint=ai_search_endpoint, index_name=index_name, credential=AzureKeyCredential(ai_search_key))
    blob_service_client = BlobServiceClient.from_connection_string(blob_connection_string)
    container_client = blob_service_client.get_container_client(container_name)

    vector_query = VectorizedQuery(vector=text_embedding(prompt), k_nearest_neighbors=topn, fields="image_vector")
    response = search_client.search(
        search_text=prompt, vector_queries=[vector_query], select=["description"], top=2
    )
    for nb, result in enumerate(response, 1):
        logger.info(f"Search Result {nb}: {result['description']}")
        blob_name = result["description"] + ".jpg"
        blob_client = container_client.get_blob_client(blob_name)
        image_url = blob_client.url
        sas_token = generate_blob_sas(
            blob_service_client.account_name,
            container_name,
            blob_name,
            account_key=blob_client.credential.account_key,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=1),
        )
        sas_url = blob_client.url + "?" + sas_token
        results_list.append(
            {
                "buy_now_link": sas_url,
                "price_of_the_product": result["description"],
                "product_image_url": image_url
            }
        )
    return results_list


# def get_cosine_similarity(vec1, vec2):
#     pass


# def visual_search(clothes_list):
#     pass


# def display_images(images_list, num_cols=5, disp_cosine=False, source="prompt"):
#     pass


# def get_list():
#     pass


# def download_and_convert_to_base64():
#     pass


# def replace_urls_with_base64_images():
#     pass