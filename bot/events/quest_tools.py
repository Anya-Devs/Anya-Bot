import re, os
from bot.cogs.quest import Quest_Data
from imports.discord_imports import * 
from imports.log_imports import *

from bot.utils.events.quest_tools import *

class Quest_Tools(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        db_name = 'Quest'  
        self.db_manager = DatabaseManager(db_name)
        self.quest_data = Quest_Data(bot)
        self.tool_handler = ToolHandler(bot, self.db_manager, self.quest_data)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author == self.bot.user or message.channel.id == 1278580578593148978 or len(message.content.split()) < 2: return
        tool_id = message.content.split()[0]
        if not re.match(r'^\d{6}$', tool_id): return
        try:
            mentioned_user = message.mentions[0] if message.mentions else None
            if mentioned_user:
                logger.info(f"Tool_ID: {tool_id} detected in message {message.id}, Target_ID: {mentioned_user.id} mentioned")
                guild_id, user_id = str(message.guild.id), str(message.author.id)
                db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
                server_collection = db['Servers']
                user_data = await server_collection.find_one(
                    {'guild_id': guild_id, f'members.{user_id}': {'$exists': True}},
                    {f'members.{user_id}.inventory.tool'}
                )
                inventory = user_data.get('members', {}).get(user_id, {}).get('inventory', {}).get('tool', {})
                if inventory:
                    logger.info(f"Inventory for User {message.author.display_name} (ID: {message.author.id}):")
                    for tool, tool_data in inventory.items():
                        tool_name = tool.capitalize()
                        tool_id_in_inventory = await self.quest_data.get_existing_tool_id(guild_id, user_id, tool)
                        logger.info(f" - Tool: {tool_name} (Tool_ID: {tool_id_in_inventory})")
                        if str(tool_id_in_inventory) == tool_id:
                            logger.info(f"Match found: Tool ID {tool_id} matches {tool_name}")
                            await self.tool_handler.apply_tool_effect(message.author.id, mentioned_user.id, tool_name, message.channel)
                            break
                    else:
                        logger.info(f"No match found for Tool_ID: {tool_id} in the inventory.")
                else:
                    logger.info(f"User {message.author.display_name} (ID: {message.author.id}) has an empty inventory.")
            else:
                logger.info("No user mentioned in the message.")
        except Exception as e:
            logger.error(f"Error processing tool in message {message.id}: {e}")

async def setup(bot):
    quest_data = Quest_Data(bot)
    mongo_url = os.getenv('MONGO_URI')  
    db_name = 'Quest'  
    await bot.add_cog(Quest_Tools(bot, mongo_url, db_name, quest_data))
