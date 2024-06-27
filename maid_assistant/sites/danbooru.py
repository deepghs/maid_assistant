import mimetypes
from functools import lru_cache
from itertools import islice
from pprint import pprint
from typing import List, Iterator

import httpx
from cheesechaser.datapool import DanbooruWebpDataPool
from cheesechaser.pipe import SimpleImagePipe, PipeItem
from waifuc.source import DanbooruSource
from waifuc.utils import srequest

mimetypes.add_type('image/webp', '.webp')


@lru_cache()
def _get_session() -> httpx.Client:
    source = DanbooruSource(['1girl'])
    source._prune_session()
    return source.session


def _iter_ids(tags: List[str]) -> Iterator[int]:
    session = _get_session()
    page_no = 1
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
            yield item['id']


def query_danbooru_images(tags: List[str], count: int = 4):
    pool = DanbooruWebpDataPool()
    pipe = SimpleImagePipe(pool)
    images = []
    with pipe.batch_retrieve(_iter_ids(tags)) as session:
        for i, item in enumerate(islice(session, count)):
            item: PipeItem
            images.append((item.id, item.data))
    return images


if __name__ == '__main__':
    pprint(query_danbooru_images(['surtr_(arknights)'], count=4))
