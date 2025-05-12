# cogs/poketwo_spawn_detector.py

from imports.discord_imports import *
from utils.subcogs.pokemon import Ping_Pokemon
from repo.utils.events.poketwo_spawns.predict import Prediction

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.target_description = "Guess the pokémon and type @Pokétwo#8236 catch <pokémon> to catch it!"
        self.predictor = Prediction()
        self.pp =  Ping_Pokemon(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.id != self.target_id or not message.embeds:
            return

        embed = message.embeds[0]
        if embed.description != self.target_description:
            return

        image_url = embed.image.url if embed.image and embed.image.url else None
        if not image_url:
            return
        try:
            pokemon_name, confidence = self.predictor.predict(image_url)
            pokemon_name = self.pp.transform_pokemon_name(pokemon_name)
            reply = f"{pokemon_name}: {confidence}"
            await message.reply(reply)
        except Exception as e:
            await message.reply(f"❌ Prediction error: {e}")


def setup(bot):
    PoketwoSpawnDetector(bot)