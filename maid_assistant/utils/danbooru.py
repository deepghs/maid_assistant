from functools import lru_cache

import httpx
from waifuc.source import DanbooruSource


@lru_cache()
def get_danbooru_session() -> httpx.Client:
    source = DanbooruSource(['1girl'])
    source._prune_session()
    return source.session
