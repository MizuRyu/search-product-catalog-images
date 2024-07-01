import os

from dotenv import load_dotenv

from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SimpleField,
    SearchField,
    SearchFieldDataType,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SearchIndex,
)

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from logger import Logger

logger = Logger()
logger.remove_oldlog()

load_dotenv()

ai_search_endpoint = os.getenv("AZURE_AI_SEARCH_ENDPOINT")
ai_search_key = os.getenv("AZURE_AI_SEARCH_KEY")

index_name = os.getenv("AZURE_AI_SEARCH_INDEX_NAME")

credential = AzureKeyCredential(ai_search_key)

index_client = SearchIndexClient(endpoint=ai_search_endpoint, credential=credential)
fields = [
    SimpleField(
        name="id", 
        type=SearchFieldDataType.String, 
        key=True
    ),
    SearchField(
        name="description", 
        type=SearchFieldDataType.String, 
        sortable=True, 
        filterable=True, 
        facetable=True
    ),
    SearchField(
        name="image_vector", 
        hidden=True, 
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single), 
        searchable=True, 
        vector_search_dimensions=1024, 
        vector_search_profile_name="myHnswProfile"
    )
]

vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(
            name="myHnsw"
        )
    ],
    profiles=[
        VectorSearchProfile(
            name="myHnswProfile",
            algorithm_configuration_name="myHnsw"
        )
    ],
)

index = SearchIndex(
    name=index_name,
    fields=fields,
    vector_search=vector_search
)
result = index_client.create_or_update_index(index)
logger.info(f"Create index {result.name}")