import json
import mimetypes
import os
import re
import shutil
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pprint import pprint
from typing import List, Iterator

from cheesechaser.datapool import DanbooruNewestWebpDataPool, ResourceNotFoundError, InvalidResourceDataError, DataPool
from cheesechaser.pipe import SimpleImagePipe, PipeItem, Pipe
from hbutils.system import TemporaryDirectory
from hfutils.archive import archive_pack
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


class DownloadImagePipe(Pipe):
    def __init__(self, pool: DataPool, dst_dir: str):
        Pipe.__init__(self, pool)
        self.dst_dir = dst_dir

    def retrieve(self, resource_id, resource_metainfo):
        with self.pool.mock_resource(resource_id, resource_metainfo) as (td, resource_metainfo):
            files = os.listdir(td)
            image_files = []
            for file in files:
                mimetype, _ = mimetypes.guess_type(file)
                if not mimetype or mimetype.startswith('image/'):
                    image_files.append(file)
            if len(image_files) == 0:
                raise ResourceNotFoundError(f'Image not found for resource {resource_id!r}.')
            elif len(image_files) != 1:
                raise InvalidResourceDataError(f'Image file not unique for resource {resource_id!r} '
                                               f'- {image_files!r}.')

            src_file = os.path.join(td, image_files[0])
            dst_file = os.path.join(self.dst_dir, os.path.relpath(src_file, td))
            if os.path.dirname(dst_file):
                os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            shutil.copyfile(src_file, dst_file)
            return dst_file


def _tag_normalize(tag) -> str:
    return re.sub(r'[\W_]+', '_', tag).strip('_')


@contextmanager
def download_danbooru_images(tags: List[str], count: int = 100, allowed_ratings=_DEFAULT):
    pool = DanbooruNewestWebpDataPool()
    if len(tags) < 2:
        tags = [*tags, f'id:<{_current_maxid()}']

    with TemporaryDirectory() as td:
        image_dir = os.path.join(td, 'images')
        os.makedirs(image_dir, exist_ok=True)

        exist_ids = set()
        pipe = DownloadImagePipe(pool, image_dir)
        image_files = []
        with pipe.batch_retrieve(_iter_ids(tags, allowed_ratings=allowed_ratings)) as session:
            for i, item in enumerate(session):
                item: PipeItem
                if item.id not in exist_ids:
                    image_files.append((item.id, item.data))
                    exist_ids.add(item.id)
                    if len(image_files) >= count:
                        break

        filename = f'{"__".join(map(_tag_normalize, tags))}__{datetime.now().strftime("%Y%m%d%H%M%S%f")}.zip'
        file_count = os.listdir(image_dir)
        package_file = os.path.join(td, filename)
        archive_pack('zip', image_dir, archive_file=package_file, clear=True)

        yield file_count,package_file


if __name__ == '__main__':
    pprint(query_danbooru_images(['surtr_(arknights)'], count=4))
