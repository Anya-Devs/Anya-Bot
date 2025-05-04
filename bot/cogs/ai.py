import os
from datetime import datetime

from PIL import Image, ImageSequence
from openai import AsyncOpenAI

from utils.cogs.ai import *
from imports.discord_imports import *
from imports.log_imports import logger
from data.const import primary_color

class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.OPENAI_KEY = os.getenv("OPENAI_KEY")
        self.HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
        self.queue = []

        if not self.OPENAI_KEY:
            raise ValueError("API key is not set in environment variables.")

        self.openai_client = AsyncOpenAI(
            api_key=self.OPENAI_KEY,
            base_url="https://api.naga.ac/v1",
        )
        self.image_gen = Image.ImageGenerator()
    
    @commands.command(name="imagine", description="Generate an image", aliases=["i"])
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        if ctx.author.id in self.queue:
            await ctx.send(Ai_Text.GENERATING_IMAGE.format(mention=ctx.author.mention))
            return

        self.queue.append(ctx.author.id)

        try:
            async with ctx.typing():
                custom_prompt = f"{prompt}"
                output_path = await self.image_gen.generate_image_sync(custom_prompt)

                new_file = self.image_gen.output_dir / "1.png"
                if new_file.exists():
                    new_file.unlink()
                if output_path is None:
                    await ctx.reply(Ai_Text.ERROR_GENERATING_PROMPT)
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
            await ctx.send(Ai_Text.ERROR_OCCURRED.format(error=e))
        finally:
            self.queue.remove(ctx.author.id)

    @commands.command(name="vision", description="Generate a vision-based response", aliases=["v"])
    async def vision_command(self, ctx, image_url: str = None):
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
                return Ai_Text.VISION_ERROR.format(error=e)

        try:
            prompt = Ai_Text.GENERATE_VISION_PROMPT
            async with ctx.typing():
                message = await ctx.reply(Ai_Text.THINKING_MESSAGE, mention_author=False)

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
                            await message.edit(content=Ai_Text.NO_IMAGE_URL_IN_REFERENCE)
                            return
                    elif ctx.message.embeds:
                        embed = ctx.message.embeds[0]
                        if embed.thumbnail and embed.thumbnail.url:
                            image_url = embed.thumbnail.url
                        elif embed.image and embed.image.url:
                            image_url = embed.image.url
                    else:
                        await message.edit(content=Ai_Text.IMAGE_URL_NOT_FOUND)
                        return

                response = await vision(image_url, prompt)
                embed = discord.Embed(
                    description=Ai_Text.VISION_DESCRIPTION.format(mention=ctx.author.mention, response=response),
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
            await message.edit(content=Ai_Text.ERROR_OCCURRED.format(error=e))

def setup(bot):
    bot.add_cog(Ai(bot))
