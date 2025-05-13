from imports.discord_imports import *
from utils.subcogs.pokemon import Ping_Pokemon
from submodules.poketwo_autonamer.predict import Prediction
from utils.token import use_test_bot as ut

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.test_mode = ut
        self.target_id = 716390085896962058
        self.target_title = "pokémon has appeared!"
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)

    @commands.Cog.listener()
    async def on_message(self, message):
      try:

        target = self.bot.user.id if self.test_mode else self.target_id
        if message.author.id != target:
            return
        image_url = None
        for embed in message.embeds:
            if self.target_title in embed.title and embed.image:
                image_url = embed.image.url
            pokemon_name, confidence = self.predictor.predict(image_url)
            formatted_name = self.format_pokemon_name(pokemon_name)
            await message.reply(f"{formatted_name}: {confidence}")
      except Exception as e:
            print(f"[ERROR] Prediction failed in message {message.id} | {type(e).__name__}: {e}")
            await message.reply(f"❌ Prediction failed: {type(e).__name__}: {e}")

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url: str = None):
        if not image_url:
            if ctx.message.reference:
                ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                if ref_msg.attachments:
                    image_url = ref_msg.attachments[0].url
                elif ref_msg.embeds and ref_msg.embeds[0].image:
                    image_url = ref_msg.embeds[0].image.url
            elif ctx.message.embeds and ctx.message.embeds[0].image:
                image_url = ctx.message.embeds[0].image.url
        if not image_url:
            return await ctx.send("❌ No image URL found.")
        try:
            print(f"[INFO] Manual prediction triggered by {ctx.author} with image: {image_url}")
            pokemon_name, confidence = self.predictor.predict(image_url)
            formatted_name = self.format_pokemon_name(pokemon_name)
            print(f"[SUCCESS] Prediction: {formatted_name} ({confidence})")
            await ctx.send(f"{formatted_name}: {confidence}")
        except Exception as e:
            print(f"[ERROR] Manual prediction failed | {type(e).__name__}: {e}")
            await ctx.send(f"❌ Prediction error: {type(e).__name__}: {e}")

    def format_pokemon_name(self, pokemon_name: str) -> str:
        REGIONAL_VARIANTS = {
            'alola': 'Alolan',
            'galar': 'Galarian',
            'hisui': 'Hisuian',
            'paldea': 'Paldean',
            'unova': 'Unovan'
        }
        parts = pokemon_name.lower().split('-')
        if len(parts) > 1 and parts[1] in REGIONAL_VARIANTS:
            region_name = REGIONAL_VARIANTS[parts[1]]
            base_name = parts[0].capitalize()
            return f"{region_name} {base_name}"
        return pokemon_name.capitalize()

def setup(bot):
    PoketwoSpawnDetector(bot)
