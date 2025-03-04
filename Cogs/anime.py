import asyncio
import aiohttp
import logging

from Imports.discord_imports import *
from subcogs.anime import Recommendation

logging.basicConfig(
    
    level=logging.ERROR,
    
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",  
)


class Anime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.jikan.moe/v4/anime/"

    @commands.command(name="anime")
    async def anime_search(self, ctx, *, query=None):
        if query is None:
            embed = discord.Embed(
                description=f"{ctx.author.display_name.title()}, can you try entering the `name` of the anime you're looking for?"
            )
            message = await ctx.reply(embed=embed, mention_author=False)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                user_message = await self.bot.wait_for(
                    "message", timeout=60, check=check
                )
                await message.delete()

                if not user_message.content.strip():
                    raise ValueError("Anime title cannot be empty")

                query = user_message.content.strip()
                await user_message.delete()

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    description="Time's Up! You didn't provide an anime title for me to look up.",
                    color=discord.Color.red(),
                )
                await message.edit(embed=timeout_embed)
                return

            except ValueError as e:
                error_embed = discord.Embed(
                    description=f"Error: {str(e)}", color=discord.Color.red()
                )
                await message.edit(embed=error_embed)
                return

        url = f"https://api.jikan.moe/v4/anime?q={query}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    anime_data = await response.json()

            current_index = 0
            current_page = 0

            view = self.AnimeView(anime_data, current_index, current_page)
            embed = await view.update_embed()
            message = await ctx.reply(embed=embed, view=view, mention_author=False)

        except aiohttp.ClientError as e:
            logging.error(f"An HTTP error occurred: {e}")
            await ctx.send(f"An HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            await ctx.send(f"An unexpected error occurred: {e}")

    @commands.command(name="character")
    async def character_search(self, ctx, *, query=None):
        if query is None:
            embed = discord.Embed(
                description=f"{ctx.author.display_name.title()}, can you try entering the `name` of the character you're looking for?"
            )
            message = await ctx.reply(embed=embed, mention_author=False)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                user_message = await self.bot.wait_for(
                    "message", timeout=60, check=check
                )
                await message.delete()

                if not user_message.content.strip():
                    raise ValueError("Character name cannot be empty")

                query = user_message.content.strip()
                await user_message.delete()

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    description="Time's Up! You didn't provide a character name for me to look up.",
                    color=discord.Color.red(),
                )
                await message.edit(embed=timeout_embed)
                return

            except ValueError as e:
                error_embed = discord.Embed(
                    description=f"Error: {str(e)}", color=discord.Color.red()
                )
                await message.edit(embed=error_embed)
                return

        url = f"{self.api_url}characters?q={query}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    character_data = await response.json()

            current_index = 0
            current_page = 0

            view = self.CharacterView(
                character_data, current_index, current_page)
            embed = await view.update_embed()
            message = await ctx.reply(embed=embed, view=view, mention_author=False)

        except aiohttp.ClientError as e:
            logging.error(f"An HTTP error occurred: {e}")
            await ctx.send(f"An HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            await ctx.send(f"An unexpected error occurred: {e}")

    @commands.command(name="manga")
    async def manga_search(self, ctx, *, query=None):
        if query is None:
            embed = discord.Embed(
                description=f"{ctx.author.display_name.title()}, can you try entering the `name` of the manga you're looking for?"
            )
            message = await ctx.reply(embed=embed, mention_author=False)

            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                user_message = await self.bot.wait_for(
                    "message", timeout=60, check=check
                )
                await message.delete()

                if not user_message.content.strip():
                    raise ValueError("Manga title cannot be empty")

                query = user_message.content.strip()
                await user_message.delete()

            except asyncio.TimeoutError:
                timeout_embed = discord.Embed(
                    description="Time's Up! You didn't provide a manga title for me to look up.",
                    color=discord.Color.red(),
                )
                await message.edit(embed=timeout_embed)
                return

            except ValueError as e:
                error_embed = discord.Embed(
                    description=f"Error: {str(e)}", color=discord.Color.red()
                )
                await message.edit(embed=error_embed)
                return

        url = f"{self.api_url}manga?q={query}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    response.raise_for_status()
                    manga_data = await response.json()

            if not manga_data["data"]:
                await ctx.reply(
                    f"No results found for '{query}'. Please try a different title."
                )
                return

            current_index = 0
            current_page = 0

            view = self.MangaView(manga_data, current_index, current_page)
            embed = await view.update_embed()
            await ctx.reply(embed=embed, view=view, mention_author=False)

        except aiohttp.ClientError as e:
            logging.error(f"An HTTP error occurred: {e}")
            await ctx.send(f"An HTTP error occurred: {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred: {e}")
            await ctx.send(f"An unexpected error occurred: {e}")

    class AnimeButton(discord.ui.Button):
        def __init__(
            self,
            label,
            style,
            custom_id,
            anime_data,
            current_index,
            current_page,
            max_pages,
        ):
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

            self.current_page = max(0, min(self.current_page, self.max_pages))
            self.current_index = self.current_page

            view = Anime.AnimeView(
                self.anime_data, self.current_index, self.current_page
            )
            embed = await view.update_embed()
            await interaction.response.edit_message(embed=embed, view=view)

    class AnimeView(discord.ui.View):
        def __init__(self, anime_data, current_index, current_page):
            super().__init__(timeout=None)
            self.anime_data = anime_data
            self.current_index = current_index
            self.current_page = current_page
            self.max_pages = len(anime_data["data"]) - 1
            self.update_buttons()

        def update_buttons(self):
            self.clear_items()
            if self.current_page > 0:
                self.add_item(
                    Anime.AnimeButton(
                        "Previous",
                        discord.ButtonStyle.primary,
                        "previous",
                        self.anime_data,
                        self.current_index,
                        self.current_page,
                        self.max_pages,
                    )
                )
            if self.current_page < self.max_pages:
                self.add_item(
                    Anime.AnimeButton(
                        "Next",
                        discord.ButtonStyle.primary,
                        "next",
                        self.anime_data,
                        self.current_index,
                        self.current_page,
                        self.max_pages,
                    )
                )

        async def update_embed(self):
            anime = self.anime_data["data"][self.current_index]
            embed = discord.Embed(title=anime["title"])

            image_url = self.get_image_url(anime["images"])
            if image_url:
                embed.set_image(url=image_url)

            embed.add_field(
                name=" ",
                value=f"**Episodes:** `{anime['episodes']}`\n"
                f"**Status:** `{anime['status']}`\n"
                f"**Genres:** `{', '.join(genre['name'] for genre in anime['genres'])}`\n"
                f"{'**Trailer:** ' + '``' + anime['trailer']['url'] + '``' if anime['trailer']['url'] else ''}\n"
                f"```py\nScore: {anime['score']:>3} (out of 10)\n"
                f"{'▰' * int(anime['score'] * 10 / 10)}{'▱' * (10 - int(anime['score'] * 10 / 10))}```",
                inline=False,
            )
            embed.description = anime.get(
                "synopsis", "> <:anya_angy:1268976144548630608> Synopsis not available"
            )
            embed.set_footer(
                text=f"Page {self.current_page + 1}/{self.max_pages + 1}")

            return embed

        @staticmethod
        def get_image_url(images):
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

    class CharacterButton(discord.ui.Button):
        def __init__(
            self,
            label,
            style,
            custom_id,
            character_data,
            current_index,
            current_page,
            max_pages,
        ):
            super().__init__(label=label, style=style, custom_id=custom_id)
            self.character_data = character_data
            self.current_index = current_index
            self.current_page = current_page
            self.max_pages = max_pages

        async def callback(self, interaction: discord.Interaction):
            if self.custom_id == "previous":
                self.current_page -= 1
                self.current_index = (self.current_index - 1) % len(
                    self.character_data["data"]
                )
            elif self.custom_id == "next":
                self.current_page += 1
                self.current_index = (self.current_index + 1) % len(
                    self.character_data["data"]
                )

            view = Anime.CharacterView(
                self.character_data, self.current_index, self.current_page
            )
            embed = await view.update_embed()
            await interaction.response.edit_message(embed=embed, view=view)

    class CharacterView(discord.ui.View):
        def __init__(self, character_data, current_index, current_page):
            super().__init__(timeout=None)
            self.character_data = character_data
            self.current_index = current_index
            self.current_page = current_page
            self.max_pages = len(character_data["data"]) - 1
            self.update_buttons()

        def update_buttons(self):
            self.clear_items()
            if self.current_page > 0:
                self.add_item(
                    Anime.CharacterButton(
                        "Previous",
                        discord.ButtonStyle.primary,
                        "previous",
                        self.character_data,
                        self.current_index,
                        self.current_page,
                        self.max_pages,
                    )
                )
            if self.current_page < self.max_pages:
                self.add_item(
                    Anime.CharacterButton(
                        "Next",
                        discord.ButtonStyle.primary,
                        "next",
                        self.character_data,
                        self.current_index,
                        self.current_page,
                        self.max_pages,
                    )
                )

        async def update_embed(self):
            character = self.character_data["data"][self.current_index]
            embed = discord.Embed(
                title=character["name"], url=character["url"])

            image_url = character["images"]["jpg"].get("image_url")
            if image_url:
                embed.set_image(url=image_url)

            embed.add_field(
                name="__Details__",
                value=(
                    f"**Nicknames:** `{', '.join(character.get('nicknames', []) or ['N/A'])}`\n"
                    f"**Favorites:** `{character.get('favorites', 'N/A')}`\n"
                ),
                inline=False,
            )
            embed.description = character.get(
                "about", "> <:anya_angy:1268976144548630608> Description not available"
            )
            embed.set_footer(
                text=f"ID: {character.get('mal_id', 'N/A')}\t\t\tPage {self.current_page + 1}/{self.max_pages + 1}"
            )

            return embed

    class MangaButton(discord.ui.Button):
        def __init__(self, label, style, action):
            super().__init__(label=label, style=style)
            self.action = action

        async def callback(self, interaction: discord.Interaction):
            
            view = self.view

            if self.action == "previous" and view.current_page > 0:
                view.current_page -= 1
            elif self.action == "next" and view.current_page < view.max_pages:
                view.current_page += 1

            
            view.current_index = view.current_page

            
            view.update_buttons()
            embed = await view.update_embed()
            await interaction.response.edit_message(embed=embed, view=view)

    class MangaView(discord.ui.View):
        def __init__(self, manga_data, current_index=0, current_page=0, timeout=None):
            super().__init__(timeout=timeout)
            self.manga_data = manga_data
            self.current_index = current_index
            self.current_page = current_page
            self.max_pages = len(manga_data["data"]) - 1
            self.update_buttons()

        def update_buttons(self):
            self.clear_items()  
            
            if self.current_page > 0:
                self.add_item(
                    Anime.MangaButton(
                        "Previous", discord.ButtonStyle.primary, "previous"
                    )
                )
            if self.current_page < self.max_pages:
                self.add_item(
                    Anime.MangaButton(
                        "Next", discord.ButtonStyle.primary, "next")
                )

        async def update_embed(self):
            manga = self.manga_data["data"][self.current_index]
            embed = discord.Embed(title=manga["title"])

            
            image_url = self.get_image_url(manga["images"])
            if image_url:
                embed.set_image(url=image_url)

            
            embed.add_field(
                name=" ",
                value=f"**Chapters:** `{manga['chapters']}`\n"
                f"**Status:** `{manga['status']}`\n"
                f"**Genres:** `{', '.join(genre['name'] for genre in manga['genres'])}`\n"
                f"```py\nScore: {manga['score'] or 'N/A'}\n"
                f"{'▰' * int(manga.get('score', 0) * 10 / 10)}{'▱' * (10 - int(manga.get('score', 0) * 10 / 10))}```",
                inline=False,
            )

            
            embed.description = manga.get(
                "synopsis", "> <:anya_angy:1268976144548630608> Synopsis not available"
            )
            embed.set_footer(
                text=f"Page {self.current_page + 1}/{self.max_pages + 1}")

            return embed

        @staticmethod
        def get_image_url(images):
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


def setup(bot):
    bot.add_cog(Anime(bot))
    bot.add_cog(Recommendation(bot))
