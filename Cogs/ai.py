import os
import asyncio
import aiohttp

from openai import OpenAI
from openai import AsyncOpenAI  # Assuming AsyncOpenAI is the correct import from your module


import aiohttp
import logging
import traceback

from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed, sdxl, primary_color

from urllib.request import urlopen, urlretrieve







class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.huggingface_url = 'https://api-inference.huggingface.co/models/ehristoforu/dalle-3-xl-v2'
        self.api_key = os.getenv("api_key")
        self.error_custom_embed = error_custom_embed

         
    async def generate_image(self, prompt: str) -> bytes:
        openai = OpenAI(
        api_key = self.api_key,
        base_url = "http://45.139.50.97:6077/v1"
        )
        response = openai.images.generate(
            prompt=prompt,
            model="lumage-1"
        )
        image_url = response.data[0].url
        print(response.data[0].url)
        return image_url

    @commands.command(name='imagine', description="Generate an image", aliases=['i'])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
     try:
      async with ctx.typing():

        # Send initial message
        message = await ctx.reply('> **Please wait while I genrate your prompt...**')

        # Generate image
        image = await self.generate_image(prompt)
        
        # Create embed
        embed = discord.Embed(description=f'**Prompt:** ```{prompt}```', color=primary_color())
        embed.set_image(url=str(image))
        embed.set_footer(text=f'Thanks for using {self.bot.user.name} | Inspired by alphast101')
        
        # Update message
        await message.edit(content='', embed=embed)

     except Exception as e:
        await ctx.send(f"An error occurred: {e}")

        
        
      
        
def setup(bot):
    bot.add_cog(Ai(bot))
