import logging
import os
import re

import discord
from discord.ext import commands
from hbutils.system import TemporaryDirectory

from maid_assistant.calc import safe_eval
from maid_assistant.sites.danbooru import query_danbooru_images

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
    await ctx.send(ret_text)


@bot.command(name='danbooru',
             help='Search danbooru images')
async def danbooru_command(ctx, *, tags_text: str):
    tags = list(filter(bool, re.split(r'\s+', tags_text)))
    with TemporaryDirectory() as td:
        embed = discord.Embed(
            title="Danbooru Images",
            description=f"This is the search result of tags: {tags!r}",
            color=0x00ff00
        )
        files = []
        for id_, image in query_danbooru_images(tags, count=10):
            dst_file = os.path.join(td, f'{id_}.webp')
            image.save(dst_file, quality=90)
            files.append(discord.File(dst_file, filename=os.path.basename(dst_file)))

        await ctx.send(embed=embed, files=files)


@bot.event
async def on_ready():
    logging.info(f'Bot logged in as {bot.user}')


if __name__ == '__main__':
    bot.run(os.environ['DC_BOT_TOKEN'])
