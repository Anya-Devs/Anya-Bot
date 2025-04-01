from Data.const import primary_color
from Imports.discord_imports import *
import cv2, numpy as np, requests, os, itertools, logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)  # You can change this level to INFO or ERROR for less verbose output
logger = logging.getLogger(__name__)

class ImgPuzzle:
    def __init__(self, url, w=800):
        self.u, self.w, self.i, self.p, self.s = url, w, None, [], {}
        self.image_dir = "Data/commands/pokemon/events/glitched/images"  

    def load(self):
        os.makedirs(self.image_dir, exist_ok=True)

        try:
            r = requests.get(self.u, stream=True)
            r.raise_for_status()
            a = np.asarray(bytearray(r.content), dtype=np.uint8)
            i = cv2.imdecode(a, cv2.IMREAD_COLOR)
        except requests.RequestException:
            i = cv2.imread("test_image.png", cv2.IMREAD_COLOR)

        if i is None:
            raise ValueError("Image load failed")
        ar = i.shape[1] / i.shape[0]
        self.i = cv2.resize(i, (self.w, int(self.w / ar)))

    def split(self):
        h, w = self.i.shape[:2]
        mx, my = w // 2, h // 2
        self.p = [self.i[:my, :mx], self.i[:my, mx:], self.i[my:, :mx], self.i[my:, mx:]]
        
        [cv2.imwrite(os.path.join(self.image_dir, f"part_{chr(65+i)}.png"), p) for i, p in enumerate(self.p)]

    def check(self, i):
        g = cv2.cvtColor(i, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 100, 255, cv2.THRESH_BINARY)
        c, _ = cv2.findContours(t, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sum(cv2.contourArea(x) for x in c)

    def eval(self, perm):
        ni = np.zeros_like(self.i)
        h, w = ni.shape[:2]
        mx, my = w // 2, h // 2
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        for idx, p in enumerate(perm):
            y, x = ps[idx]
            ni[y:y+my, x:x+mx] = self.p[p]
        sc = self.check(ni)
        return sc, (sc / (h * w)) * 100

    def solve(self):
        self.load()
        self.split()
        lb, bp, bs, bc = ['A', 'B', 'C', 'D'], None, 0, 0
        for p in itertools.permutations(range(4)):
            sc, c = self.eval(p)
            self.s[p] = (sc, c)
            if sc > bs:
                bp, bs, bc = p, sc, c
        return ''.join(lb[i] for i in bp)
class GlitchSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = None  
        self.embed_footer_message = "You have 45 seconds to fix this glitch. Any incense active in this channel will be paused til then."

    @commands.command()
    async def extract_embed(self, ctx):
        message_link = "https://discord.com/channels/1278580577104040018/1278580578593148971/1356513107169771560"
        channel_id = 1278580578593148971
        message_id = 1356513107169771560

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(message_id)

            if message.embeds:
                for embed in message.embeds:
                    embed.set_footer(text=self.embed_footer_message)
                    await ctx.send(embed=embed)
            else:
                await ctx.send("No embed found in the message.")
        except discord.NotFound:
            await ctx.send("The message was not found!")
        except discord.HTTPException as e:
            await ctx.send(f"[ERROR] Error: {e}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot.user.id:
            for embed in message.embeds:
                if self.embed_footer_message in embed.footer.text:
                    if embed.image:
                        image_url = embed.image.url
                        solver = ImgPuzzle(image_url)
                        
                        try:
                            solution = solver.solve()

                            embed = discord.Embed(
                                title="Puzzle Solved!",
                                description=f"Puzzle solved! Best arrangement: ```{solution}```",
                                color=primary_color()
                            )
                            await message.channel.send(embed=embed)

                        except Exception as e:
                            await message.channel.send(f"[ERROR] Failed to process image: {e}")

def setup(bot):
    bot.add_cog(GlitchSolver(bot))
