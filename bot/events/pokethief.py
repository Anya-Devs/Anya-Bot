import asyncio, datetime, re, time, os, requests, traceback, logging, json
from data.const import primary_color
from utils.token import get_bot_token
from imports.log_imports import *
from imports.discord_imports import *
from utils.events.pokethief import PokemonThiefUtils, ShinyHunterManager, PokemonThiefHandler

log_dir = "data"
if not os.path.exists(log_dir): os.makedirs(log_dir)

class Anti_Thief(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_id = [874910942490677270, 1234247716243112100, 854233015475109888]
        self.hunter_manager = ShinyHunterManager(bot)
        self.primary_color = primary_color()
        self.ignore_channel = 'incense'
        
    async def process_pings(self, guild, message_content): return await self.hunter_manager.process_pings(guild, message_content)
    async def is_shiny_hunter(self, user_id): return await self.hunter_manager.is_shiny_hunter(user_id)

    @commands.command(name='set_phrase', hidden=True)
    async def set_ping_phrase(self, ctx, *, new_phrase: str):
        if ctx.author.id != 1124389055598170182: return
        success = self.hunter_manager.update_ping_phrase(new_phrase)
        await ctx.reply(f"Shiny hunt ping phrase updated to: {new_phrase}" if success else "Failed to update the ping phrase", mention_author=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        if 'incense' not in message.channel.name.lower() and message.author.id in self.bot_id and message.guild:
            self.hunter_manager.shiny_hunters = await self.process_pings(message.guild, message.content)
            if self.hunter_manager.shiny_hunters:
                await self.bot.get_cog('EventGate').send_shiny_hunt_embed(message.channel, self.hunter_manager.shiny_hunters, reference_message=message)

class EventGate(commands.Cog):
    def __init__(self, bot, anti_thief=None):
        self.bot = bot
        self.anti_thief = anti_thief
        self.timeout_duration = datetime.timedelta(hours=3)
        self.detect_bot_id = 716390085896962058
        self.wait_time = 30
        self.primary_color = primary_color()
        self.active_events = {}
        self.handled_congrats = set()
        self.thief_handler = PokemonThiefHandler(bot)
        self.shiny_ping_phrase = PokemonThiefUtils.load_ping_phrase()

    async def send_shiny_hunt_embed(self, channel, shiny_hunters, reference_message=None):
        if channel.id in self.active_events: return
        timestamp, wait_until = datetime.datetime.utcnow().timestamp(), timestamp + self.wait_time
        self.active_events[channel.id] = wait_until
        wait_embed = Embed(description=f"{PokemonThiefUtils.timestamp_gen(wait_until)} | waiting for {' '.join([hunter.mention for hunter in shiny_hunters])}", color=self.primary_color)
        try:
            message = await channel.send(embed=wait_embed, reference=reference_message)
        except Exception as e:
            logger.error(f"Failed to send shiny hunt embed: {e}")
            message = await channel.send(embed=wait_embed)
        await self.start_countdown(message, wait_until, reference_message)

    async def start_countdown(self, message, wait_until, reference_message):
        try:
            await asyncio.wait_for(self.wait_for_congratulations(message, wait_until, reference_message), timeout=self.wait_time)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout reached in channel {message.channel.id}. Allowing all to catch.")
            await self.allow_all_to_catch(message)
        finally:
            self.active_events.pop(message.channel.id, None)

    async def wait_for_congratulations(self, message, wait_until, reference_message):
        def check(m): return m.channel.id == message.channel.id and m.author.id == self.detect_bot_id and m.id not in self.handled_congrats and re.match(r"Congratulations <@(\d+)>! You caught a Level \d+ .+", m.content)
        try:
            congrats_message = await self.bot.wait_for('message', check=check, timeout=max(0, wait_until - time.time()))
            self.handled_congrats.add(congrats_message.id)
            await self.process_congratulations(congrats_message, message, reference_message)
        except asyncio.TimeoutError:
            logger.warning(f"Timeout: No congratulatory message detected in channel {message.channel.id}.")
            await self.allow_all_to_catch(message)
        except Exception as e:
            logger.error(f"Unexpected error in wait_for_congratulations: {e}")
            traceback.print_exc()

    async def process_congratulations(self, congrats_message, original_message, reference_message):
        try:
            self.shiny_ping_phrase = PokemonThiefUtils.load_ping_phrase()
            catch_channel = reference_message.channel
            mentioned_user_id = re.search(r"<@(\d+)>", reference_message.content).group(1)
            who_caught_pokemon_user_id = re.search(r"<@(\d+)>", congrats_message.content).group(1)
            if who_caught_pokemon_user_id not in congrats_message.content:
                await catch_channel.send(f"⚠️ Something weird is going on. Please submit the issue and screenshot to https://discord.com/channels/1278580577104040018/1307894465440256100.")
                return
            quest_user_ids = await self.thief_handler.extract_user_ids_from_ping(reference_message.content, self.shiny_ping_phrase)
            if who_caught_pokemon_user_id not in quest_user_ids:
                is_shiny_hunter = await self.bot.get_cog('Anti_Thief').is_shiny_hunter(int(who_caught_pokemon_user_id))
                if not is_shiny_hunter:
                    non_hunter = await self.bot.fetch_user(who_caught_pokemon_user_id)
                    pokemon_name = await self.thief_handler.extract_pokemon_name(congrats_message)
                    await self.thief_handler.timeout_user(non_hunter, original_message.guild.id)
                    embed = Embed(title="Shiny Thief Detected!", description=f"<:sigh:1328502167153410068> {non_hunter.mention} stole **{pokemon_name}**. They've been timed out for 3 hours.", color=self.primary_color)
                    await catch_channel.send(embed=embed)
                    await self.thief_handler.log_theft_incident(non_hunter, pokemon_name, catch_channel, original_message.jump_url)
                    return
            shiny_hunters = await self.bot.get_cog('Anti_Thief').process_pings(reference_message.guild.id, reference_message.content)
            shiny_hunter = next((hunter for hunter in shiny_hunters if str(hunter.id) == mentioned_user_id), None)
            if shiny_hunter:
                embed = Embed(title=":sparkles: Congratulations!", description=f"Best of luck on your shiny hunt, <@{who_caught_pokemon_user_id}>!", color=self.primary_color)
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1328500899953512569.webp?size=96&animated=true")
                await catch_channel.send(embed=embed)
                await self.delete_embed_on_catch(original_message)
            else:
                await catch_channel.send("⚠️ No shiny hunter detected for the channel. Please double-check.")
        except Exception as e:
            logger.error(f"Unexpected error in process_congratulations: {e}")
            traceback.print_exc()

    @staticmethod
    async def allow_all_to_catch(message):
        embed = message.embeds[0]
        embed.description = ":white_check_mark: Everyone may catch the Pokémon now! No restrictions."
        await message.edit(embed=embed)

    @staticmethod
    async def delete_embed_on_catch(message):
        try:
            await message.delete()
        except Exception as e:
            logger.error(f"Error deleting embed: {e}")

def setup(bot):
    bot.add_cog(Anti_Thief(bot))
    bot.add_cog(EventGate(bot))
