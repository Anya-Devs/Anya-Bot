import os
from datetime import datetime
from PIL import Image
from openai import AsyncOpenAI
from utils.cogs.ai import *
from imports.discord_imports import *
from imports.log_imports import logger
from data.local.const import primary_color

class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = []
        self.OPENAI_KEY = os.getenv("OPENAI_KEY")
        self.HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
        if not self.OPENAI_KEY:
            raise ValueError("OPENAI_KEY missing in env.")
        self.openai_client = AsyncOpenAI(api_key=self.OPENAI_KEY, base_url="https://api.naga.ac/v1")
        self.image_gen = Image.ImageGenerator()

    @commands.command(name="imagine", aliases=["i"], description="Generate an image")
    async def imagine(self, ctx: commands.Context, *, prompt: str):
     if ctx.author.id in self.queue:
        return await ctx.send(Ai_Text.IMAGINE_ALREADY_IN_QUEUE.format(ctx.author.mention))
     self.queue.append(ctx.author.id)
     try:
        async with ctx.typing():
            output_path, config_json = await self.image_gen.generate_image_sync(prompt)
            if not output_path:
                return await ctx.reply(Ai_Text.ERROR_GENERATING_PROMPT)
            final_path = self.image_gen.output_dir / "1.png"
            if final_path.exists():
                final_path.unlink()
            output_path.rename(final_path)
            embed = discord.Embed(
                description=f"**Prompt:** ```{prompt}```",
                color=primary_color(),
                timestamp=datetime.now(),
                url="https://rajtech.me"
            )
            embed.set_image(url="attachment://1.png")
            embed.set_footer(icon_url=ctx.author.avatar, text=f"Requested by {ctx.author}")
            view = discord.ui.View(timeout=None)

            async def show_config_callback(interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("This isn't your button!", ephemeral=True)
                try:
                    dm = await interaction.user.create_dm()
                    await dm.send("📦 Here's the full configuration used for generation:", file=discord.File(str(final_path), filename="1.png"))
                    for section in config_json.split("\n\n"):
                        embed = discord.Embed(description=f"```json\n{section.strip()}\n```", color=primary_color())
                        await dm.send(embed=embed)
                    await interaction.response.send_message("✅ Sent to your DMs!", ephemeral=True)
                except Exception as e:
                    await interaction.response.send_message(f"Error sending DM: {e}", ephemeral=True)

            btn = discord.ui.Button(label="Show Config", style=discord.ButtonStyle.secondary, custom_id="show_config")
            btn.callback = show_config_callback
            view.add_item(btn)

            await ctx.reply(embed=embed, file=discord.File(str(final_path), filename="1.png"), view=view)
     except Exception as e:
        await ctx.send(Ai_Text.ERROR_GENERATING_PROMPT.format(error=e))
     finally:
        self.queue.remove(ctx.author.id)





    @commands.command(name="vision", aliases=["v"], description="Generate a vision-based response")
    async def vision_command(self, ctx, image_url: str = None):
        prompt, message = Ai_Text.VISION_PROMPT, await ctx.reply(Ai_Text.THINKING_MESSAGE, mention_author=False)
        try:
            if not image_url:
                ref = ctx.message
                if ref.attachments:
                    image_url = ref.attachments[0].url
                elif ref.reference:
                    ref_msg = await ctx.channel.fetch_message(ref.reference.message_id)
                    image_url = next((a.url for a in ref_msg.attachments), None) or next(
                        (e.thumbnail.url if e.thumbnail else e.image.url for e in ref_msg.embeds if e), None)
                elif ref.embeds:
                    embed = ref.embeds[0]
                    image_url = embed.thumbnail.url if embed.thumbnail else embed.image.url
                if not image_url:
                    return await message.edit(content=Ai_Text.IMAGE_URL_NOT_FOUND)

            response = await Vision._generate_vision_response(Ai(self.bot), image_url, prompt)
            embed = discord.Embed(
                description=Ai_Text.VISION_RESPONSE.format(mention=ctx.author.mention, response=response),
                color=primary_color()
            )
            embed.set_thumbnail(url=image_url)
            embed.set_footer(icon_url=self.bot.user.avatar, text=f"Thanks for using {self.bot.user.name}")
            await message.delete()
            await ctx.reply(embed=embed)
        except Exception as e:
            await message.edit(content=Ai_Text.ERROR_GENERATING_PROMPT.format(error=e))
            
def setup(bot): bot.add_cog(Ai(bot))
