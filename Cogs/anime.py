# Run Request
import asyncio
import requests
import aiohttp

# Local
from Imports.log_imports import *
from Imports.discord_imports import *

class Anime(commands.Cog):
  def __init__(self, bot):
        self.bot = bot

  @commands.command(name='anime')
  async def anime_search(self, ctx, *, query=None):
        if query is None:
            embed = discord.Embed(description=f"{ctx.author.display_name.title()}, can you try entering the `name` of the anime you're looking for?")
            message = await ctx.reply(embed=embed)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                user_message = await self.bot.wait_for('message', timeout=60, check=check)
                await message.delete()

                if not user_message.content.strip():
                    raise ValueError("Anime title cannot be empty")

                query = user_message.content.strip()
                await user_message.delete()

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(description="Time's Up! You didn't provide an anime title for me to look up.", color=discord.Color.red())
                await message.edit(embed=timeout_embed)
                return

            except ValueError as e:
                error_embed = discord.Embed(description=f"Error: {str(e)}", color=discord.Color.red())
                await message.edit(embed=error_embed)
                return

        url = f'https://api.jikan.moe/v4/anime?q={query}'

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    anime_data = await response.json()

            current_index = 0
            current_page = 0

            view = self.AnimeView(anime_data, current_index, current_page)
            embed = await view.update_embed()
            message = await ctx.reply(embed=embed, view=view)

        except aiohttp.ClientError as e:
            logging.error(f"An HTTP error occurred: {e}")
            await ctx.send(f"An HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            await ctx.send(f"An unexpected error occurred: {e}")

  class AnimeButton(discord.ui.Button):
        def __init__(self, label, style, custom_id, anime_data, current_index, current_page, max_pages):
            super().__init__(label=label, style=style, custom_id=custom_id)
            self.anime_data = anime_data
            self.current_index = current_index
            self.current_page = current_page
            self.max_pages = max_pages

        async def callback(self, interaction: discord.Interaction):
            if self.custom_id == "previous":
                self.current_page -= 1
            elif self.custom_id == "next":
                self.current_page += 1

            # Ensure that the page index is within bounds
            self.current_page = max(0, min(self.current_page, self.max_pages))

            # Update the current index based on the current page
            self.current_index = self.current_page

            # Create a new AnimeView with the updated page
            view = Anime.AnimeView(self.anime_data, self.current_index, self.current_page)
            embed = await view.update_embed()
            await interaction.response.edit_message(embed=embed, view=view)

  class AnimeView(discord.ui.View):
        def __init__(self, anime_data, current_index, current_page):
            super().__init__(timeout=200)
            self.anime_data = anime_data
            self.current_index = current_index
            self.current_page = current_page
            self.max_pages = len(anime_data['data']) - 1
            self.update_buttons()

        def update_buttons(self):
            self.clear_items()
            if self.current_page > 0:
                self.add_item(Anime.AnimeButton("Previous", discord.ButtonStyle.primary, "previous", self.anime_data, self.current_index, self.current_page, self.max_pages))
            if self.current_page < self.max_pages:
                self.add_item(Anime.AnimeButton("Next", discord.ButtonStyle.primary, "next", self.anime_data, self.current_index, self.current_page, self.max_pages))

        async def update_embed(self):
            anime = self.anime_data['data'][self.current_index]
            embed = discord.Embed(title=anime['title'])

            thumbnail_url = self.get_image_url(anime['images'])
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            embed.add_field(
                name=" ",
                value=f"**Episodes:** `{anime['episodes']}`\n"
                      f"**Status:** `{anime['status']}`\n"
                      f"**Genres:** `{', '.join(genre['name'] for genre in anime['genres'])}`\n"
                      f"{'**Trailer:** ' + '``' + anime['trailer']['url'] + '``' if anime['trailer']['url'] else ''}\n"
                      f"```py\nScore: {anime['score']:>3} (out of 10)\n"
                      f"{'▰' * int(anime['score'] * 10 / 10)}{'▱' * (10 - int(anime['score'] * 10 / 10))}```",
                inline=False
            )
            embed.description = "{}".format(anime['synopsis'] if anime and anime.get('synopsis') is not None else "> Synopsis not available"
            embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages + 1}")

            return embed

        def get_image_url(self, images):
            size_order = ['large', 'medium', 'small']
            for size in size_order:
                image_url = images.get('jpg', {}).get(f'{size}_image_url')
                if image_url:
                    return image_url
            for size in size_order:
                image_url = images.get('webp', {}).get(f'{size}_image_url')
                if image_url:
                    return image_url
            return None

def setup(bot):
    bot.add_cog(Anime(bot))

    
