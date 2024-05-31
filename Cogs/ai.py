import discord
from discord.ext import commands
from openai import AsyncOpenAI  # Assuming AsyncOpenAI is the correct import from your module

class Ai(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='i', description="Generate an image",hidden=True)
    async def imagine(self, ctx: commands.Context, *, prompt: str):
        try:
            # Send initial message
            embed = discord.Embed(title="Generating image...", color=discord.Color.blue())
            message = await ctx.send(embed=embed)

            # Generate image
            image_url = await sdxl(prompt)

            # Edit message with the generated image
            embed.title = "Generated Image"
            embed.set_image(url=image_url)
            await message.edit(embed=embed)

        except Exception as e:
            await ctx.send(f"An error occurred: {e}")

async def sdxl(prompt):
    openai_client = AsyncOpenAI(
        api_key='ng-YgkaT8abn2sWaqZRUmVPzs07BdtrE',  # API key remains the same as provided
        base_url="https://api.naga.ac/v1"
    )

    response = await openai_client.images.generate(
        model="playground-v2.5",  # Using a valid model for image generation
        prompt=prompt,
        n=1,  # images count
        size="1024x1024"  # Standard size for image generation
    )
    return response.data[0].url


def setup(bot):
    bot.add_cog(Ai(bot))
