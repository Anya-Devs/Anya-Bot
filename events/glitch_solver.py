from Data.const import primary_color
from Imports.discord_imports import *
import cv2, numpy as np, requests, os, itertools, logging, aiohttp, re, io
from collections import Counter


test_mode = False

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
        print(f"Image loaded and resized to {s.i.shape}")

    def split(s):
        h, w = s.i.shape[:2]
        mx, my = w // 2, h // 2
        s.p = [s.i[:my, :mx], s.i[:my, mx:], s.i[my:, :mx], s.i[my:, mx:]]
        os.makedirs("pieces", exist_ok=True)
        [cv2.imwrite(f"pieces/{chr(65+i)}.png", p) for i, p in enumerate(s.p)]
        print("Pieces saved to disk")

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
        
        print(f"Evaluating arrangement: {perm}")
        
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
            if sc > bs: 
                bp, bs, bc = p, sc, c
        
        solution_image = np.zeros_like(s.i)
        h, w = solution_image.shape[:2]
        mx, my = w // 2, h // 2
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        
        for idx, p in enumerate(bp):
            y, x = ps[idx]
            solution_image[y:y+my, x:x+mx] = s.p[p]
        
        # Save the solution image
        #cv2.imwrite("solution_image.png", solution_image)        
        return ''.join(lb[i] for i in bp)



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
