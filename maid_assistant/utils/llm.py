import os
from functools import lru_cache

from openai import OpenAI


@lru_cache()
def _get_llm_base_url():
    return os.environ['LLM_BASE_URL']


@lru_cache()
def _get_llm_api_key():
    return os.environ['LLM_API_KEY']


@lru_cache()
def get_openai_client():
    return OpenAI(
        api_key=_get_llm_api_key(),
        base_url=_get_llm_base_url(),
    )


@lru_cache()
def get_llm_default_model():
    return os.environ['LLM_DEFAULT_MODEL']
