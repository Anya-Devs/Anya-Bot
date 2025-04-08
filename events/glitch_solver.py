from Data.const import primary_color
from Imports.discord_imports import *
import cv2, numpy as np, requests, os, itertools, logging, aiohttp, re, io
from collections import Counter


test_mode = False

class ImgPuzzle:
    def __init__(self, url: str, w: int = 800):
        self.u = url
        self.w = w
        self.i = None
        self.p = []
        self.s = {}
        self.d = "Data/commands/pokemon/events/glitched/images"
        os.makedirs(self.d, exist_ok=True)

    def load(self):
        try:
            r = requests.get(self.u, stream=True, timeout=5)
            r.raise_for_status()
            a = np.asarray(bytearray(r.content), dtype=np.uint8)
            i = cv2.imdecode(a, cv2.IMREAD_COLOR)
        except Exception:
            i = cv2.imread("test_image.png", cv2.IMREAD_COLOR)

        if i is None:
            raise ValueError("Image load failed")
        
        ar = i.shape[1] / i.shape[0]
        self.i = cv2.resize(i, (self.w, int(self.w / ar)))

    def split(self):
        h, w = self.i.shape[:2]
        mx, my = w // 2, h // 2
        self.p = [self.i[:my, :mx], self.i[:my, mx:], self.i[my:, :mx], self.i[my:, mx:]]
        
        for idx, part in enumerate(self.p):
            cv2.imwrite(os.path.join(self.d, f"{chr(65 + idx)}.png"), part)

    def _score(self, i):
        g = cv2.cvtColor(i, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 100, 255, cv2.THRESH_BINARY)
        c, _ = cv2.findContours(t, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return sum(cv2.contourArea(x) for x in c)

    def _check_alignment(self, pieces):
        ni = np.zeros_like(self.i)
        h, w = ni.shape[:2]
        mx, my = w // 2, h // 2
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        for idx, pi in enumerate(pieces):
            y, x = ps[idx]
            ni[y:y+my, x:x+mx] = self.p[pi]
        
        gray = cv2.cvtColor(ni, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        return edges

    def eval(self, p):
        ni = np.zeros_like(self.i)
        h, w = ni.shape[:2]
        mx, my = w // 2, h // 2
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        for idx, pi in enumerate(p):
            y, x = ps[idx]
            ni[y:y+my, x:x+mx] = self.p[pi]
        
        edge_image = self._check_alignment(p)
        sc = np.sum(edge_image)
        return sc, (sc / (h * w)) * 100

    def solve(self):
        self.load()
        self.split()
        lb, bs, bc = ['A', 'B', 'C', 'D'], -1, 0
        for p in itertools.permutations(range(4)):
            sc, c = self.eval(p)
            self.s[p] = (sc, c)
            if sc > bs:
                bs, bc = sc, c
                bp = p
        return ''.join(lb[i] for i in reversed(bp))

    
    def check_completed(self):
        final_image = np.zeros_like(self.i)
        h, w = final_image.shape[:2]
        mx, my = w // 2, h // 2
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        
        for idx, p in enumerate(self.s.keys()):
            y, x = ps[idx]
            final_image[y:y+my, x:x+mx] = self.p[p]
        
        gray = cv2.cvtColor(final_image, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours) > 0:
            return True  
        return False
    


class GlitchSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058  
        self.delete_target_id = 854233015475109888 
        self.delete_target_phrase = "@Pokétwo#8236 afd fix"
        self.embed_footer_message = "fix this glitch"
        self.test_mode = test_mode

    @commands.command()
    async def extract_embed(self, ctx, message_link: str):
        pattern = r'https://discord.com/channels/(\d+)/(\d+)/(\d+)'
        match = re.match(pattern, message_link)

        if match:
            guild_id, channel_id, message_id = map(int, match.groups())

            channel = self.bot.get_channel(channel_id)
            if not channel:
                return await ctx.send("Channel not found!")

            try:
                message = await channel.fetch_message(message_id)

                if message.embeds:
                    for embed in message.embeds:
                        await ctx.send(embed=embed)
                else:
                    await ctx.send("No embed found in the message.")
            except discord.NotFound:
                await ctx.send("The message was not found!")
            except discord.HTTPException as e:
                await ctx.send(f"[ERROR] Error: {e}")
        else:
            await ctx.send("Invalid message link format!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if self.test_mode:
            target =  self.bot.user.id
        else: 
            target = self.target_id

        if message.author.id == target:
            for embed in message.embeds:
                if self.embed_footer_message in (embed.footer.text or ""):
                    if embed.image:
                        image_url = embed.image.url
                        s = ImgPuzzle(url=image_url)
                        solved = s.solve()
                        try:
                            solution = solved
                            embed = discord.Embed(
                                title="Puzzle Solved!",
                                description=f"@Pokétwo#8236 afd fix {solution.lower()}",
                                color=primary_color()
                            )
                            await message.channel.send(embed=embed)
                        except Exception as e:
                            await message.channel.send(f"[ERROR] Failed to process image: {e}")

        if message.author.id == self.delete_target_id and self.delete_target_phrase in message.content:
            try:
                await message.delete()
            except discord.Forbidden:
                print("Bot lacks permission to delete messages.")
            except discord.HTTPException as e:
                print(f"Failed to delete message: {e}")

def setup(bot):
    bot.add_cog(GlitchSolver(bot))
