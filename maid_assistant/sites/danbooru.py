import json
import mimetypes
import os
from functools import lru_cache
from pprint import pprint
from typing import List, Iterator

from cheesechaser.datapool import DanbooruNewestWebpDataPool
from cheesechaser.pipe import SimpleImagePipe, PipeItem
from huggingface_hub import HfFileSystem
from waifuc.utils import srequest

from ..utils import get_danbooru_session

mimetypes.add_type('image/webp', '.webp')

_N_REPO_ID = 'deepghs/danbooru_newest-webp-4Mpixel'


@lru_cache()
def _current_maxid():
    hf_fs = HfFileSystem(token=os.environ.get('HF_TOKEN'))
    return max(json.loads(hf_fs.read_text(f'datasets/{_N_REPO_ID}/exist_ids.json')))


_DEFAULT = object()
_DEFAULT_ALLOWED_RATINGS = {'g', 's', 'q', 'e'}


def _iter_ids(tags: List[str], allowed_ratings=_DEFAULT) -> Iterator[int]:
    session = get_danbooru_session()
    page_no = 1
    if allowed_ratings is _DEFAULT:
        allowed_ratings = _DEFAULT_ALLOWED_RATINGS
    while True:
        resp = srequest(
            session,
            'GET', f'https://danbooru.donmai.us/posts.json',
            params={
                "format": "json",
                "limit": "200",
                "page": str(page_no),
                "tags": ' '.join(tags),
            }
        )
        if not resp.json():
            break

        for item in resp.json():
            if not item.get('parent_id') and item['rating'] in allowed_ratings:
                yield item['id']

        page_no += 1
        if page_no > 1000:
            break


def query_danbooru_images(tags: List[str], count: int = 4, allowed_ratings=_DEFAULT):
    pool = DanbooruNewestWebpDataPool()
    pipe = SimpleImagePipe(pool)
    images = []
    exist_ids = set()
    if len(tags) < 2:
        tags = [*tags, f'id:<{_current_maxid()}']
    with pipe.batch_retrieve(_iter_ids(tags, allowed_ratings=allowed_ratings)) as session:
        for i, item in enumerate(session):
            item: PipeItem
            if item.id not in exist_ids:
                images.append((item.id, item.data))
                exist_ids.add(item.id)
                if len(images) >= count:
                    break
    return images


if __name__ == '__main__':
    pprint(query_danbooru_images(['surtr_(arknights)'], count=4))
