
import os
import asyncio
from pathlib import Path
from datetime import datetime
from openai import AsyncOpenAI  

from huggingface_hub import InferenceClient


from Imports.discord_imports import *
from Imports.log_imports import logger
from Data.const import error_custom_embed, primary_color


class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_key = os.getenv("OPENAI_KEY")
        self.h_api_key =  os.getenv("HUGGINGFACE_API_KEY")

        if not self.api_key:
            raise ValueError("API key is not set in environment variables.")

        self.openai_client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.naga.ac/v1",
        )
        self.image_gen = ImageGenerator(self.h_api_key)  
        self.error_custom_embed = error_custom_embed

   
    @commands.command(name="imagine", description="Generate an image", aliases=["i"])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        try:
            style_list = ["color-detailed stlye", "shadow-detailed stlye", "hyper-detailed stlye"]

            generated_files = []

            async with ctx.typing():
                for idx, punct in enumerate(style_list, start=1):
                    custom_prompt = f"{punct}: {prompt} "
                    output_path = await asyncio.to_thread(
                        self.image_gen.generate_image_sync, custom_prompt
                    )

                    new_file = self.image_gen.output_dir / f"{idx}.png"
                    if new_file.exists():
                        new_file.unlink()
                    output_path.rename(new_file)
                    generated_files.append(new_file)

                embeds = []
                files = []
                for idx, file_path in enumerate(generated_files, start=1):
                    file = discord.File(str(file_path), filename=f"{idx}.png")
                    files.append(file)

                    description = f"**Prompt:** ```{prompt}```"
                    embed = discord.Embed(
                        description=description,
                        color=primary_color(),  
                        timestamp=datetime.now(),
                        url="https://rajtech.me"
                    )
                    embed.set_image(url=f"attachment://{idx}.png")
                    embed.set_footer(
                        icon_url=ctx.author.avatar, text=f"Requested by {ctx.author}"
                    )
                    embeds.append(embed)

            await ctx.reply(embeds=embeds, files=files)
        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

    @commands.command(
        name="vision", description="Generate a vision-based response", aliases=["v"])
    async def vision_commmand(self, ctx, image_url: str = None):
        async def vision(image_link: str, prompt: str = " ") -> str:
            try:
                response = await self.openai_client.chat.completions.create(
                    model="gemini-1.5-pro",  
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
            prompt = "in a tone of innocent, and slightly naive (you are anya from spx x family : DO NOT TALK ABOUT PENUTS are make refrences to the show) describe the image you see and have turthful opionins"
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


class ImageGenerator:
    def __init__(self, api_key: str):
        
        self.client = InferenceClient(
            "black-forest-labs/FLUX.1-dev", token=api_key)
        self.output_dir = Path("Data/commands/ai/images")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        print("Using Hugging Face model via InferenceClient...")

    def generate_image_sync(
        self, prompt: str, width: int = 1344, height: int = 768
    ) -> Path:
        """Generates an image synchronously using Hugging Face InferenceClient."""
        try:
            print(f"Generating image for prompt: {prompt}")
            negative_prompt = "longbody, lowres, bad anatomy, bad hands, missing fingers, pubic hair, extra digit, fewer digits, cropped, worst quality, low quality, very displeasing"

            
            image = self.client.text_to_image(prompt)

            print(image)
            
            output_path = self.output_dir / f"generated_image.png"
            image.save(output_path)
            print(f"Image saved at: {output_path}")
            return output_path

        except Exception as e:
            print(f"Error during image generation: {e}")
            raise e

    async def generate_image(self, prompt: str) -> str:
        """Generates an image asynchronously."""
        try:
            output_path = await asyncio.to_thread(self.generate_image_sync, prompt)
            return str(output_path)
        except Exception as e:
            print(f"Failed to generate image: {e}")
            raise Exception(f"Failed to generate image: {e}")



def setup(bot):
    bot.add_cog(Ai(bot))
