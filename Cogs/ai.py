import os
import asyncio
import aiohttp


from PIL import Image
from io import BytesIO
from pathlib import Path


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
        
        self.api_key = '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'
        self.huggingface_url = 'https://api-inference.huggingface.co/models/ehristoforu/dalle-3-xl-v2'
        
        self.error_custom_embed = error_custom_embed

    async def update_progress_bar(self, message, total_steps, interval=0.5):
     progress_template = "Generating image: {progress_bar} {percent}%"
     step_time = 0.1  # Adjust this based on estimated processing time per step
     current_percent = 0
    
     for step in range(total_steps + 1):
        progress_bar = '█' * step + '▒' * (total_steps - step)
        percent = int((step / total_steps) * 100)
        
        if percent > current_percent:
            current_percent = percent
            await message.edit(content=progress_template.format(progress_bar=progress_bar, percent=percent))
        
        await asyncio.sleep(step_time)

     await message.edit(content=progress_template.format(progress_bar='█' * total_steps, percent=100))
            
    async def generate_image(self, prompt: str, progress_callback=None) -> str:
     headers = {
        "Authorization": f"Bearer {self.api_key}"
     }
     payload = {
        "inputs": prompt,
        "options": {
            "wait_for_model": True
        }
     }

     max_retries = 5
     backoff_factor = 2
     # Create the directory if it doesn't exist
     output_dir = Path("Data/Image/Ai")
     output_dir.mkdir(parents=True, exist_ok=True)

     # Adjust total_steps based on estimated processing time
     total_steps = 10  # Adjust as needed
     step_time = 1.0  # Adjust based on estimated processing time per step

     for attempt in range(max_retries):
        async with aiohttp.ClientSession() as session:
            async with session.post(self.huggingface_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    image_bytes = await response.read()  # Get image bytes
                    
                    # Save image bytes to file
                    output_path = output_dir / "generated_image.png"
                    with open(output_path, "wb") as image_file:
                        image_file.write(image_bytes)
                    
                    # Update progress if callback is provided
                    if progress_callback:
                        await progress_callback(total_steps, step_time)
                    
                    return str(output_path)  # Return the file path
                elif response.status == 500:
                    error_message = await response.text()
                    if "CUDA out of memory" in error_message:
                        # Wait before retrying
                        if attempt < max_retries - 1:
                            wait_time = backoff_factor ** attempt
                            await asyncio.sleep(wait_time)
                        else:
                            raise Exception(f"Failed to generate image: {response.status} - {error_message}")
                    else:
                        raise Exception(f"Failed to generate image: {response.status} - {error_message}")
                else:
                    raise Exception(f"Failed to generate image: {response.status} - {await response.text()}")
    
    async def progress_callback(total_steps, step_time):
     progress_template = "Generating image: {progress_bar} {percent}%"
     for step in range(total_steps + 1):
        progress_bar = '█' * step + '▒' * (total_steps - step)
        percent = int((step / total_steps) * 100)
        print(progress_template.format(progress_bar=progress_bar, percent=percent))
        await asyncio.sleep(step_time)
                        
    
    @commands.command(name='imagine', description="Generate an image", aliases=['i'])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        try:
            async with ctx.typing():
                # Send initial message with progress bar
                message = await ctx.reply('> **Please wait while I generate your prompt...**\nGenerating image: ▒▒▒▒▒▒▒▒▒▒ 0%')

                # Create a coroutine to update the progress bar
                progress_task = asyncio.create_task(self.update_progress_bar(message, total_steps=10, interval=1))
                
                # Generate image with progress callback
                image_path = await self.generate_image(prompt, progress_callback=lambda step, total: progress_task)
                
                # Cancel the progress bar update task when done
                progress_task.cancel()
                
                # Create discord.File
                image_file = discord.File(image_path, filename="generated_image.png")

                
                # Create embed
                embed = discord.Embed(description=f'Requested by {ctx.author.mention}\nPrompt:  {prompt}', color=primary_color())
                embed.set_image(url="attachment://generated_image.png")
                embed.set_footer(icon_url=self.bot.user.avatar.url, text=f'Thanks for using {self.bot.user.name} | Inspired by alphast101')
                
                # Update message
                await message.edit(content='', embed=embed, attachments=[image_file])

        except Exception as e:
            await ctx.send(f"An error occurred: {e}")
            
            
    @commands.command(name='vision', description="Generate a vision-based response", aliases=['v'])
    async def vision_command(self, ctx, image_url: str = None):
        async def vision(image_link: str, prompt: str = ' ') -> str:
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

        try:

            prompt = 'Describe the [image] in a way that sounds like Anya from "Spy x Family," (because you are Anya) with a childish tone and clear explanation. Assume your audience is eager to learn but has limited prior knowledge on the topic. Use childlike opinions and feelings about the image.'

            async with ctx.typing():
                message = await ctx.reply('> **Please wait while I analyze the image...**')
                
                # Check for image URL in command arguments or attachments
                if not image_url:
                    if ctx.message.attachments:
                        image_url = ctx.message.attachments[0].url
                    elif ctx.message.reference:
                        ref_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                        if ref_message.attachments:
                            image_url = ref_message.attachments[0].url
                        else:
                            await message.edit(content="No image URL found in the referenced message. Please provide an image URL or attach an image to your message.")
                            return
                    else:
                        await message.edit(content="No image URL found. Please provide an image URL, attach an image to your message, or reply to a message with an image.")
                        return


                # Log the image URL and prompt for debugging
                logger.info(f"Image URL: {image_url}")
                logger.info(f"Prompt: {prompt}")

                # Download the image and convert it to bytes

                response = await vision(image_url, prompt)
                embed = discord.Embed(description=f'Asked by {ctx.author.mention}\n\nVision - {response}', color=primary_color())
                embed.set_thumbnail(url=image_url)
                embed.set_footer(icon_url=self.bot.user.avatar, text=f'Thanks for using {self.bot.user.name} | Inspired by alphast101')
                await message.edit(content='', embed=embed)
        except Exception as e:
            await message.edit(content=f"An error occurred: {e}")

      
        
def setup(bot):
    bot.add_cog(Ai(bot))
