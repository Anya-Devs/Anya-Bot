import aiohttp
from imports.discord_imports import *
from data.local.const import primary_color
from data.local.emojis import *


left_button_emoji = "<:point_left:1351851216153350145>"
right_button_emoji  = "<:point_right:1351851206103928948>"


class Anime_Btn(discord.ui.Button):
    def __init__(
        self,
        label,
        style,
        custom_id,
        emoji,
        anime_data,
        current_index,
        current_page,
        max_pages,
    ):
        super().__init__(label=label, style=style, custom_id=custom_id, emoji=emoji)
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

        view = AnimeView(self.anime_data, self.current_index, self.current_page)
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
                Anime_Btn(
                    "Previous",
                    discord.ButtonStyle.gray,
                    "previous",
                    right_button_emoji,
                    self.anime_data,
                    self.current_index,
                    self.current_page,
                    self.max_pages,
                )
            )
        if self.current_page < self.max_pages:
            self.add_item(
                Anime_Btn(
                    "Next",
                    discord.ButtonStyle.gray,
                    "next",
                    left_button_emoji,
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
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages + 1}")

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


class Character_Btn(discord.ui.Button):
    def __init__(
        self,
        label,
        style,
        custom_id,
        character_data,
        current_index,
        current_page,
        max_pages,
        emoji=None
    ):
        super().__init__(label=label, style=style, custom_id=custom_id, emoji=emoji)
        self.character_data = character_data
        self.current_index = current_index
        self.current_page = current_page
        self.max_pages = max_pages

    async def callback(self, interaction: discord.Interaction):
        if self.custom_id == "previous":
            self.current_page -= 1
            self.current_index = (self.current_index - 1) % len(self.character_data["data"])
        elif self.custom_id == "next":
            self.current_page += 1
            self.current_index = (self.current_index + 1) % len(self.character_data["data"])

        view = CharacterView(
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
                Character_Btn(
                    "Previous",
                    discord.ButtonStyle.primary,
                    "previous",
                    self.character_data,
                    self.current_index,
                    self.current_page,
                    self.max_pages,
                    emoji=left_button_emoji
                )
            )
        if self.current_page < self.max_pages:
            self.add_item(
                Character_Btn(
                    "Next",
                    discord.ButtonStyle.primary,
                    "next",
                    self.character_data,
                    self.current_index,
                    self.current_page,
                    self.max_pages,
                    emoji=right_button_emoji
                )
            )

    async def update_embed(self):
        character = self.character_data["data"][self.current_index]
        embed = discord.Embed(
            title=character["name"],
            url=character["url"]
        )

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


class Manga_Btn(discord.ui.Button):
    def __init__(self, label, style, action, emoji=None):
        super().__init__(label=label, style=style, emoji=emoji)
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
                Manga_Btn("Previous", discord.ButtonStyle.primary, "previous", emoji=left_button_emoji)
            )
        if self.current_page < self.max_pages:
            self.add_item(
                Manga_Btn("Next", discord.ButtonStyle.primary, "next", emoji=right_button_emoji)
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
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages + 1}")
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


class Anime_Recommendation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.API_URL = "https://api.jikan.moe/v4/random/anime"

    async def fetch_random_anime(self) -> dict | None:
        async with aiohttp.ClientSession() as s:
            async with s.get(self.API_URL) as r:
                return await r.json() if r.status == 200 else None

    @staticmethod
    def get_image_url(imgs: dict) -> str | None:
        for f in ("jpg", "webp"):
            for s in ("large", "medium", "small"):
                u = imgs.get(f, {}).get(f"{s}_image_url")
                if u:
                    return u
        return None

    async def update_anime_embed(self, m: discord.Message, d: dict):
        a = d["data"]
        g = ", ".join(g["name"] for g in a.get("genres", [])) or "N/A"
        s = a.get("score") or 0
        stars = "▰" * int(s) + "▱" * (10 - int(s))

        e = discord.Embed(
            title=a.get("title", "Unknown Title"),
            description=a.get("synopsis", "> <:anya_angy:1268976144548630608> Synopsis not available"),
            color=primary_color()
        )
        e.add_field(
            name=" ",
            value=f"**Episodes:** `{a.get('episodes','N/A')}`\n"
                  f"**Status:** `{a.get('status','N/A')}`\n"
                  f"**Genres:** `{g if len(g) > 2 else 'Not Rated'}`\n"
                  + (f"**Trailer:** `{a.get('trailer',{}).get('url')}`\n" if a.get("trailer") else "")
                  + f"```py\nScore: {s:.1f}\n{stars}```",
            inline=False
        )
        e.set_image(url=self.get_image_url(a.get("images", {})))
        e.set_footer(text="Anime Recommendation")

        v = View()
        v.add_item(Button(label="View Reviews", style=discord.ButtonStyle.link,
                          url=f"https://myanimelist.net/anime/{a.get('mal_id')}/reviews",
                          disabled=not a.get("mal_id")))
        b = Button(label="Get Another Random Anime", style=discord.ButtonStyle.primary, custom_id="random_anime_button")
        b.callback = self.random_anime_callback
        v.add_item(b)
        await m.edit(embed=e, view=v)

    async def random_anime_callback(self, i: discord.Interaction):
        d = await self.fetch_random_anime()
        await self.update_anime_embed(i.message, d)
        await i.response.defer()
