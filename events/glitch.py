from Data.const import primary_color
from Imports.discord_imports import *
import cv2, numpy as np, requests, os, itertools, logging


class ImgPuzzle:
    def __init__(s, url, w=800):
        s.u, s.w, s.i, s.p, s.s = url, w, None, [], {}

    def load(s):
        try:
            r = requests.get(s.u, stream=True)
            r.raise_for_status()
            a = np.asarray(bytearray(r.content), dtype=np.uint8)
            i = cv2.imdecode(a, cv2.IMREAD_COLOR)
        except requests.RequestException:
            i = cv2.imread("test_image.png", cv2.IMREAD_COLOR)
        if i is None: raise ValueError("Image load failed")
        ar = i.shape[1] / i.shape[0]
        s.i = cv2.resize(i, (s.w, int(s.w / ar)))

    def split(s):
        h, w = s.i.shape[:2]
        mx, my = w // 2, h // 2
        s.p = [s.i[:my, :mx], s.i[:my, mx:], s.i[my:, :mx], s.i[my:, mx:]]
        os.makedirs("pieces", exist_ok=True)
        [cv2.imwrite(f"pieces/{chr(65+i)}.png", p) for i, p in enumerate(s.p)]

    def check(s, i):
        orb = cv2.ORB_create()
        g = cv2.cvtColor(i, cv2.COLOR_BGR2GRAY)
        kp, des = orb.detectAndCompute(g, None)
        _, t = cv2.threshold(g, 100, 255, cv2.THRESH_BINARY)
        c, _ = cv2.findContours(t, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        return len(kp), sum(cv2.contourArea(x) for x in c)

    def eval(s, perm):
        ni = np.zeros_like(s.i)
        h, w = ni.shape[:2]
        mx, my = w // 2, h // 2
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        for idx, p in enumerate(perm):
            y, x = ps[idx]
            ni[y:y+my, x:x+mx] = s.p[p]
        sc, f = s.check(ni)
        return sc + f, (sc / (h * w)) * 100  

    def solve(s):
        s.load()
        s.split()
        lb, bp, bs, bc = ['A', 'B', 'C', 'D'], None, 0, 0
        for p in itertools.permutations(range(4)):
            sc, c = s.eval(p)
            s.s[p] = (sc, c)
            if sc > bs: bp, bs, bc = p, sc, c
        return ''.join(lb[i] for i in bp)
    



class GlitchSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058  
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
        if message.author.id == self.target_id:
            for embed in message.embeds:
                if self.embed_footer_message in embed.footer.text:
                    if embed.image:
                        image_url = embed.image.url
                        solver = ImgPuzzle(image_url)
                        
                        try:
                            solution = solver.solve()

                            embed = discord.Embed(
                                title="Puzzle Solved!",
                                description=f"Best arrangement: ```{solution}```",
                                color=primary_color()
                            )
                            await message.channel.send(embed=embed)

                        except Exception as e:
                            await message.channel.send(f"[ERROR] Failed to process image: {e}")

def setup(bot):
    bot.add_cog(GlitchSolver(bot))
