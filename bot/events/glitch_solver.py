from data.local.const import primary_color
from bot.utils.events.glitch_solver import *
from imports.discord_imports import *
import cv2, numpy as np, requests, io, itertools, discord, re
from collections import Counter

test_mode = False

class GlitchSolver(commands.Cog):
    def __init__(self, bot):
        self.bot, self.target_id, self.delete_target_id, self.delete_target_phrase, self.embed_footer_message, self.test_mode = bot, 716390085896962058, 854233015475109888, "@Pokétwo#8236 afd fix", "fix this glitch", test_mode

    @commands.command(name='ee',hidden=True)
    async def extract_embed(self, ctx, message_link: str):
        if match := re.match(r'https://discord.com/channels/(\d+)/(\d+)/(\d+)', message_link):
            guild_id, channel_id, message_id = map(int, match.groups())
            channel = self.bot.get_channel(channel_id)
            if not channel: return await ctx.send("Channel not found!")
            try:
                message = await channel.fetch_message(message_id)
                if message.embeds:
                    for embed in message.embeds: await ctx.send(embed=embed)
                else: await ctx.send("No embed found in the message.")
            except discord.NotFound: await ctx.send("Message not found!")
            except discord.HTTPException as e: await ctx.send(f"[ERROR] Error: {e}")
        else: await ctx.send("Invalid message link format!")

    @commands.Cog.listener()
    async def on_message(self, message):
        target = self.bot.user.id if self.test_mode else self.target_id
        if message.author.id == target:
            for embed in message.embeds:
                if self.embed_footer_message in (embed.footer.text or ""):
                    if embed.image:
                        image_url = embed.image.url
                        solved = ImgPuzzle(self.bot).solve(image_url)
                        try:
                            embed = discord.Embed(
                                title="Puzzle Solved!",
                                description=f"@Pokétwo#8236 afd fix {solved.lower()}",
                                color=primary_color()
                            )
                            await message.channel.send(embed=embed)
                        except Exception as e:
                            await message.channel.send(f"[ERROR] Failed to process image: {e}")

        if message.author.id == self.delete_target_id and self.delete_target_phrase in message.content:
            try: await message.delete()
            except discord.Forbidden: print("Bot lacks permission to delete messages.")
            except discord.HTTPException as e: print(f"Failed to delete message: {e}")

def setup(bot): bot.add_cog(GlitchSolver(bot))
