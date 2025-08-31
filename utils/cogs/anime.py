import aiohttp, asyncio, traceback
from datetime import datetime
from typing import Dict, Any, List, Optional
from imports.discord_imports import *
from concurrent.futures import ThreadPoolExecutor
from data.local.const import primary_color
from data.local.emojis import *
from io import BytesIO
from PIL import Image



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







class MangaAPIError(Exception):
    """Custom exception for errors occurring when fetching or processing manga data from the API."""
    def __init__(self, message: str = "An error occurred with the Manga API"):
        super().__init__(message)


class MangaReader:
    BASE_URL = "https://api.mangadex.org"
    CDN_QUALITY = "data"

    @staticmethod
    async def fetch_manga_chapters(manga_id: str, language: str = "en", limit: int = 1) -> Dict[str, Any]:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{MangaReader.BASE_URL}/chapter"
                params = {"manga": manga_id, "translatedLanguage[]": language, "limit": limit, "order[chapter]": "asc"}
                async with session.get(url, params=params) as resp:
                    if resp.status != 200: raise MangaAPIError(f"API returned {resp.status}")
                    data = await resp.json()
                    if not data.get("data"): raise MangaAPIError("No chapters found")
                    return data
        except aiohttp.ClientError as e: raise MangaAPIError(f"Network error: {str(e)}")

    @staticmethod
    async def fetch_chapter_pages(chapter_id: str) -> List[str]:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{MangaReader.BASE_URL}/at-home/server/{chapter_id}"
                async with session.get(url) as resp:
                    if resp.status != 200: raise MangaAPIError(f"CDN returned {resp.status}")
                    data = await resp.json()
                    base, chapter = data.get("baseUrl"), data.get("chapter", {})
                    hash_val, filenames = chapter.get("hash"), chapter.get(MangaReader.CDN_QUALITY, [])
                    if not all([base, hash_val, filenames]): raise MangaAPIError("Invalid chapter data")
                    return [f"{base}/{MangaReader.CDN_QUALITY}/{hash_val}/{f}" for f in filenames]
        except aiohttp.ClientError as e: raise MangaAPIError(f"Network error: {str(e)}")

    @staticmethod
    async def fetch_manga_chapters(manga_id: str, language: str = "en") -> List[Dict[str, Any]]:
        chapters = []
        limit = 100
        offset = 0
        async with aiohttp.ClientSession() as session:
            while True:
                url = f"{MangaReader.BASE_URL}/chapter"
                params = {
                    "manga": manga_id,
                    "translatedLanguage[]": language,
                    "limit": limit,
                    "offset": offset,
                    "order[chapter]": "asc"
                }
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        raise MangaAPIError(f"API returned {resp.status}")
                    data = await resp.json()
                    chapters.extend(data.get("data", []))
                    if offset + limit >= data.get("total", 0):
                        break
                    offset += limit
        if not chapters:
            raise MangaAPIError("No chapters found")
        return chapters

    @staticmethod
    async def fetch_chapter_pages(chapter_id: str) -> List[str]:
        async with aiohttp.ClientSession() as session:
            url = f"{MangaReader.BASE_URL}/at-home/server/{chapter_id}"
            async with session.get(url) as resp:
                if resp.status != 200:
                    raise MangaAPIError(f"CDN returned {resp.status}")
                data = await resp.json()
                base, chapter = data.get("baseUrl"), data.get("chapter", {})
                hash_val, filenames = chapter.get("hash"), chapter.get(MangaReader.CDN_QUALITY, [])
                if not all([base, hash_val, filenames]):
                    raise MangaAPIError("Invalid chapter data")
                return [f"{base}/{MangaReader.CDN_QUALITY}/{hash_val}/{f}" for f in filenames]

