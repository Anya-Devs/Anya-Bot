import os, asyncio, base64,tempfile
from io import BytesIO
from pathlib import Path
from datetime import datetime

import aiohttp
import numpy as np
import cv2 as cv
from PIL import Image, ImageSequence
from openai import AsyncOpenAI

from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed, primary_color
from utils.ai import Processor, ImageGenerator




class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.OPENAI_KEY = os.getenv("OPENAI_KEY")
        self.HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

        if not self.OPENAI_KEY:
            raise ValueError("API key is not set in environment variables.")

        self.openai_client = AsyncOpenAI(
            api_key=self.OPENAI_KEY,
            base_url="https://api.naga.ac/v1",
        )
        self.image_gen = ImageGenerator()
        self.detect = Processor(
            face_model=('Data/commands/ai/detect/deploy.prototxt', 'Data/commands/ai/detect/res10_300x300_ssd_iter_140000.caffemodel'),
            body_model=('Data/commands/ai/detect/yolov4.cfg', 'Data/commands/ai/detect/yolov4.weights')
        )

    @commands.command()
    async def detect(self, ctx, url: str):
        async with ctx.typing():
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    if resp.status != 200:
                        await ctx.send("Failed to fetch image from the provided URL.")
                        return
                    content_type = resp.headers.get("Content-Type", "").lower()
                    data = await resp.read()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".gif" if "gif" in content_type else ".png") as tmp_file:
            tmp_file.write(data)
            temp_path = tmp_file.name

        is_gif = "gif" in content_type
        output_bytes = BytesIO()

        try:
            if is_gif:
                pil_image = Image.open(temp_path)
                frames = [frame.copy().convert("RGB") for frame in ImageSequence.Iterator(pil_image)]
                durations = [frame.info.get("duration", 100) for frame in ImageSequence.Iterator(pil_image)]

                processed_frames, durations = await self.detect.process_gif(frames, durations)
                processed_pil = [Image.fromarray(cv.cvtColor(f, cv.COLOR_BGR2RGB)) for f in processed_frames]
                processed_pil[0].save(output_bytes, format="GIF", save_all=True, append_images=processed_pil[1:], duration=durations, loop=0)

                filename = "detection_result.gif"
            else:
                pil_image = Image.open(temp_path).convert("RGB")
                np_image = cv.cvtColor(np.array(pil_image), cv.COLOR_RGB2BGR)
                processed_np = await asyncio.to_thread(self.detect.process_frame, np_image)
                processed_pil = Image.fromarray(cv.cvtColor(processed_np, cv.COLOR_BGR2RGB))
                processed_pil.save(output_bytes, format="PNG")

                filename = "detection_result.png"

            output_bytes.seek(0)
            await ctx.send(
                embed=Embed(title="Detection Result", description="Detected faces and bodies:"),
                file=File(fp=output_bytes, filename=filename)
            )

        except Exception as e:
            await ctx.send(f"Error during processing: {e}")
        finally:
            os.remove(temp_path)



    @commands.command(name="imagine", description="Generate an image", aliases=["i"])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
     if ctx.author.id in self.queue:
        await ctx.send(f"{ctx.author.mention}, you're already in the process of generating an image. Please wait until it finishes.")
        return
    
     self.queue.append(ctx.author.id)
    
     try:
        async with ctx.typing():
            custom_prompt = f"{prompt}"
            output_path = await self.image_gen.generate_image_sync(custom_prompt)

            new_file = self.image_gen.output_dir / "1.png"
            if new_file.exists():
                new_file.unlink()
            if output_path == None:
                await ctx.reply("❌ Error generating prompt, please try again.")
                return
            output_path.rename(new_file)

            file = discord.File(str(new_file), filename="1.png")
            description = f"**Prompt:** ```{prompt}```"
            embed = discord.Embed(
                description=description,
                color=primary_color(),
                timestamp=datetime.now(),
                url="https://rajtech.me"
            )
            embed.set_image(url="attachment://1.png")
            embed.set_footer(
                icon_url=ctx.author.avatar, text=f"Requested by {ctx.author}"
            )

            await ctx.reply(embed=embed, file=file)
    
     except Exception as e:
        await ctx.send(f"An error occurred: {e}")
     finally:
        self.queue.remove(ctx.author.id)

    @commands.command(
        name="vision", description="Generate a vision-based response", aliases=["v"])
    async def vision_commmand(self, ctx, image_url: str = None):
        async def vision(image_link: str, prompt: str = " ") -> str:
            try:
                response = await self.openai_client.chat.completions.create(
                    model="gemini-2.0-flash-lite",  
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
            prompt = "in a tone of innocent, and slightly naive (you are anya forger from spx x family : DO NOT TALK ABOUT PENUTS are make refrences to the show) describe the image you see and have turthful opionins"
            async with ctx.typing():
                message = await ctx.reply(
                    "> **Thinking ... :thought_balloon:**",
                    mention_author=False,
                )

                if not image_url:
                    if ctx.message.attachments:
                        image_url = ctx.message.attachments[0].url
                    elif ctx.message.reference:
                        ref_message = await ctx.channel.fetch_message(
                            ctx.message.reference.message_id
                        )
                        if ref_message.attachments:
                            image_url = ref_message.attachments[0].url
                        elif ref_message.embeds:
                            
                            embed = ref_message.embeds[0]
                            if embed.thumbnail and embed.thumbnail.url:
                                image_url = embed.thumbnail.url
                            elif embed.image and embed.image.url:
                                image_url = embed.image.url
                        else:
                            await message.edit(
                                content="No image URL found in the referenced message. Please provide an image URL or attach an image to your message."
                            )
                            return
                    elif ctx.message.embeds:
                        
                        embed = ctx.message.embeds[0]
                        if embed.thumbnail and embed.thumbnail.url:
                            image_url = embed.thumbnail.url
                        elif embed.image and embed.image.url:
                            image_url = embed.image.url
                    else:
                        await message.edit(
                            content="No image URL found. Please provide an image URL, attach an image to your message, or reply to a message with an image."
                        )
                        return

                logger.info(f"Image URL: {image_url}")
                logger.info(f"Prompt: {prompt}")

                response = await vision(image_url, prompt)
                embed = discord.Embed(
                    description=f"-# Asked by {ctx.author.mention}\n\n**Vision** - {response}",
                    color=primary_color(),
                )
                embed.set_thumbnail(url=image_url)
                embed.set_footer(
                    icon_url=self.bot.user.avatar,
                    text=f"Thanks for using {self.bot.user.name}",
                )
                await message.delete()
                await ctx.reply(embed=embed)
        except Exception as e:
            await message.edit(content=f"An error occurred: {e}")




def setup(bot):
    bot.add_cog(Ai(bot))