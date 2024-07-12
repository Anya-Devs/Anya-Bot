import os
import asyncio
import aiohttp

from PIL import Image
from io import BytesIO

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
        self.api_key = os.getenv("api_key")

        self.openai_client =  AsyncOpenAI(api_key = 'ng-YgkaT8abn2sWaqZRUmVPzs07BdtrE', base_url = "https://api.naga.ac/v1")
        self.huggingface_url = 'https://api-inference.huggingface.co/models/ehristoforu/dalle-3-xl-v2'
        
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

        return image_url
    
    async def vision(self, image_link: str, prompt: str = ' ') -> str:
        try:
            response = await self.openai_client.chat.completions.create(
                model="gemini-pro-vision",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {"url": image_link},
                            },
                        ],
                    }
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ouch! Something went wrong! {e}"

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
    
    @commands.command(name='vision', description="Generate a vision-based response", aliases=['v'])
    async def vision_command(self, ctx, image_url: str = None):
        try:
            prompt = 'Describe [image] with clear explanation summary. Assume your audience is eager to learn but you may have limited prior knowledge on the topic.'
            async with ctx.typing():
                message = await ctx.reply('> **Please wait while I analyze the image...**')
                
                # Check for image URL in command arguments or attachments
                if not image_url:
                    if ctx.message.attachments:
                        image_url = ctx.message.attachments[0].url
                    else:
                        await ctx.send("No image URL found. Please provide an image URL or attach an image to your message.")
                        return

                # Log the image URL and prompt for debugging
                logger.info(f"Image URL: {image_url}")
                logger.info(f"Prompt: {prompt}")

                # Download the image and convert it to bytes

                response = await self.vision(image_url, prompt)
                embed = discord.Embed(description=f'**Response:**```{response}```', color=primary_color())
                embed.set_image(url=image_url)
                embed.set_footer(text=f'Thanks for using {self.bot.user.name} | Inspired by alphast101')
                await message.edit(content='', embed=embed)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

      
        
def setup(bot):
    bot.add_cog(Ai(bot))
