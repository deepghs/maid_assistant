import os
import re

import discord
from discord.ext import commands
from ditk import logging
from hbutils.string import plural_word
from hbutils.system import TemporaryDirectory

from maid_assistant.calc import safe_eval
from maid_assistant.explain import tag_explain
from maid_assistant.sites.danbooru import query_danbooru_images

logging.try_init_root(logging.INFO)

intents = discord.Intents.default()
intents.message_content = True
intents.messages = True

bot = commands.Bot(command_prefix='maid ', intents=intents)


@bot.command(name='calc',
             help="Calculate python-based math expression.")
async def calc_command(ctx, *, expression: str):
    logging.info(f'Calculate expression {expression!r} ...')
    try:
        result = safe_eval(expression)
        ret_text = f"Result: {result}"
    except Exception as e:
        ret_text = f'Calculation Error: {e}'
    await ctx.message.reply(ret_text)


@bot.command(name='danbooru',
             help='Search danbooru images')
async def danbooru_command(ctx, *, tags_text: str):
    tags = list(filter(bool, re.split(r'\s+', tags_text)))
    with TemporaryDirectory() as td:
        result = query_danbooru_images(tags, count=10)
        embed = discord.Embed(
            title="Danbooru Images",
            description=f"This is the search result of tags: {tags!r}.\n"
                        f"{plural_word(len(result), 'image')} found in total.\n"
                        f"Powered by [deepghs/danbooru2023-webp-4Mpixel_index](https://huggingface.co/datasets/deepghs/danbooru2023-webp-4Mpixel_index) "
                        f"and [deepghs/cheesechaser](https://github.com/deepghs/cheesechaser).",
            color=0x00ff00
        )
        files = []
        for id_, image in result:
            dst_file = os.path.join(td, f'{id_}.webp')
            image.save(dst_file, quality=90)
            files.append(discord.File(dst_file, filename=os.path.basename(dst_file)))

        await ctx.message.reply(embed=embed, files=files)


async def explain_command_raw(ctx, *, tag: str, lang: str):
    reply_message = await ctx.message.reply(f'Explanation of `{tag}` to {lang} received, generating ...')
    try:
        reply_text = tag_explain(tag, lang, use_other_names=True)
    except Exception as err:
        reply_text = f'Explain error - {err!r}'

    await reply_message.delete()
    await ctx.message.reply(reply_text)


@bot.command(name='explain',
             help='Explain tags in english')
async def explain_en_command(ctx, *, tag: str):
    await explain_command_raw(ctx, tag=tag, lang='english')


@bot.command(name='explain_cn',
             help='Explain tags in chinese')
async def explain_cn_command(ctx, *, tag: str):
    await explain_command_raw(ctx, tag=tag, lang='simplified chinese')


@bot.event
async def on_ready():
    logging.info(f'Bot logged in as {bot.user}')


if __name__ == '__main__':
    bot.run(os.environ['DC_BOT_TOKEN'])
