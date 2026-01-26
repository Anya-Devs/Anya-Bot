import asyncio
import random
import logging
from datetime import datetime, timezone
from typing import Optional

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

from imports.discord_imports import *
from data.local.const import primary_color
from bot.utils.cogs.anime import (
    Anime_Recommendation, 
    Manga_Recommendation,
    AnimeView,
    CharacterView,
    MangaView,
    MangaSession
)


class Anime(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api.jikan.moe/v4/"
        self.mangadex_url = "https://api.mangadex.org"
        self.waifu_api = "https://api.waifu.pics"
        self.nekos_api = "https://nekos.best/api/v2"
        self.red = discord.Color.red()
        self.ar = Anime_Recommendation(bot)
        self.mr = Manga_Recommendation(bot)
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self.session
    
    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    async def prompt_query(self, ctx, media_type):
        """Prompt user for search query"""
        embed = discord.Embed(
            title=f"🔍 Search {media_type.title()}",
            description=f"What {media_type} would you like to search for?",
            color=primary_color()
        )
        await ctx.reply(embed=embed, mention_author=False)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            msg = await self.bot.wait_for("message", timeout=30.0, check=check)
            return msg.content
        except asyncio.TimeoutError:
            await ctx.send("⏰ Search timed out!")
            return None

    async def fetch_and_send(self, ctx, url, query, view_class):
        """Generic method to fetch API data and send with view"""
        session = await self.get_session()
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    view = view_class(ctx, data, query, self.api_url, session)
                    embed = await view.update_embed()
                    await ctx.reply(embed=embed, view=view, mention_author=False)
        except Exception as e:
            logging.error(f"Error: {e}")
            await ctx.send(f"Oops! Something went wrong: {e}")

    # ═══════════════════════════════════════════════════════════════
    # ANIME COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="anime", invoke_without_command=True)
    async def anime_group(self, ctx):
        """Anime commands - search, recommendations, quotes & more"""
        embed = discord.Embed(
            title="📺 Anime Commands",
            description=(
                f"`{ctx.prefix}anime search <name>` - Find an anime\n"
                f"`{ctx.prefix}anime recommend` - Get random anime\n"
                f"`{ctx.prefix}anime character <name>` - Search characters\n"
                f"`{ctx.prefix}anime quote` - Random anime quote\n"
                f"`{ctx.prefix}anime schedule` - Today's airing anime"
            ),
            color=primary_color()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @anime_group.command(name="search")
    async def anime_search(self, ctx, *, query: Optional[str] = None):
        """Search for anime by name"""
        query = query or await self.prompt_query(ctx, "anime")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}anime?q={query}", query, AnimeView)

    @anime_group.command(name="character")
    async def anime_character(self, ctx, *, query=None):
        """Search for anime characters"""
        query = query or await self.prompt_query(ctx, "character")
        if not query: return
        await self.fetch_and_send(ctx, f"{self.api_url}characters?q={query}", query, CharacterView)
    
    @anime_group.command(name="recommend")
    async def anime_recommend(self, ctx):
        """Get a random anime recommendation"""
        d = await self.ar.fetch_random_anime()
        m = await ctx.reply(embed=discord.Embed(description=f'🔍 Finding you an anime...', color=primary_color()), mention_author=False)
        await self.ar.update_anime_embed(m, d)

    @anime_group.command(name="quote")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def anime_quote(self, ctx):
        """Get a random anime quote"""
        session = await self.get_session()
        try:
            async with session.get("https://animechan.io/api/v1/quotes/random") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    quote_data = data.get("data", {})
                    
                    quote = quote_data.get("content", "No quote found")
                    character = quote_data.get("character", {}).get("name", "Unknown")
                    anime = quote_data.get("anime", {}).get("name", "Unknown Anime")
                    
                    embed = discord.Embed(
                        description=f"💬 *\"{quote}\"*",
                        color=primary_color(),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.add_field(name="Character", value=character, inline=True)
                    embed.add_field(name="Anime", value=anime, inline=True)
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Quote API error: {e}")
        
        # Fallback quotes
        fallback_quotes = [
            {"quote": "People's lives don't end when they die. It ends when they lose faith.", "character": "Itachi Uchiha", "anime": "Naruto"},
            {"quote": "The world isn't perfect. But it's there for us, doing the best it can.", "character": "Roy Mustang", "anime": "Fullmetal Alchemist"},
            {"quote": "If you don't take risks, you can't create a future.", "character": "Monkey D. Luffy", "anime": "One Piece"},
            {"quote": "Whatever you lose, you'll find it again. But what you throw away you'll never get back.", "character": "Kenshin Himura", "anime": "Rurouni Kenshin"},
        ]
        q = random.choice(fallback_quotes)
        embed = discord.Embed(
            description=f"💬 *\"{q['quote']}\"*",
            color=primary_color()
        )
        embed.add_field(name="Character", value=q["character"], inline=True)
        embed.add_field(name="Anime", value=q["anime"], inline=True)
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # FUN IMAGE COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="waifu")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def waifu(self, ctx):
        """Get a random waifu image"""
        session = await self.get_session()
        try:
            async with session.get(f"{self.waifu_api}/sfw/waifu") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    embed = discord.Embed(
                        title="💖 Waifu",
                        color=discord.Color.from_rgb(255, 182, 193),
                        timestamp=datetime.now(timezone.utc)
                    )
                    embed.set_image(url=data.get("url", ""))
                    embed.set_footer(text=f"Requested by {ctx.author}")
                    return await ctx.reply(embed=embed, mention_author=False)
        except Exception as e:
            logging.error(f"Waifu API error: {e}")
        await ctx.reply("❌ Couldn't fetch waifu image", mention_author=False)

    @commands.command(name="neko")
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def neko(self, ctx):
        """Get a random neko image"""
        session = await self.get_session()
        try:
            async with session.get(f"{self.nekos_api}/neko") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if results:
                        url = results[0].get("url", "")
                        artist = results[0].get("artist_name", "Unknown")
                        
                        embed = discord.Embed(
                            title="🐱 Neko",
                            color=discord.Color.from_rgb(255, 182, 193),
                            timestamp=datetime.now(timezone.utc)
                        )
                        embed.set_image(url=url)
                        embed.set_footer(text=f"Source: {artist} • Requested by {ctx.author}")
                        
                        view = discord.ui.View()
                        view.add_item(discord.ui.Button(
                            label="Download",
                            style=discord.ButtonStyle.link,
                            url=url,
                            emoji="⬇️"
                        ))
                        
                        return await ctx.reply(embed=embed, view=view, mention_author=False)
        except Exception as e:
            logging.error(f"Neko API error: {e}")
        await ctx.reply("❌ Couldn't fetch neko image", mention_author=False)

    @commands.command(name="wallpaper")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def wallpaper(self, ctx):
        """Get a random anime wallpaper"""
        session = await self.get_session()
        
        # Use reliable APIs with proper fallbacks - focused on anime wallpapers
        apis = [
            {
                "url": "https://api.waifu.im/search/?included_tags=wallpaper&limit=1",
                "parser": lambda data: (
                    data.get("results", [{}])[0].get("url", ""),
                    data.get("results", [{}])[0].get("artist", "Waifu.im")
                )
            },
            {
                "url": "https://nekos.best/api/v2/wallpaper",
                "parser": lambda data: (
                    data.get("results", [{}])[0].get("url", ""),
                    data.get("results", [{}])[0].get("artist_name", "Nekos.best")
                )
            },
            {
                "url": "https://api.waifu.pics/sfw/wallpaper",
                "parser": lambda data: (data.get("url", ""), "Waifu.pics")
            }
        ]
        
        for i, api in enumerate(apis):
            try:
                async with session.get(api["url"], timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        # Parse response using the specific parser
                        url, artist = api["parser"](data)
                        
                        if url:
                            embed = discord.Embed(
                                title="🖼️ Anime Wallpaper",
                                color=primary_color(),
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.set_image(url=url)
                            embed.set_footer(text=f"Source: {artist} • Requested by {ctx.author}")
                            
                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(
                                label="Download",
                                style=discord.ButtonStyle.link,
                                url=url,
                                emoji="⬇️"
                            ))
                            
                            return await ctx.reply(embed=embed, view=view, mention_author=False)
                        else:
                            logging.warning(f"Wallpaper API {i+1} returned no URL: {api['url']}")
                    else:
                        logging.warning(f"Wallpaper API {i+1} returned status {resp.status}: {api['url']}")
                        
            except asyncio.TimeoutError:
                logging.warning(f"Wallpaper API {i+1} timeout: {api['url']}")
                continue
            except Exception as e:
                logging.error(f"Wallpaper API {i+1} error: {e}", exc_info=True)
                continue
        
        # If all APIs fail, send a fallback message
        embed = discord.Embed(
            title="❌ Wallpaper Service Unavailable",
            description="All wallpaper sources are currently unavailable. Please try again later.",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"Requested by {ctx.author}")
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Anime(bot))
