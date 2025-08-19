import os, re, csv, json, logging, asyncio, aiohttp
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np

from imports.discord_imports import *
from utils.subcogs.pokemon import *
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut
from data.local.const import *
from motor.motor_asyncio import AsyncIOMotorClient
from utils.events.poketwo_spawns import PokemonImageBuilder, PokemonUtils

_executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
logger = logging.getLogger(__name__)


class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.predictor = Prediction()
        self.pp = PoketwoCommands(bot)
        self.mongo = MongoHelper(AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["pokemon"])
        self.pokemon_utils = PokemonUtils(
            self.mongo,
            type_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_types.json",
            quest_emojis_file="data/commands/pokemon/pokemon_emojis/_pokemon_quest.json",
            description_file="data/commands/pokemon/pokemon_description.csv",
            id_file="data/commands/pokemon/pokemon_names.csv",
            regional_forms={
                "alola": "Alolan", "galar": "Galarian",
                "hisui": "Hisuian", "paldea": "Paldean", "unova": "Unovan"
            },
            lang_flags={"ja": "🇯🇵", "de": "🇩🇪", "fr": "🇫🇷", "en": "🇺🇸"},
            bot=bot,
            pp=self.pp,
        )
        self.pokemon_image_builder = PokemonImageBuilder()
        self._pokemon_ids = self.pokemon_utils.load_pokemon_ids()
        self.success_emoji = "<:green:1261639410181476443>"
        self.error_emoji = "<:red:1261639413943762944>"
        self.cross_emoji = "❌"
        self.emojis = {
            "shiny": "<:shiny_sparkle:1394386258406412380>",
            "collection": "<:collection_ball:1394386212961124504>",
        }

    async def output_prediction(self, message, image_url):
        try:
            slug_raw, conf = await asyncio.to_thread(self.predictor.predict, image_url)
            slug = self.pokemon_utils.get_base_pokemon_name(slug_raw)
            if slug not in self._pokemon_ids:
                slug = self.pokemon_utils.find_full_name_for_slug(slug_raw).lower().replace("_", "-")
                #print(f"Slug fallback: {slug}")

            try:
                conf_float = float(str(conf).strip().rstrip("%"))
                low_conf = conf_float < 30
            except Exception:
                conf_float, low_conf = 0.0, False

            rare, regional = self.pokemon_utils._special_names
            server_config, (shiny_pings, collection_pings), type_pings, quest_pings = await asyncio.gather(
                self.pokemon_utils.get_server_config(message.guild.id),
                self.pokemon_utils.get_ping_users(message.guild, slug),
                self.pokemon_utils.get_type_ping_users(message.guild, slug),
                self.pokemon_utils.get_quest_ping_users(message.guild, slug),
            )

            special_roles = []
            if any(r in slug for r in rare) and server_config.get("rare_role"):
                special_roles.append(f"<@&{server_config['rare_role']}>")
            if (
                (any(r in slug for r in regional) or any(slug.startswith(f"{f.lower()}-") for f in self.pokemon_utils.regional_forms.values()))
                and server_config.get("regional_role")
            ):
                special_roles.append(f"<@&{server_config['regional_role']}>")

            description, dex, _ = self.pokemon_utils.get_description(slug)
            if not dex or dex == "???":
                dex = self._pokemon_ids.get(slug, "???")

            ping_msg, embed = await self.pokemon_utils.format_messages(
                slug,
                type_pings,
                quest_pings,
                shiny_pings,
                collection_pings,
                " ".join(special_roles),
                f"{conf_float:.2f}%",
                dex,
                description,
                image_url,
                low_conf,
            )

            slug_fmt = slug.replace("_", " ")
            best_alt = self.pokemon_utils.get_best_normal_alt_name(slug)
            #print(best_alt)
            self.pokemon_image_builder.create_image(
                raw_slug=slug_raw,
                pokemon_name=self.pokemon_utils.format_name(slug).replace('_', ' ').title(),
                best_name=best_alt or "",
                types=self.pokemon_utils.get_pokemon_types(slug),
                bg_url=None
            )

            file = discord.File("data/events/poketwo_spawns/image/test.png", filename="pokemon_spawn.png")
            await message.channel.send(content=ping_msg, file=file, reference=message)
        except Exception as e:
            logger.error(f"Error in output_prediction: {type(e).__name__}: {e}")
            await message.channel.send(f"{self.error_emoji} Failed to process spawn", reference=message)

    @commands.Cog.listener()
    async def on_message(self, message):
        try:
            if ut:
                return
            if message.author.id == self.target_id:
                for embed in message.embeds:
                    if embed.title and "pokémon has appeared!" in embed.title.lower() and embed.image:
                        await self.output_prediction(message, embed.image.url)
        except Exception as e:
            print(f"{self.cross_emoji} Error in on_message: {type(e).__name__}: {e}")

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        try:
            message = ctx.message
            if not image_url:
                ref = message.reference
                if ref:
                    message = await ctx.channel.fetch_message(ref.message_id)
                if message.attachments:
                    image_url = message.attachments[0].url
                elif message.embeds and message.embeds[0].image:
                    image_url = message.embeds[0].image.url
            if not image_url:
                return await ctx.send(f"{self.cross_emoji} No image URL found.")
            await self.output_prediction(message, image_url)
        except Exception as e:
            await ctx.send(f"{self.cross_emoji} Prediction error: {type(e).__name__}: {e}")


def setup(bot): bot.add_cog(PoketwoSpawnDetector(bot))
