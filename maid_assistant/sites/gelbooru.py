import json
import mimetypes
import os
import re
import shutil
import zipfile
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pprint import pprint
from typing import List, Optional

from cheesechaser.datapool import GelbooruWebpDataPool, DataPool, ResourceNotFoundError, InvalidResourceDataError
from cheesechaser.pipe import SimpleImagePipe, PipeItem, Pipe
from cheesechaser.query import GelbooruIdQuery
from hbutils.system import TemporaryDirectory
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


class DownloadImagePipe(Pipe):
    def __init__(self, pool: DataPool, dst_dir: str):
        Pipe.__init__(self, pool)
        self.dst_dir = dst_dir

    def retrieve(self, resource_id, resource_metainfo, silent: bool = False):
        with self.pool.mock_resource(resource_id, resource_metainfo, silent=silent) as (td, resource_metainfo):
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
def download_gelbooru_images(tags: List[str], max_count: Optional[int] = None, max_total_size: int = 24 * 1024 ** 2,
                             allowed_ratings=_DEFAULT):
    pool = GelbooruWebpDataPool()
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

    with TemporaryDirectory() as td:
        image_dir = os.path.join(td, 'images')
        os.makedirs(image_dir, exist_ok=True)

        exist_ids = set()
        pipe = DownloadImagePipe(pool, image_dir)
        image_files = []
        current_size = 0
        with pipe.batch_retrieve(query) as session:
            for i, item in enumerate(session):
                item: PipeItem
                if item.id not in exist_ids:
                    if current_size + os.path.getsize(item.data) > max_total_size:
                        break

                    image_files.append((item.id, item.data))
                    exist_ids.add(item.id)
                    current_size += os.path.getsize(item.data)
                    if max_count is not None and len(image_files) >= max_count:
                        break

        filename = f'{"__".join(map(_tag_normalize, tags))}__{datetime.now().strftime("%Y%m%d%H%M%S%f")}.zip'
        file_count = os.listdir(image_dir)
        package_file = os.path.join(td, filename)
        current_size = 0
        with zipfile.ZipFile(package_file, 'w') as zf:
            for _, img_file in image_files:
                if (current_size + os.path.getsize(img_file)) < max_total_size:
                    zf.write(img_file, os.path.basename(img_file))

        yield file_count, package_file


if __name__ == '__main__':
    pprint(query_gelbooru_images(['surtr_(arknights)'], count=4))