class MangaSession(View):
    active_sessions: dict[int, "MangaSession"] = {}

    def __init__(self, ctx, manga_data: Dict[str, Any]):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.manga_list = manga_data.get("data", [])[:25]
        self.author_id = ctx.author.id
        self.current_manga: Optional[Dict[str, Any]] = None
        self.current_chapter: Optional[Dict[str, Any]] = None
        self.page_urls: list[str] = []
        self.current_page_index: int = 0
        self.chapters_data: list[Dict[str, Any]] = []
        self.chapter_page = 0
        self.chapters_per_page = 25
        self.session_start_time = datetime.now()
        self.nsfw_warning_shown: bool = False
        self._previous_state: Optional[dict] = None  # NEW: store previous state

        self.button_config = [
            {"label": "", "custom_id": "prev_page", "style": ButtonStyle.secondary, "row": 0, "emoji": "⬅️", "disabled": False},
            {"label": "{}/{}", "custom_id": "page_indicator", "style": ButtonStyle.primary, "row": 0, "emoji": None, "disabled": True},
            {"label": "", "custom_id": "next_page", "style": ButtonStyle.secondary, "row": 0, "emoji": "➡️", "disabled": False},
            {"label": "Other Options", "custom_id": "other_options", "style": ButtonStyle.secondary, "row": 1, "emoji": "⚙️", "disabled": False},
        ]

        self._setup_manga_selector()

    @classmethod
    async def create(cls, ctx, manga_data: Dict[str, Any]) -> "MangaSession":
        existing = cls.active_sessions.get(ctx.author.id)
        if existing:
            try:
                if hasattr(existing, "message"):
                    embed = discord.Embed(
                        title="👋 Previous Reading Session Ended",
                        description="A new session was started, ending the old one automatically.",
                        color=discord.Color.red()
                    )
                    await existing.message.edit(embed=embed, view=None)
            except Exception:
                pass
            existing.stop()
            del cls.active_sessions[ctx.author.id]

        session = cls(ctx, manga_data)
        cls.active_sessions[ctx.author.id] = session
        return session

    def _setup_manga_selector(self):
        if not self.manga_list:
            return
        options = [
            SelectOption(
                label=f"{i+1}. {m.get('attributes', {}).get('title', {}).get('en') or next(iter(m.get('attributes', {}).get('title', {}).values()), 'Unknown')}"[:100],
                value=str(i),
                description=(m.get("attributes", {}).get("description", {}).get("en") or "No description")[:100],
                emoji="📖"
            )
            for i, m in enumerate(self.manga_list)
        ]
        select = discord.ui.Select(placeholder="📚 Choose a manga...", options=options, min_values=1, max_values=1)
        select.callback = self._on_manga_selected
        self.add_item(select)

        # NEW: Go Back button if previous state exists
        if self._previous_state:
            go_back_btn = Button(label="⬅️ Go Back", custom_id="go_back", style=ButtonStyle.secondary)
            go_back_btn.callback = self._go_back_to_previous
            self.add_item(go_back_btn)

    async def interaction_check(self, interaction: Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                embed=Embed(title="❌ Access Denied", description="You can't use these buttons 😅", color=discord.Color.red()),
                ephemeral=True
            )
            return False
        return True

    async def _on_manga_selected(self, interaction: Interaction):
        idx = int(interaction.data["values"][0])
        # SAVE previous state before changing manga
        self._previous_state = {
            "current_manga": self.current_manga,
            "current_chapter": self.current_chapter,
            "page_urls": self.page_urls.copy(),
            "current_page_index": self.current_page_index,
            "chapters_data": self.chapters_data.copy(),
            "chapter_page": self.chapter_page
        }

        self.current_manga = self.manga_list[idx]
        content_rating = self.current_manga.get("attributes", {}).get("contentRating", "safe").lower()
        if content_rating != "safe" and not getattr(interaction.channel, "is_nsfw", lambda: False)():
            await interaction.response.send_message(
                embed=Embed(
                    title="⚠️ NSFW Content Warning",
                    description="This manga contains NSFW content. Please use a NSFW channel.",
                    color=discord.Color.orange()
                ),
                ephemeral=True
            )
            return

        try:
            self.chapters_data = await MangaReader.fetch_manga_chapters(self.current_manga["id"])
            if not self.chapters_data:
                await self._handle_error(interaction, "No chapters available 😅 Just pick a different manga.", ephemeral=True)
                return
            await self._show_chapter_selector(interaction)
        except Exception:
            await self._handle_error(interaction, "Could not load this manga 😅 Please select another one.", ephemeral=True)

    async def _show_chapter_selector(self, interaction: Interaction):
        self.clear_items()
        start = self.chapter_page * self.chapters_per_page
        end = start + self.chapters_per_page
        options = []
        for i in range(start, min(end, len(self.chapters_data))):
            chap = self.chapters_data[i]
            attrs = chap.get("attributes", {})
            chap_num = attrs.get("chapter") or 0
            chap_title = attrs.get("title") or ""
            chap_title = "" if chap_title.strip().lower() == "no title" else chap_title
            tags_list = attrs.get("tags", [])
            tags_str = ", ".join([
                t.get("attributes", {}).get("name", {}).get("en") or next(iter(t.get("attributes", {}).get("name", {}).values()), "Unknown")
                for t in tags_list
            ])
            label = f"Ch {chap_num}" + (f": {chap_title}" if chap_title else "") + (f" [{tags_str}]" if chap_title and tags_str else "")
            options.append(SelectOption(label=label[:100], value=str(i)))

        select = discord.ui.Select(
            placeholder=f"📚 Select Chapter {start+1}-{min(end, len(self.chapters_data))}",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self._on_chapter_selected
        self.add_item(select)

        if start > 0:
            prev_btn = Button(label="⬅️ Prev Chapters", custom_id="prev_chapter_page", style=ButtonStyle.secondary)
            prev_btn.callback = self._handle_chapter_navigation
            self.add_item(prev_btn)
        if end < len(self.chapters_data):
            next_btn = Button(label="➡️ Next Chapters", custom_id="next_chapter_page", style=ButtonStyle.secondary)
            next_btn.callback = self._handle_chapter_navigation
            self.add_item(next_btn)

        # NEW: Go Back button if previous state exists
        if self._previous_state:
            go_back_btn = Button(label="⬅️ Go Back", custom_id="go_back", style=ButtonStyle.secondary)
            go_back_btn.callback = self._go_back_to_previous
            self.add_item(go_back_btn)

        embed = Embed(
            title=f"📚 {self._get_manga_title()} Chapters",
            description=f"Select a chapter to start reading ({start+1}-{min(end,len(self.chapters_data))})",
            color=primary_color()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_chapter_selected(self, interaction: Interaction):
        idx = int(interaction.data["values"][0])
        # SAVE previous state before reading chapter
        self._previous_state = {
            "current_manga": self.current_manga,
            "current_chapter": None,
            "page_urls": [],
            "current_page_index": 0,
            "chapters_data": self.chapters_data.copy(),
            "chapter_page": self.chapter_page
        }
        self.current_chapter = self.chapters_data[idx]
        self.page_urls = await MangaReader.fetch_chapter_pages(self.current_chapter["id"])
        if not self.page_urls:
            await self._handle_error(interaction, "This chapter has no pages 😅 Please pick a different chapter.", ephemeral=True)
            return
        self.current_page_index = 0
        self.clear_items()
        await self._setup_reading_interface(interaction)

    async def _handle_chapter_navigation(self, interaction: Interaction):
        if interaction.data["custom_id"] == "prev_chapter_page":
            self.chapter_page = max(self.chapter_page - 1, 0)
        else:
            self.chapter_page += 1
        await self._show_chapter_selector(interaction)

    async def _setup_reading_interface(self, interaction: Interaction):
        self.clear_items()
        for cfg in self.button_config:
            label = cfg["label"].format(self.current_page_index + 1, len(self.page_urls)) if "{}" in cfg["label"] else cfg["label"]
            btn = Button(label=label, style=cfg["style"], custom_id=cfg["custom_id"], disabled=cfg["disabled"], row=cfg["row"], emoji=cfg.get("emoji"))
            btn.callback = self._handle_button_interaction
            self.add_item(btn)
        await self._update_reading_display(interaction)

    async def _handle_button_interaction(self, interaction: Interaction):
        cid = interaction.data["custom_id"]
        if cid == "prev_page": await self._navigate_page(interaction, -4)
        elif cid == "next_page": await self._navigate_page(interaction, 4)
        elif cid == "jump_page": await self._handle_page_jump(interaction)
        elif cid == "chapter_info": await self._show_chapter_info(interaction)
        elif cid == "select_new": await self._restart_manga_selection(interaction)
        elif cid == "stop_session": await self._stop_session(interaction)
        elif cid == "other_options": await self._show_other_options(interaction)
        elif cid == "select_chapter": await self._show_chapter_selector(interaction)
        elif cid == "next_chapter":
            idx = self.chapters_data.index(self.current_chapter) + 1
            if idx < len(self.chapters_data):
                self.current_chapter = self.chapters_data[idx]
                self.page_urls = await MangaReader.fetch_chapter_pages(self.current_chapter["id"])
                self.current_page_index = 0
                self.clear_items()
                await self._setup_reading_interface(interaction)
        elif cid == "go_back":
            await self._go_back_to_previous(interaction)

    # --- NEW: Go Back implementation ---
    async def _go_back_to_previous(self, interaction: Interaction):
        if not self._previous_state:
            await interaction.response.send_message("❌ No previous session found.", ephemeral=True)
            return
        state = self._previous_state
        self.current_manga = state.get("current_manga")
        self.current_chapter = state.get("current_chapter")
        self.page_urls = state.get("page_urls", [])
        self.current_page_index = state.get("current_page_index", 0)
        self.chapters_data = state.get("chapters_data", [])
        self.chapter_page = state.get("chapter_page", 0)
        self._previous_state = None  # clear previous state

        self.clear_items()
        if self.current_chapter and self.page_urls:
            await self._setup_reading_interface(interaction)
        elif self.current_manga:
            await self._show_chapter_selector(interaction)
        else:
            self._setup_manga_selector()
            embed = Embed(title="📚 Manga Selection", description="Choose a manga from the dropdown", color=primary_color())
            embed.set_footer(text=f"Session started by {self.ctx.author.display_name}")
            await interaction.response.edit_message(embed=embed, view=self)

    async def _show_other_options(self, interaction: Interaction):
        self.clear_items()
        for bcfg in [
            {"label":"Jump to Page","custom_id":"jump_page","style":ButtonStyle.secondary,"emoji":"🔢"},
            {"label":"Chapter Info","custom_id":"chapter_info","style":ButtonStyle.secondary,"emoji":"📋"},
            {"label":"Select Chapter","custom_id":"select_chapter","style":ButtonStyle.primary,"emoji":"📖"},
            {"label":"New Manga","custom_id":"select_new","style":ButtonStyle.success,"emoji":None},
            {"label":"Stop Reading","custom_id":"stop_session","style":ButtonStyle.danger,"emoji":"🛑"},
        ]:
            btn = Button(label=bcfg["label"], style=bcfg["style"], custom_id=bcfg["custom_id"], emoji=bcfg.get("emoji"))
            btn.callback = self._handle_button_interaction
            self.add_item(btn)
        embed = Embed(
            title=f"📚 {self._get_manga_title()} - Other Options",
            description="Select an option below:",
            color=primary_color()
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def _navigate_page(self, interaction: Interaction, direction: int):
        new_index = self.current_page_index + direction
        if 0 <= new_index < len(self.page_urls):
            self.current_page_index = new_index
            await self._update_reading_display(interaction)
        else:
            if direction > 0 and self._has_next_chapter():
                view = discord.ui.View()
                next_btn = Button(label="Go to Next Chapter", custom_id="next_chapter", style=ButtonStyle.success)
                next_btn.callback = self._handle_button_interaction
                view.add_item(next_btn)
                await interaction.response.send_message(
                    "📖 You've reached the end of this chapter. Go to the next chapter?", view=view, ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    embed=Embed(title="⚠️ Page Navigation", description="You're at the edge 😅", color=discord.Color.orange()),
                    ephemeral=True
                )

    def _has_next_chapter(self) -> bool:
        if not self.current_chapter or not self.chapters_data:
            return False
        idx = self.chapters_data.index(self.current_chapter)
        return idx + 1 < len(self.chapters_data)

    async def _handle_page_jump(self, interaction: Interaction):
        modal = PageJumpModal(self)
        await interaction.response.send_modal(modal)

    async def _show_chapter_info(self, interaction: Interaction):
        if not self.current_chapter:
            await interaction.response.send_message("❌ No chapter info available 😅", ephemeral=True)
            return
        attrs = self.current_chapter.get("attributes", {})
        chap_num = attrs.get("chapter", "Unknown")
        chap_title = attrs.get("title", "No title")
        pages_count = len(self.page_urls)
        progress = ((self.current_page_index + 1) / pages_count) * 100
        progress_bar = "█"*(int(progress)//10) + "░"*(10-int(progress)//10)
        tags_list = attrs.get("tags", [])
        tags_str = ", ".join([t.get("attributes", {}).get("name", {}).get("en") or next(iter(t.get("attributes", {}).get("name", {}).values()), "Unknown") for t in tags_list]) or "No tags"
        embed = Embed(title="📋 Chapter Information", color=discord.Color.blue())
        embed.add_field(name="📖 Manga", value=self._get_manga_title(), inline=False)
        embed.add_field(name="📄 Chapter", value=f"Chapter {chap_num}", inline=True)
        embed.add_field(name="📝 Title", value=chap_title, inline=True)
        embed.add_field(name="📊 Pages", value=f"{pages_count}", inline=True)
        embed.add_field(name="🎯 Current Page", value=f"{self.current_page_index+1}/{pages_count}", inline=True)
        embed.add_field(name="📈 Progress", value=f"{progress_bar} {progress:.1f}%", inline=False)
        embed.add_field(name="🏷️ Tags", value=tags_str, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _restart_manga_selection(self, interaction: Interaction):
        self.current_manga = None
        self.current_chapter = None
        self.page_urls = []
        self.current_page_index = 0
        self.clear_items()
        self._setup_manga_selector()
        embed = Embed(title="📚 Manga Selection", description="Choose a manga from the dropdown", color=primary_color())
        embed.set_footer(text=f"Session started by {self.ctx.author.display_name}")
        await interaction.response.edit_message(embed=embed, view=self)

    async def _stop_session(self, interaction: Interaction):
        duration = datetime.now() - self.session_start_time
        hours, remainder = divmod(int(duration.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m {seconds}s"
        embed = Embed(title="👋 Reading Session Ended", description="Thanks for reading! 😊", color=discord.Color.red())
        if self.current_manga:
            embed.add_field(name="📖 Last Read", value=self._get_manga_title(), inline=False)
        embed.add_field(name="⏱️ Session Duration", value=duration_str, inline=True)
        embed.set_footer(text="Use the manga command again to start a new session!")
        await interaction.response.edit_message(embed=embed, view=None)
        if self.author_id in MangaSession.active_sessions:
            del MangaSession.active_sessions[self.author_id]
        self.stop()

    async def _update_reading_display(self, interaction: Interaction):
        if not self.page_urls:
            await self._handle_error(interaction, "No pages to display 😅 Please select a different manga.", ephemeral=True)
            return
        try:
            embeds = []
            for i in range(4):
                idx = self.current_page_index + i
                if idx >= len(self.page_urls):
                    break
                embed = Embed(title=f"{self._get_manga_title()}", url="https://rajtech.me", color=primary_color())
                embed.set_image(url=self.page_urls[idx])
                embeds.append(embed)
            self._update_button_states()
            if interaction.response.is_done():
                await interaction.followup.send(embeds=embeds, ephemeral=False, view=self)
            else:
                await interaction.response.edit_message(embeds=embeds, view=self)
        except Exception:
            await self._handle_error(interaction, "Failed to display pages 😅 Please pick another manga.", ephemeral=True)

    def _update_button_states(self):
        for item in self.children:
            if hasattr(item, 'custom_id'):
                if item.custom_id == "page_indicator":
                    item.label = f"{self.current_page_index+1}/{len(self.page_urls)}"
                elif item.custom_id == "prev_page":
                    item.disabled = self.current_page_index == 0
                elif item.custom_id == "next_page":
                    item.disabled = self.current_page_index + 4 >= len(self.page_urls)

    def _get_manga_title(self) -> str:
        if not self.current_manga:
            return "Unknown Manga"
        title_dict = self.current_manga.get("attributes", {}).get("title", {})
        return title_dict.get("en") or next(iter(title_dict.values()), "Unknown Title")

    async def _handle_error(self, interaction: Interaction, msg: str, ephemeral: bool = True):
        embed = Embed(title="ℹ️ Info", description=msg, color=discord.Color.orange())
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=ephemeral)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
        except Exception:
            pass

    async def on_timeout(self):
        embed = Embed(title="⏰ Session Timed Out", description="Your reading session expired due to inactivity 😅", color=discord.Color.orange())
        if hasattr(self, "message"):
            await self.message.edit(embed=embed, view=None)
        if self.author_id in MangaSession.active_sessions:
            del MangaSession.active_sessions[self.author_id]
        self.stop()
 
class PageJumpModal(discord.ui.Modal):
    
    def __init__(self, manga_session: MangaSession):
        super().__init__(title="Jump to Page")
        self.manga_session = manga_session
        self.page_input = discord.ui.TextInput(label="Page Number", placeholder=f"1-{len(manga_session.page_urls)}", min_length=1, max_length=4, required=True)
        self.add_item(self.page_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_number = int(self.page_input.value)
            if 1 <= page_number <= len(self.manga_session.page_urls):
                self.manga_session.current_page_index = page_number-1
                await self.manga_session._update_reading_display(interaction)
            else:
                await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid Page Number", description=f"Enter between 1 and {len(self.manga_session.page_urls)}", color=discord.Color.red()), ephemeral=True)
        except ValueError: await interaction.response.send_message(embed=discord.Embed(title="❌ Invalid Input", description="Enter a valid number.", color=discord.Color.red()), ephemeral=True)
        except Exception as e: await interaction.response.send_message(f"❌ Error jumping page: {e}", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        traceback.print_exc()
        embed = discord.Embed(title="❌ Modal Error", description="Error processing page jump.", color=discord.Color.red())
        try: await interaction.response.send_message(embed=embed, ephemeral=True)
        except: await interaction.followup.send(embed=embed, ephemeral=True)