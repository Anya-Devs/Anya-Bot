from imports.discord_imports import *
from utils.subcogs.pokemon import Ping_Pokemon
from submodules.poketwo_autonamer.predict import Prediction
from bot.token import use_test_bot as ut

class PoketwoSpawnDetector(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.test_mode = ut
        self.target_id = 716390085896962058
        self.target_title = "pokémon has appeared!"
        self.predictor = Prediction()
        self.pp = Ping_Pokemon(bot)

    def format_name(self, name):
        m = {'alola': 'Alolan', 'galar': 'Galarian', 'hisui': 'Hisuian', 'paldea': 'Paldean', 'unova': 'Unovan'}
        p = name.lower().split('-')
        o = f"{m[p[1]]} {p[0]}" if len(p) > 1 and p[1] in m else name
        return o.replace('-', ' ').title()

    async def output_prediction(self, dest, image_url, reference=None):
        name, conf = self.predictor.predict(image_url)
        msg = f"{self.format_name(name)}: {conf}"
        if isinstance(reference, discord.Message):
            await dest.send(msg, reference=reference)
        else:
            await dest.reply(msg, mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, m):
        try:
            if m.author.id != (self.bot.user.id if self.test_mode else self.target_id):
                return
            for e in m.embeds:
                if self.target_title in (e.title or "") and e.image:
                    return await self.output_prediction(m.channel, e.image.url, reference=m)
        except Exception as e:
            print(f"❌ Error in on_message: {type(e).__name__}: {e}")

    @commands.command(name="ps", hidden=True)
    async def predict_spawn(self, ctx, image_url=None):
        if not image_url:
            r = ctx.message.reference
            m = await ctx.channel.fetch_message(r.message_id) if r else ctx.message
            if m.attachments:
                image_url = m.attachments[0].url
            elif m.embeds and m.embeds[0].image:
                image_url = m.embeds[0].image.url
        if not image_url:
            return await ctx.send("❌ No image URL found.")
        try:
            await self.output_prediction(ctx, image_url, reference=ctx.message)
        except Exception as e:
            await ctx.send(f"❌ Prediction error: {type(e).__name__}: {e}")

def setup(bot):
    bot.add_cog(PoketwoSpawnDetector(bot))
