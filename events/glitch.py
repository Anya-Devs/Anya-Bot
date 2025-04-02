from Data.const import primary_color
from Imports.discord_imports import *
import cv2, numpy as np, requests, os, itertools, logging

class ImgPuzzle:
    def __init__(s, url, w=800):
        s.url = url
        s.w = w
        s.orb = cv2.ORB_create()

    async def load(s):
        async with s.bot.session.get(s.url) as r:
            if r.status != 200:
                raise ValueError("Failed to fetch image")
            return cv2.imdecode(np.asarray(bytearray(await r.read()), dtype=np.uint8), cv2.IMREAD_COLOR)

    def split(s, img):
        h, w = img.shape[:2]
        mx, my = w // 2, h // 2
        return [img[:my, :mx], img[:my, mx:], img[my:, :mx], img[my:, mx:]]

    def check(s, img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 100, 255, cv2.THRESH_BINARY)
        c, _ = cv2.findContours(t, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        e = cv2.Canny(g, 50, 150)
        return sum(cv2.contourArea(x) for x in c), np.count_nonzero(e)

    def edge_consistency(s, p1, p2, axis):
        b1, b2 = (p1[:, -1], p2[:, 0]) if axis == 'vertical' else (p1[-1, :], p2[0, :])
        return np.sum(np.abs(b1 - b2))

    def process(s, img, parts, perm):
        h, w = img.shape[:2]
        mx, my = w // 2, h // 2
        ni = np.zeros((h, w, 3), dtype=img.dtype)
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        edge_score = 0
        
        for i, p in enumerate(perm):
            y, x = ps[i]
            ni[y:y + my, x:x + mx] = parts[p]
            if i % 2 == 1:
                edge_score += s.edge_consistency(parts[perm[i - 1]], parts[p], 'vertical')
            if i >= 2:
                edge_score += s.edge_consistency(parts[perm[i - 2]], parts[p], 'horizontal')

        contour_score, edge_count = s.check(ni)
        return (contour_score * 0.4) + (edge_count * 0.2) - (edge_score * 0.4)

    async def solve(s):
        img = await s.load()
        parts = s.split(img)
        labels = 'ABCD'
        best_p = max(itertools.permutations(range(4)), key=lambda p: s.process(img, parts, p))
        return ''.join(labels[i] for i in reversed(best_p))


class GlitchSolver(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.target_id = 716390085896962058  
        self.delete_target_id = 854233015475109888 
        self.delete_target_phrase = "@Pokétwo#8236 afd fix"
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
                if self.embed_footer_message in (embed.footer.text or ""):
                    if embed.image:
                        image_url = embed.image.url
                        solver = ImgPuzzle(image_url)
                        try:
                            solution = solver.solve()
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
