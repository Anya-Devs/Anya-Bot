import aiohttp
import discord
from discord.ext import commands
from discord.ui import Button, View

from Imports.discord_imports import *
from Data.const import primary_color


class Recommendation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.JIKAN_API_URL = "https://api.jikan.moe/v4/random/anime"

    async def fetch_random_anime(self):
        """Fetches a random anime from the Jikan API."""
        async with aiohttp.ClientSession() as session:
            async with session.get(self.JIKAN_API_URL) as response:
                if response.status == 200:
                    return await response.json()
                return None

    @staticmethod
    def get_image_url(images):
        """Fetches the image URL from the API response."""
        size_order = ["large", "medium", "small"]
        for size in size_order:
            image_url = images.get("jpg", {}).get(f"{size}_image_url")
            if image_url:
                return image_url
        for size in size_order:
            image_url = images.get("webp", {}).get(f"{size}_image_url")
            if image_url:
                return image_url
        return None

    async def update_anime_embed(self, message, anime_data):
        """Updates the anime recommendation embed."""
        if anime_data:
            anime = anime_data['data']
            anime_title = anime['title']
            anime_description = anime.get(
                "synopsis", "> <:anya_angy:1268976144548630608> Synopsis not available"
            )

            # Prepare the additional fields for the embed
            episodes = anime.get('episodes', 'N/A')
            status = anime.get('status', 'N/A')
            genres = ', '.join(genre['name'] for genre in anime.get('genres', []))
            trailer_url = anime.get('trailer', {}).get('url', '')
            score = anime.get('score', 0)  # Default to 0 if None
            mal_id = anime.get('mal_id', None)

            # Ensure the score is not None and handle it
            if score is None:
                score = 0

            # Create the embed
            embed = discord.Embed(
                title=f"{anime_title}",
                description=anime_description,
                color=primary_color()
            )

            # Add extra fields to the embed
            embed.add_field(
                name=" ",
                value=(
                    f"**Episodes:** `{episodes}`\n"
                    f"**Status:** `{status}`\n"
                    f"**Genres:** `{genres}`\n"
                    f"{'**Trailer:** ' + f'``{trailer_url}``' if trailer_url else ''}\n"
                    f"```py\nScore: {score:>3} (out of 10)\n"
                    f"{'▰' * int(score * 10 / 10)}{'▱' * (10 - int(score * 10 / 10))}```"
                ),
                inline=False
            )

            image_url = self.get_image_url(anime["images"])
            embed.set_image(url=image_url)

            # Add footer to the embed
            embed.set_footer(text="Anime Recommendation")

            # Create a button for reviews (link button to MyAnimeList reviews)
            if mal_id:
                reviews_button = Button(
                    label="View Reviews",
                    style=discord.ButtonStyle.link,
                    url=f"https://myanimelist.net/anime/{mal_id}/reviews"
                )
            else:
                reviews_button = Button(
                    label="View Reviews",
                    style=discord.ButtonStyle.secondary,
                    disabled=True
                )

            # Create a "Random Anime" button to fetch another random anime
            random_button = Button(
                label="Get Another Random Anime",
                style=discord.ButtonStyle.primary,
                custom_id="random_anime_button"
            )

            # Create a view with the review button and random anime button
            view = View()
            view.add_item(reviews_button)
            view.add_item(random_button)

            # Add the callback to the random anime button
            random_button.callback = self.random_anime_callback

            # Edit the message with the new embed and buttons
            await message.edit(embed=embed, view=view)

        else:
            await message.edit(content="Sorry, I couldn't fetch a random anime at the moment.")

    async def random_anime_callback(self, interaction: discord.Interaction):
        """Callback for the random anime button."""
        anime_data = await self.fetch_random_anime()

        # Update the embed with the new anime data
        await self.update_anime_embed(interaction.message, anime_data)
        await interaction.response.defer()

    @commands.command(name="anime_recommend", aliases=["ar"])
    async def recommend_anime(self, ctx):
        """Fetches a random anime and sends the recommendation."""
        anime_data = await self.fetch_random_anime()

        # Send the initial message with the anime embed and random button
        anime_message = await ctx.reply(embed=None, mention_author=False)
        await self.update_anime_embed(anime_message, anime_data)
