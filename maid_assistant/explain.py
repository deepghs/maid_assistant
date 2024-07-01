import io
import json
import logging
import os
import re
from typing import Optional

from hbutils.string import ordinalize
from requests import JSONDecodeError
from rich.errors import MarkupError
from waifuc.utils import srequest

from maid_assistant.utils import get_openai_client, get_llm_default_model, get_danbooru_session


def ask_chatgpt(message: str, lang: str = 'english', model_name: Optional[str] = None):
    client = get_openai_client()
    model_name = model_name or get_llm_default_model()

    _system_text = f"""
I have an anime image dataset that contains many image labels. 
When I provide an image label, containing its name and its wiki description text, 
you need to translate the label into explicit {lang}, as accurate as you can, as provide the {lang} description in a paragraph.
Do not provide any additional information, so that the script can process in bulk.
Do not be too long, save some tokens for me!!!
Do not have multiple lines directly in description text!!! If some line breaks are necessary, just use text '<br>' to replace the line break characters. 
If some useful links are given in the original description text, select some most important ones and put them into the answer description.
You have to follow the following format, like this example

I Ask:

```
## Tag '1girl'

Tag: 1girl
Description: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

## Mentioned Tags Information

### Mentioned Tag 1

xxxxxxxxxxx

### Mentioned Tag 2

xxxxxxxxxxx

...
```

You answer:
Tag: <Translated tag name in {lang}>
Description: <{lang} description>
"""
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {'role': 'system', 'content': _system_text},
            {"role": "user", "content": message},
        ],
    )
    return response.choices[0].message.content.strip()


def _get_desc_by_wiki_data(data, tag=None, use_other_names: bool = False):
    with io.StringIO() as sf:
        print(f'Tag: {tag or data["title"]}', file=sf)
        if use_other_names and data['other_names']:
            print(f'Other Names: {", ".join(data["other_names"])}', file=sf)
        desc = data['body']
        if desc:
            print(f'Description: {desc}', file=sf)
        else:
            print('No description found.', file=sf)
        return bool(desc), sf.getvalue()


def _extract_wiki_titles(wiki_text):
    pattern = r'\[\[(.*?)(?:\|(.*?))?\]\]'
    links = re.findall(pattern, wiki_text)
    extracted_wiki_titles = []
    for link in links:
        if '|' in link[0]:
            page, text = link[0].split('|', 1)
        else:
            page, text = link[0], (link[1] or link[0])
        extracted_wiki_titles.append(page.strip())

    return extracted_wiki_titles


def _get_wiki_info_by_title(title: str):
    session = get_danbooru_session()
    resp = srequest(session, 'GET', f'https://danbooru.donmai.us//wiki_pages.json',
                    params={'search[title_normalize]': title}, raise_for_status=False)

    if resp.json():
        return resp.json()[0]
    else:
        return None


def _get_desc(tag: str, use_other_names: bool = False):
    session = get_danbooru_session()
    resp = srequest(session, 'GET', f'https://danbooru.donmai.us/wiki_pages/{tag}.json', raise_for_status=False)
    if resp.status_code == 404:
        return False, f'Tag: {tag}\nNo description found.'
    else:
        resp.raise_for_status()
        try:
            _ = resp.json()
        except (JSONDecodeError, json.JSONDecodeError):
            return False, f'Tag: {tag}\nNo description found.'

        title_attachments = []
        if resp.json()['body']:
            exist_related_tag_titles = {resp.json()['title']}
            tag_titles = _extract_wiki_titles(resp.json()['body'])
            for title in tag_titles:
                title_data = _get_wiki_info_by_title(title)
                if title_data and title_data['title'] not in exist_related_tag_titles:
                    title_attachments.append((title, title_data))
                    exist_related_tag_titles.add(title_data['title'])

        with io.StringIO() as sf:
            found, text = _get_desc_by_wiki_data(resp.json(), tag=tag, use_other_names=use_other_names)
            print(f'## Tag {tag!r}', file=sf)
            print(f'', file=sf)
            print(text, file=sf)
            print(f'', file=sf)

            if title_attachments:
                print(f'## Mentioned Tags Information', file=sf)
                print(f'', file=sf)
                print(f'The following parts are attachment tag '
                      f'information mentioned in tag {tag!r}s description body.', file=sf)
                print(f'', file=sf)
                for title, title_data in title_attachments:
                    title_found, title_text = _get_desc_by_wiki_data(
                        title_data, tag=title, use_other_names=False)
                    if title_found:
                        print(f'### {title}', file=sf)
                        print(f'', file=sf)
                        print(title_text, file=sf)
                        print(f'', file=sf)

            return found, sf.getvalue()


def _raw_explain(tag: str, lang: str = 'english', use_other_names: bool = False):
    tag_found, desc = _get_desc(tag, use_other_names=use_other_names)
    desc_lines = desc.splitlines(keepends=False)
    if len(desc_lines) > 400:
        desc_lines = desc_lines[:400] + ['(... more lines)']
    try:
        logging.info(f'Desc of tag {tag!r}:\n{os.linesep.join(desc_lines)}')
    except MarkupError:
        pass
    result = ask_chatgpt(desc, model_name='gpt-4o', lang=lang)
    logging.info(f'Answer: {result}')
    res_lines = result.strip().splitlines(keepends=False)
    if len(res_lines) != 2:
        return None
    else:
        first_line = res_lines[0]
        l, content = first_line.split(':', maxsplit=1)
        if l.strip().lower() != 'tag':
            return None
        translated = content.strip()

        second_line = res_lines[1]
        l, content = second_line.split(':', maxsplit=1)
        if l.strip().lower() != 'description':
            return None, None
        desc = content.strip().replace('<br>', os.linesep)

        with io.StringIO() as sf:
            print(f'## {translated}', file=sf)
            print(f'', file=sf)

            if not tag_found:
                print(f'ATTENTION: Tag or wiki information not found for tag `{tag}`, '
                      f'so this part of the explanation is automatically generated by LLM, '
                      f'and **its accuracy is not worthy of high trust**.', file=sf)
                print(f'', file=sf)

            print(f'{desc}', file=sf)
            print(f'', file=sf)

            return sf.getvalue()


def tag_explain(tag: str, lang: str = 'english', use_other_names: bool = False, max_retry: int = 5):
    i = 0
    while True:
        i += 1
        logging.info(f'{ordinalize(i)} attempt to explain tag {tag!r} in {lang} ...')
        retval = _raw_explain(tag, lang=lang, use_other_names=use_other_names)
        if retval is not None:
            return retval

        if i >= max_retry:
            raise ValueError(f'Unable to explain {tag!r} ...')
