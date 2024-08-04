import json
import mimetypes
import os
from functools import lru_cache
from typing import List

from cheesechaser.datapool import GelbooruWebpDataPool
from cheesechaser.pipe import SimpleImagePipe, PipeItem
from cheesechaser.query import GelbooruIdQuery
from huggingface_hub import HfFileSystem

mimetypes.add_type('image/webp', '.webp')

_N_REPO_ID = 'deepghs/gelbooru-webp-4Mpixel'


@lru_cache()
def _current_maxid():
    hf_fs = HfFileSystem(token=os.environ.get('HF_TOKEN'))
    return max(json.loads(hf_fs.read_text(f'datasets/{_N_REPO_ID}/exist_ids.json')))


_DEFAULT = object()
_DEFAULT_ALLOWED_RATINGS = {'general', 'sensitive', 'questionable', 'explicit'}


def query_gelbooru_images(tags: List[str], count: int = 4, allowed_ratings=_DEFAULT):
    pool = GelbooruWebpDataPool()
    pipe = SimpleImagePipe(pool)
    images = []
    exist_ids = set()
    tags = [*tags, f'id:<{_current_maxid()}']
    if not any(tag.startswith('sort:') for tag in tags):
        tags = [*tags, 'sort:score:desc']
    if allowed_ratings is _DEFAULT:
        allowed_ratings = _DEFAULT_ALLOWED_RATINGS

    query = GelbooruIdQuery(
        tags=tags,
        filters=[
            lambda x: x['rating'] in allowed_ratings,
        ]
    )

    with pipe.batch_retrieve(query) as session:
        for i, item in enumerate(session):
            item: PipeItem
            if item.id not in exist_ids:
                images.append((item.id, item.data))
                exist_ids.add(item.id)
                if len(images) >= count:
                    break
    return images
