import asyncio
import datetime
from discord import Embed
from discord.ext import commands
from Imports.discord_imports import *
from Data.const import primary_color
import re

# Timestamp function
def timestamp_gen(timestamp: int) -> str:
    dt = datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'  # Returns relative time format (e.g., "in 30 seconds")

class Anti_Thief(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_id = 874910942490677270
        self.shiny_hunters = []
        self.shiny_ping_phrase = "**✨ Shiny Hunt Pings:**"
        self.shiny_regex = r"<@(\d+)>"

    async def process_pings(self, guild, message_content):
        shiny_hunters = []
        if self.shiny_ping_phrase in message_content:
            mention_start_index = message_content.find(self.shiny_ping_phrase) + len(self.shiny_ping_phrase)
            mention_part = message_content[mention_start_index:].strip()

            if mention_part:
                try:
                    shiny_match = re.findall(self.shiny_regex, mention_part)
                    if shiny_match:
                        shiny_hunters = [
                            await self.get_member(guild, int(user_id))
                            for user_id in shiny_match
                            if await self.get_member(guild, int(user_id))
                        ]
                except re.error as e:
                    print(f"Regex error: {e}")

        return shiny_hunters

    async def get_member(self, guild, user_id):
        try:
            return await guild.fetch_member(user_id)
        except:
            return None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.id == self.bot_id:
            self.shiny_hunters = await self.process_pings(message.guild, message.content)

class EventGate(commands.Cog):
    def __init__(self, bot, anti_thief=None):
        self.bot = bot
        self.anti_thief = anti_thief  # Store the Anti_Thief cog instance
        self.timeout_duration = datetime.timedelta(hours=3)  # Timeout duration (3 hours)
        self.detect_bot_id = 874910942490677270  # Bot ID for detection

    async def send_shiny_hunt_embed(self, channel, shiny_hunters):
        # Get current time and generate the time to wait
        timestamp = datetime.datetime.utcnow().timestamp()
        wait_until = timestamp + 30  # 30 seconds from now

        embed = Embed(
            title="Shiny Detection",
            description=f"Shiny hunters, get ready! Waiting for the catch... {timestamp_gen(wait_until)}",
            color=primary_color()
        )
        message = await channel.send(embed=embed)

        # Run the countdown asynchronously without blocking the bot
        await self._wait_and_update_embed(message, wait_until)

    async def _wait_and_update_embed(self, message, wait_until):
        # Wait for 30 seconds, while other tasks run
        await asyncio.sleep(30)
        
        # Update embed after the wait period
        embed = message.embeds[0]
        embed.description = "Everyone may catch the Pokémon now! No restrictions."
        await message.edit(embed=embed)

    async def handle_congratulations(self, message, channel, shiny_hunters):
        # Check if message is a congratulations message
        if "Congratulations" in message.content:
            mentioned_user = re.findall(r"<@(\d+)>", message.content)
            if mentioned_user:
                mentioned_user = mentioned_user[0]
                shiny_hunter = next((hunter for hunter in shiny_hunters if str(hunter.id) == mentioned_user), None)

                if shiny_hunter:  # If shiny hunter, send congrats
                    embed = Embed(
                        title="Congratulations!",
                        description=f"Well done, {shiny_hunter.mention}, Good luck on your streak!",
                        color=primary_color()
                    )
                    await channel.send(embed=embed)
                    return True  # End event after congrats
                else:  # If non-hunter, timeout and warn
                    non_hunter = await self.bot.fetch_user(mentioned_user)
                    await non_hunter.timeout(self.timeout_duration, reason=f"Shiny thief detected")
                    embed = Embed(
                        title="Shiny Thief Detected!",
                        description=f"{non_hunter.mention} tried to steal the shiny Pokémon. They've been timed out for 3 hours.",
                        color=primary_color()
                    )
                    await channel.send(embed=embed)
                    return False
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if the message is from the Pokétwo bot
        if message.author.id == 716390085896962058:  # Pokétwo message
            # Dynamically fetch shiny hunters from the Anti_Thief cog
            shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(message.guild, message.content)
            
            if len(shiny_hunters) > 0:  # If there are shiny hunters
                channel = message.channel
                await self.send_shiny_hunt_embed(channel, shiny_hunters)
                if await self.handle_congratulations(message, channel, shiny_hunters):
                    print("Shiny hunter caught the pokemon!")
                    return  # End the event
                else:
                    # If non-shiny catcher, inform them how long they need to wait
                    non_hunter_mention = re.findall(r"<@(\d+)>", message.content)
                    if non_hunter_mention:
                        non_hunter = await self.bot.fetch_user(non_hunter_mention[0])
                        await channel.send(f"{non_hunter.mention}, you need to wait for 3 hours before you can participate again.")
        
        # Check for reference to the bot's shiny hunt message and simulate the same behavior as the command
        if message.author.id == self.detect_bot_id and message.reference:
            reference_message = await message.channel.fetch_message(message.reference.message_id)
            if reference_message.author.id == self.detect_bot_id:
                # Dynamically fetch shiny hunters from the referenced message content
                shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(message.guild, reference_message.content)
                await message.channel.send(f"Shiny hunters: {', '.join([hunter.mention for hunter in shiny_hunters])}")
                
                # Trigger EventManually by simulating an on_message call
                await self.send_shiny_hunt_embed(message.channel, shiny_hunters)
                await self.handle_congratulations(reference_message, message.channel, shiny_hunters)



class ShinyBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.detect_bot_id = 874910942490677270
    @commands.command(name="s_t", aliases=['t_s', 'ts'])
    async def test_shiny_extraction(self, ctx):
        if ctx.message.reference:
            reference_message = await ctx.channel.fetch_message(ctx.message.reference.message_id)
            if reference_message.author.id == self.detect_bot_id:
                shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(ctx.guild, reference_message.content)
                await ctx.send(f"Shiny hunters: {', '.join([hunter.mention for hunter in shiny_hunters])}")
                
                # Trigger EventManually by simulating an on_message call
                channel = ctx.channel
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(channel, shiny_hunters)
                await self.bot.get_cog('EventGate').handle_congratulations(reference_message, channel, shiny_hunters)

            else:
                await ctx.send("This message isn't a valid reference from the bot.")

async def setup(bot):
    # Initialize Anti_Thief with the bot instance
    anti_thief = Anti_Thief(bot)
    
    # Initialize EventGate with the Anti_Thief cog instance
    event_gate = EventGate(bot, anti_thief)
    
    # Add the cogs to the bot
    bot.add_cog(anti_thief)
    bot.add_cog(event_gate)
