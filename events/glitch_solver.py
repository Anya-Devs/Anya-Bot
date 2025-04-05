from Data.const import primary_color
from Imports.discord_imports import *
import cv2, numpy as np, requests, os, itertools, logging, aiohttp, re

test_mode = False

class ImgPuzzle:
    def __init__(self, bot):
        self.bot = bot
        self.orb = cv2.ORB_create()

        if not hasattr(self.bot, "session") or self.bot.session is None:
            self.bot.session = aiohttp.ClientSession()

    async def load(self, url):
        async with self.bot.session.get(url) as response:
            if response.status != 200:
                raise ValueError("Failed to fetch image")
            data = await response.read()
            image = np.asarray(bytearray(data), dtype=np.uint8)
            return cv2.imdecode(image, cv2.IMREAD_COLOR)

    def split(self, image):
        h, w = image.shape[:2]
        mx, my = w // 2, h // 2

        if w % 2 != 0:
            mx += 1
        if h % 2 != 0:
            my += 1

        return [image[:my, :mx], image[:my, mx:], image[my:, :mx], image[my:, mx:]]

    def check(self, img):
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, t = cv2.threshold(g, 100, 255, cv2.THRESH_BINARY)
        c, _ = cv2.findContours(t, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        edges = cv2.Canny(g, 50, 150)
        edge_count = np.count_nonzero(edges)
        return sum(cv2.contourArea(x) for x in c), edge_count

    def edge_consistency(self, part1, part2, axis):
        if axis == 'vertical':
            border1 = part1[:, -1]
            border2 = part2[:, 0]
        else:
            border1 = part1[-1, :]
            border2 = part2[0, :]
        return np.sum(np.abs(border1 - border2))

    def process(self, image, parts, perm):
        h, w = image.shape[:2]
        mx, my = w // 2, h // 2
        ni = np.zeros((h, w, 3), dtype=image.dtype)
        ps = [(0, 0), (0, mx), (my, 0), (my, mx)]
        total_similarity = 0
        total_edge_consistency = 0

        for idx, p in enumerate(perm):
            y, x = ps[idx]
            ni[y:y + my, x:x + mx] = parts[p]
            if idx % 2 == 1:
                total_edge_consistency += self.edge_consistency(parts[perm[idx - 1]], parts[p], 'vertical')
            if idx >= 2:
                total_edge_consistency += self.edge_consistency(parts[perm[idx - 2]], parts[p], 'horizontal')

        contour_score, edge_count = self.check(ni)
        combined_score = (contour_score * 0.4) + (edge_count * 0.2) - (total_edge_consistency * 0.4)
        return combined_score, total_similarity

    async def solve(self, url):
        image = await self.load(url)
        parts = self.split(image)
        labels = ['A', 'B', 'C', 'D']
        best_score = -1
        best_part = None

        for p in itertools.permutations(range(4)):
            process_score, _ = self.process(image, parts, p)
            if process_score > best_score:
                best_score = process_score
                best_part = p

        return ''.join(labels[i] for i in reversed(best_part))






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
                        embed.set_footer(text=self.embed_footer_message)
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
                        s = ImgPuzzle(self.bot)
                        solved = await s.solve(image_url)
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
