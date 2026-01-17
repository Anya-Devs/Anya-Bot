import asyncio, datetime, re, os, requests, json, logging
from imports.discord_imports import *
from data.local.const import primary_color
from bot.token import get_bot_token

logger = logging.getLogger(__name__)


# Ensure data directory exists
os.makedirs("data/commands/pokethief", exist_ok=True)
CONFIG_PATH = "data/commands/pokethief/shiny_ping_config.json"


def load_ping_phrase() -> str:
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f).get("shiny_ping_phrase", "**:sparkles: Shiny Hunt Pings:**")
    return "**:sparkles: Shiny Hunt Pings:**"


def save_ping_phrase(new_phrase: str):
    with open(CONFIG_PATH, 'w') as f:
        json.dump({"shiny_ping_phrase": new_phrase}, f, indent=4)



class PokemonThiefUtils:
    

    @staticmethod
    def timestamp_gen(timestamp: int) -> str:
        return f'<t:{int(datetime.datetime.utcfromtimestamp(timestamp).replace(tzinfo=datetime.timezone.utc).timestamp())}:R>'
    
    @staticmethod
    def load_ping_phrase():
        config_path = "data/commands/pokethief/shiny_ping_config.json"

        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                return json.load(file).get("shiny_ping_phrase", "**:sparkles: Shiny Hunt Pings:**")
        return "**:sparkles: Shiny Hunt Pings:**"
    
    @staticmethod
    def save_ping_phrase(new_phrase):
        config_path = "data/commands/pokethief/shiny_ping_config.json"

        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as file:
            json.dump({"shiny_ping_phrase": new_phrase}, file, indent=4)

class ShinyHunterManager:
    def __init__(self, bot):
        self.bot = bot
        self.shiny_hunters = []
        self.shiny_ping_phrase = PokemonThiefUtils.load_ping_phrase()
        self.shiny_regex = r"<@(\d+)>"
    
    async def get_member(self, guild, user_id):
        try:
            return await guild.fetch_member(user_id) if isinstance(guild, int) else self.bot.get_guild(guild).fetch_member(user_id)
        except Exception as e:
            logger.error(f"Error fetching member {user_id}: {e}")
            return None
    
    async def process_pings(self, guild, message_content):
        shiny_hunters = []
        if self.shiny_ping_phrase in message_content:
            mention_part = message_content.split(self.shiny_ping_phrase)[1].split("\n")[0].strip()
            if mention_part:
                shiny_hunters = [member for member in [await self.get_member(guild, int(user_id)) for user_id in re.findall(self.shiny_regex, mention_part)] if member]
        return shiny_hunters
    
    async def is_shiny_hunter(self, user_id):
        return any(hunter.id == user_id for hunter in self.shiny_hunters)
    
    def update_ping_phrase(self, new_phrase):
        self.shiny_ping_phrase = new_phrase
        PokemonThiefUtils.save_ping_phrase(new_phrase)
        return True

class PokemonThiefHandler:
    def __init__(self, bot):
        self.bot = bot
        self.timeout_duration = datetime.timedelta(hours=3)
        self.primary_color = primary_color()
        self.logger_channel_id = 1278580578593148976

    async def extract_user_ids_from_ping(self, message_content, shiny_ping_phrase):
        quest_user_ids = []
        if shiny_ping_phrase in message_content:
            shiny_ping_block = re.search(re.escape(shiny_ping_phrase) + r"(.*?)(?:\n\S|$)", message_content, re.DOTALL).group(1).strip()
            quest_user_ids = re.findall(r"<@(\d+)>", shiny_ping_block)
        return quest_user_ids
    
    async def extract_pokemon_name(self, congrats_message):
        return re.search(r"Level \d+ ((?:[A-Z][a-z]*\s*)+)", congrats_message.content).group(1).strip() if re.search(r"Level \d+ ((?:[A-Z][a-z]*\s*)+)", congrats_message.content) else "Unknown Pokémon"
    
    async def timeout_user(self, user, guild_id):
        BOT_TOKEN = await get_bot_token()
        timeout_end = datetime.datetime.utcnow() + datetime.timedelta(minutes=180)
        response = requests.patch(f"https://discord.com/api/v10/guilds/{guild_id}/members/{user.id}", json={"communication_disabled_until": timeout_end.isoformat() + "Z"}, headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"})
        if response.status_code == 204:
            logger.info(f"User {user.mention} timed out for 3 hours.")
            return True
        logger.error(f"Failed to timeout user {user.mention}: {response.status_code}")
        return False
    
    async def log_theft_incident(self, thief, pokemon_name, channel, message_url):
        try:
            log_embed = Embed(title="Shiny Theft", description=f"**User:** {thief.mention} (`{thief.id}`)\n**Pokémon:** {pokemon_name}\n**Location:** [{channel.name}]({message_url})", color=self.primary_color)
            log_embed.set_thumbnail(url=thief.avatar)
            log_embed.set_footer(icon_url=self.bot.user.avatar, text='Anya Logger')
            await self.bot.get_channel(self.logger_channel_id).send(embed=log_embed)
            return True
        except Exception as e:
            logger.error(f"Error logging theft incident: {e}")
            return False
