from imports.discord_imports import *
from utils.subcogs.pokemon import Ping_Pokemon
from _repo.utils.events.poketwo_spawns.predict import Prediction

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058
        self.target_description = "Guess the pokémon and type @Pokétwo#8236 catch <pokémon> to catch it!"
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)

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
            formatted_name = self.format_pokemon_name(pokemon_name)
            reply = f"{formatted_name}: {confidence}"
            await message.reply(reply)
        except Exception as e:
            await message.reply(f"❌ Prediction error: {e}")

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url: str = None):
        if not image_url:
            if ctx.message.reference:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref_msg.attachments:
                    image_url = ref_msg.attachments[0].url
                elif ref_msg.embeds:
                    image_url = ref_msg.embeds[0].image.url if ref_msg.embeds[0].image else None
            elif ctx.message.embeds:
                image_url = ctx.message.embeds[0].image.url if ctx.message.embeds[0].image else None
        if not image_url:
            return await ctx.send("❌ No image URL found.")
        try:
            pokemon_name, confidence = self.predictor.predict(image_url)
            formatted_name = self.format_pokemon_name(pokemon_name)
            await ctx.send(f"{formatted_name}: {confidence}")
        except Exception as e:
            await ctx.send(f"❌ Prediction error: {e}")

    def format_pokemon_name(self, pokemon_name: str) -> str:
        REGIONAL_VARIANTS = {'alola': 'Alolan', 'galar': 'Galarian', 'hisui': 'Hisuian', 'paldea': 'Paldean', 'unova': 'Unovan'}
        parts = pokemon_name.lower().split('-')
        if len(parts) > 1 and parts[1] in REGIONAL_VARIANTS:
            region_name = REGIONAL_VARIANTS[parts[1]]
            base_name = parts[0].capitalize()
            return f"{region_name} {base_name}"
        else:
            return pokemon_name.capitalize()

def setup(bot):
    PoketwoSpawnDetector(bot)
