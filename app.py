import logging
import os

import discord
from discord.ext import commands

from maid_assistant.calc import safe_eval

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


@bot.event
async def on_ready():
    logging.info(f'Bot logged in as {bot.user}')


if __name__ == '__main__':
    bot.run(os.environ['DC_BOT_TOKEN'])
