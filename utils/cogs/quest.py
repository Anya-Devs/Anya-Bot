
import os
import datetime
import random
import string
import typing
import traceback
import asyncio
import random
from io import BytesIO
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

 

import json
import numpy as np
import motor.motor_asyncio
from pymongo.errors import PyMongoError



from data.local.const import *
from data.commands.quest.data import *
from imports.discord_imports import *
from imports.log_imports import *
from utils.cogs.quest import *




import discord
import traceback
from discord.ui import View

class Quest_View(View):
    def __init__(self, bot, all_quests, ctx, page=0, filtered_quests=None):
        super().__init__(timeout=None)
        self.bot = bot
        self.all_quests = all_quests
        self.filtered_quests = filtered_quests if filtered_quests is not None else all_quests
        self.ctx = ctx
        self.page = page
        self.max_pages = (len(self.filtered_quests) + 4) // 5  # ceil division (5 per page)

        try:
            self.add_item(Quest_Select_Filter(bot, self.all_quests, ctx))

            if self.max_pages > 1:
                self.add_item(
                    Quest_Select(bot, self.filtered_quests, ctx, self.max_pages, self.all_quests)
                )
            if self.page > 0:
                self.add_item(
                    QuestButton(
                        "Previous",
                        discord.ButtonStyle.primary,
                        "previous",
                        bot,
                        self.filtered_quests,
                        ctx,
                        self.page,
                        self.all_quests,
                    )
                )
            if self.page < self.max_pages - 1:
                self.add_item(
                    QuestButton(
                        "Next",
                        discord.ButtonStyle.primary,
                        "next",
                        bot,
                        self.filtered_quests,
                        ctx,
                        self.page,
                        self.all_quests,
                    )
                )

            self.add_item(
                QuestButton(
                    "Fresh Start",
                    discord.ButtonStyle.danger,
                    "fresh_start",
                    bot,
                    self.filtered_quests,
                    ctx,
                    self.page,
                    self.all_quests,
                )
            )
        except Exception as e:
            print(f"[Quest_View Init Error] {e}")
            traceback.print_exc()

    async def generate_messages(self):
        try:
            start_index = self.page * 5
            index = start_index
            embed = discord.Embed(color=primary_color())
            embed.set_footer(
                text=f"{self.ctx.author.display_name}'s quests",
                icon_url=self.ctx.author.avatar,
            )

            field_count = 0
            while field_count < 5 and index < len(self.filtered_quests):
                quest = self.filtered_quests[index]
                index += 1

                quest_id = quest["quest_id"]
                progress = quest["progress"]
                times = quest["times"]
                method = quest["method"]
                content = quest["content"]
                reward = quest["reward"]
                percent = int((progress / times) * 100) if times > 0 else 0

                channel = self.bot.get_channel(int(quest["channel_id"]))

                if method == "message":
                    instruction = "Send: {0}".format(content.replace("\n", " "))
                elif method == "emoji":
                    instruction = f"Send emoji: {content}"
                elif method == "reaction":
                    instruction = f"React with: {content}"
                else:
                    instruction = "Unknown method. Please refer to the quest details."

                progress_bar = await Quest_Progress.generate_progress_bar(
                    progress / times if times > 0 else 0, self.bot
                )

                reward_emoji_id = 1247800150479339581
                reward_emoji = discord.utils.get(self.bot.emojis, id=reward_emoji_id)
                instructions_emoji = "📍"

                if channel:
                    channel_link = (
                        f"[Go here](https://discord.com/channels/{self.ctx.guild.id}/{channel.id})"
                        if channel.id != self.ctx.channel.id
                        else "In this channel"
                    )
                    can_view_channel = channel.permissions_for(self.ctx.author).view_channel
                else:
                    channel_link = f"Channel not found | Recommended: `{self.ctx.prefix}quest delete quest_id: {quest_id}`"
                    can_view_channel = True  # Show to allow deletion recommendation

                if not can_view_channel:
                    continue

                # Inspired by leaderboard: #ID - Instruction   bar   percent%
                message = (
                    f"#{quest_id} - **{instruction}**\n"
                    f"`{progress}/{times}` {progress_bar} `{percent}%`\n"
                    f"`•` {instructions_emoji} {channel_link}\n"
                    f"`└─` {reward_emoji} Reward: `{reward} stp`\n\n"
                )

                embed.add_field(name="", value=message, inline=False)
                field_count += 1

            file = discord.File("data/images/generated_image.png", filename="image.png")
            embed.set_image(url=f"attachment://image.png")

            return embed

        except Exception as e:
            print(f"[Quest_View generate_messages Error] {e}")
            traceback.print_exc()
            return discord.Embed(
                description="⚠️ Something went wrong while generating the quest messages.",
                color=discord.Color.red()
            )
   

class Quest_Select(Select):
    def __init__(self, bot, filtered_quests, ctx, max_pages, all_quests):
        options = [
            discord.SelectOption(label=f"Page {i+1}", value=str(i))
            for i in range(max_pages)
        ]
        super().__init__(placeholder="Select page...", options=options)
        self.bot = bot
        self.all_quests = all_quests
        self.filtered_quests = filtered_quests
        self.ctx = ctx
        self.max_pages = max_pages

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "This is not your section.", ephemeral=True
            )
            return

        try:
            page_index = int(self.values[0])
            view = Quest_View(
                self.bot,
                self.all_quests,
                self.ctx,
                page=page_index,
                filtered_quests=self.filtered_quests,
            )
            embed = await view.generate_messages()
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            print(error_message)
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await self.ctx.send(f"{error_message}")


class Quest_Select_Filter(Select):
    def __init__(self, bot, all_quests, ctx):
        methods = list(set(quest["method"] for quest in all_quests))
        options = [
            discord.SelectOption(label=method.title(), value=method)
            for method in methods
        ]
        options.insert(0, discord.SelectOption(label="All", value="all"))
        super().__init__(placeholder="Filter...", options=options)
        self.bot = bot
        self.all_quests = all_quests
        self.ctx = ctx

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "This is not your section.", ephemeral=True
            )
            return

        try:
            selected_method = self.values[0]
            if selected_method == "all":
                filtered_quests = None
            else:
                filtered_quests = [
                    quest for quest in self.all_quests if quest["method"] == selected_method
                ]

            view = Quest_View(
                self.bot, self.all_quests, self.ctx, filtered_quests=filtered_quests
            )
            embed = await view.generate_messages()
            await interaction.response.edit_message(embed=embed, view=view)
        except Exception as e:
            error_message = "An error occurred while fetching quests."
            print(error_message)
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await self.ctx.send(f"{error_message}")


class QuestButton(discord.ui.Button):
    def __init__(self, label, style, custom_id, bot, filtered_quests, ctx, page, all_quests):
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.bot = bot
        self.all_quests = all_quests
        self.filtered_quests = filtered_quests
        self.ctx = ctx
        self.page = page
        self.quest_data = Quest_Data(bot)

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user != self.ctx.author:
                await interaction.response.send_message(
                    "This is not your section.", ephemeral=True
                )
                return

            embed = None
            view = None

            if self.custom_id == "previous":
                self.page -= 1
            elif self.custom_id == "next":
                self.page += 1
            elif self.custom_id == "fresh_start":
                success = await self.quest_data.delete_all_quests(
                    self.ctx.guild.id, self.ctx.author
                )
                if success:
                    embed = discord.Embed(
                        description=f":white_check_mark: All quests have been deleted for you {self.ctx.author.mention}. Starting fresh!",
                        color=discord.Color.green(),
                    )
                    self.page = 0
                    self.all_quests = []
                    self.filtered_quests = []
                    view = None
                    # Clear attachments
                    await interaction.response.edit_message(embed=embed, view=view, attachments=[])
                    return
                else:
                    embed = discord.Embed(
                        description="You have no quests.", color=discord.Color.red()
                    )
                    view = Quest_View(self.bot, self.all_quests, self.ctx, self.page)

            if not embed:
                view = Quest_View(self.bot, self.all_quests, self.ctx, self.page, self.filtered_quests)
                embed = await view.generate_messages()

            await interaction.response.edit_message(embed=embed, view=view)

        except Exception as e:
            # Print the full traceback for debugging
            print("Exception in QuestButton callback:")
            traceback.print_exc()
            print(f"Error: {e}")

            # Send error feedback to user
            try:
                await interaction.response.send_message(
                    f":x: An error occurred: `{e}`", ephemeral=True
                )
            except discord.InteractionResponded:
                # If response already sent, follow up
                await interaction.followup.send(
                    f":x: An error occurred: `{e}`", ephemeral=True
                )
class Quest_Button1(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def add_user_to_server(self):
        logger.debug("Adding user to server.")
        try:
            user_id = str(self.ctx.author.id)
            guild_id = str(self.ctx.guild.id)
            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")

            if user_id not in users_in_server:
                await self.quest_data.add_user_to_server(user_id, guild_id)
                return True
            else:
                return False
        except Exception as e:
            error_message = "An error occurred while adding user to server."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, self.ctx, error_message, title="Add User Error"
            )
            return False

    @discord.ui.button(label="New Quest", style=discord.ButtonStyle.success)
    async def new_quest_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        try:
            
            guild_id = str(interaction.guild.id)
            channel_id = await self.quest_data.get_random_channel_for_guild(guild_id)

            if not channel_id:
                
                await interaction.response.edit_message(
                    content="No redirected channels found for this guild. Please set redirect channels before creating a new quest.\n"
                    f"> Ask a member with permission to manage channels or with the Anya Manager role to use the command: `{self.ctx.prefix}redirect <channels>`"
                )
                return  

            
            button_user = interaction.user

            
            await self.quest_data.add_balance(button_user, guild_id, 0)

            
            for _ in range(50):
                logger.debug("Adding new quest")
                await self.quest_data.add_new_quest(guild_id, button_user, chance=100)

            
            await interaction.response.edit_message(
                content=f"Successfully created new quests for you, {button_user.mention}!",
                embed=None,
                view=None,
            )

        except Exception as e:
            error_message = "An error occurred while processing the new quest button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, self.ctx, error_message, title="Button Error"
            )

class Quest_Button1(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def add_user_to_server(self):
        logger.debug("Adding user to server.")
        try:
            user_id = str(self.ctx.author.id)
            guild_id = str(self.ctx.guild.id)
            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")

            if user_id not in users_in_server:
                await self.quest_data.add_user_to_server(user_id, guild_id)
                return True
            else:
                return False
        except Exception as e:
            error_message = "An error occurred while adding user to server."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, self.ctx, error_message, title="Add User Error"
            )
            return False

    @discord.ui.button(label="New Quest", emoji="➕", style=discord.ButtonStyle.gray)
    async def new_quest_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        try:
            
            guild_id = str(button.guild.id)
            channel_id = await self.quest_data.get_random_channel_for_guild(guild_id)

            if not channel_id:
                
                await button.response.edit_message(
                    content="No redirected channels found for this guild. Please set redirect channels before creating a new quest.\n"
                    f"> Ask a member with permission to manage channels or with the Anya Manager role to use the command: `{self.ctx.prefix}redirect <channels>`"
                )
                return  

            
            button_user = button.user

            
            await self.quest_data.add_balance(button_user, guild_id, 0)

            
            for _ in range(50):
                logger.debug("Adding new quest")
                await self.quest_data.add_new_quest(guild_id, button_user, chance=100)

            
            await button.response.edit_message(
                content=f"Successfully created new quests for you, {button_user.mention}!",
                embed=None,
                view=None,
            )

        except Exception as e:
            error_message = "An error occurred while processing the new quest button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, self.ctx, error_message, title="Button Error"
            )


class Quest_Button(discord.ui.View):
    def __init__(self, bot, ctx):
        super().__init__()
        self.ctx = ctx
        self.bot = bot
        self.quest_data = Quest_Data(bot)

    async def add_user_to_server(self):
        logger.debug("Adding user to server.")
        try:
            user_id = str(self.ctx.author.id)
            guild_id = str(self.ctx.guild.id)
            users_in_server = await self.quest_data.find_users_in_server(guild_id)
            logger.debug(f"Users in server: {users_in_server}")

            if user_id not in users_in_server:
                await self.quest_data.add_user_to_server(user_id, guild_id)
                return True
            else:
                return False
        except Exception as e:
            error_message = "An error occurred while adding user to server."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, self.ctx, error_message, title="Add User Error"
            )
            return False

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        guild_id = str(button.guild.id)
        channel_id = await self.quest_data.get_random_channel_for_guild(guild_id)
        if not channel_id:
            
            await button.response.send_message(
                "No redirected channels found for this guild. Please set redirect channels before creating a new quest.\n"
                f"> Ask a member with permission to manage channels or with the Anya Manager role to use the command: `{self.ctx.prefix}redirect <channels>`",
                ephemeral=True,
            )
            return  
        try:
            added = await self.add_user_to_server()

            if added:
                
                guild_id = str(button.guild.id)

                
                embed = await QuestEmbed.get_agree_confirmation_embed(
                    bot=self.bot, user=button.user, prefix=self.ctx.prefix
                )
                await button.response.send_message(embed=embed)
                await button.followup.delete_message(button.message.id)

                button_user = button.user

                
                await self.quest_data.add_balance(button_user, guild_id, 0)

                
                for _ in range(10):
                    logger.debug("Adding new quest")
                    await self.quest_data.add_new_quest(
                        guild_id, button_user, chance=100
                    )

            else:
                
                await button.response.send_message(
                    "You are already part of the game!",
                    ephemeral=True,
                    mention_author=False,
                )
                await button.followup.edit_message(button.message.id, view=None)
        except Exception as e:
            error_message = "An error occurred while processing the accept button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot,
                self.ctx,
                error_message,
                title="Button Error",
                mention_author=False,
            )

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(
        self, button: discord.ui.Button, interaction: discord.Interaction
    ):
        try:
            embed = discord.Embed(
                title="Quest Canceled",
                description="You have declined the quest.",
                color=discord.Color.red(),
            )
            await button.response.edit_message(embed=embed, view=None)
        except Exception as e:
            error_message = "An error occurred while processing the decline button."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, self.ctx, error_message, title="Button Error"
            )


class ImageGenerator:
    def __init__(self, ctx, text, config_path="data/commands/quest/image/quest_view.json"):
        self.config_path = config_path
        self.description_text = text

        self.config = self._load_config()
        self._apply_config()

        self._load_resources()
        self._apply_color_replacements()

    def _load_config(self):
        with open(self.config_path, "r") as file:
            return json.load(file)

    def _apply_config(self):
        """Assign config values to class attributes."""
        cfg = self.config

        self.font_path_header = cfg.get("font_path_header")
        self.font_path_description = cfg.get("font_path_description")
        self.character_path = cfg.get("character_path")
        self.background_path = cfg.get("background_path")

        self.header_font_size = cfg.get("header_font_size", 35)
        self.description_font_size = cfg.get("description_font_size", 11)

        self.header_font_color = cfg.get("header_font_color", "white")
        self.description_font_color = cfg.get("description_font_color", "black")

        self.character_scale = cfg.get("character_scale", 0.4)

        self.header_text = cfg.get("header_text", "Quest!")
        # description_text is dynamic, not from config

        self.character_pos = tuple(cfg.get("character_pos", (5, 5)))
        self.text_x_offset = cfg.get("text_x_offset", 10)
        self.text_y_offset = cfg.get("text_y_offset", 25)
        self.text_spacing = cfg.get("text_spacing", 20)
        self.text_box_margin = cfg.get("text_box_margin", 20)

        self.color_replacements_map = cfg.get("color_replacements_map", {})

    def _load_resources(self):
        """Load fonts and images."""
        try:
            self.header_font = ImageFont.truetype(
                self.font_path_header, self.header_font_size
            )
        except Exception:
            self.header_font = ImageFont.load_default()

        try:
            self.description_font = ImageFont.truetype(
                self.font_path_description, self.description_font_size
            )
        except Exception:
            self.description_font = ImageFont.load_default()

        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")

        self._resize_character()

    def _resize_background(self):
        config = self._load_config()
        new_width = round(self.background.width * config["background_scale"])
        new_height = round(self.background.height * config["background_scale"])
        self.background = self.background.resize((new_width, new_height))


    def _resize_character(self):
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height))

    def _apply_color_replacements(self):
        bg_array = np.array(self.background).copy()

        for old_hex, replacement in self.color_replacements_map.items():
            old_color = tuple(int(old_hex[i: i + 2], 16) for i in (0, 2, 4))
            lower_bound = np.array(old_color) - 10
            upper_bound = np.array(old_color) + 10

            if replacement == "transparent":
                mask = cv2.inRange(bg_array[:, :, :3], lower_bound, upper_bound)
                bg_array[mask > 0] = [0, 0, 0, 0]
            elif replacement.startswith("http"):
                replacement_img = self._download_image(replacement)
                replacement_img = replacement_img.resize(
                    (self.background.width, self.background.height)
                )
                replacement_array = np.array(replacement_img)[:, :, :3]
                mask = cv2.inRange(bg_array[:, :, :3], lower_bound, upper_bound)
                bg_array[mask > 0, :3] = replacement_array[mask > 0]
            else:
                replacement_color = tuple(
                    int(replacement[i: i + 2], 16) for i in (1, 3, 5)
                )
                mask = cv2.inRange(bg_array[:, :, :3], lower_bound, upper_bound)
                bg_array[mask > 0, :3] = replacement_color

        self.background = Image.fromarray(bg_array, "RGBA")

    def _wrap_text(self, text, max_width):
        lines = []
        words = text.split()
        current_line = []

        dummy_img = Image.new("RGBA", (1, 1))
        draw = ImageDraw.Draw(dummy_img)

        for word in words:
            current_line.append(word)
            line_width = draw.textlength(" ".join(current_line), font=self.description_font)
            if line_width > max_width:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    def _draw_text(self, draw, text_x, text_y):
        draw.text(
            (text_x, text_y),
            self.header_text,
            font=self.header_font,
            fill=self.header_font_color,
        )
        text_y += self.header_font.size + self.text_spacing

        text_box_width = self.background.width - text_x - self.text_box_margin * 2
        wrapped_text = self._wrap_text(self.description_text, text_box_width)
        draw.multiline_text(
            (text_x + self.text_box_margin, text_y),
            wrapped_text,
            font=self.description_font,
            fill=self.description_font_color,
        )

    @staticmethod
    def _download_image(url):
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content)).convert("RGBA")

    def create_image(self):
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)
        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        text_x = self.character.width + self.text_x_offset - 45
        text_y = self.text_y_offset
        self._draw_text(draw, text_x, text_y)

        return bg

    def save_image(self, file_path):
        img = self.create_image()
        img.save(file_path)
        return file_path

    def show_image(self):
        img = self.create_image()
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        return img_bytes.getvalue()


class Quest_Data(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_NAME = "Quest"
        
        # Get MongoDB connection
        mongo_url = os.getenv("MONGO_URI")
        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)

        # Initialize the main database manager with all nested classes
        self.db_manager = DatabaseManager(self.mongoConnect, self.DB_NAME, self.bot)
        
        # Keep references for backward compatibility and easier access
        self.config = self.db_manager.config
        self.quest_content_file = self.config.quest_content_file

    async def handle_error(self, interaction, error, title):
        # This would need to be imported from wherever error_custom_embed is defined
        # await error_custom_embed(self.bot, interaction, str(error), title=title)
        pass

    @staticmethod
    async def validate_input(**kwargs):
        for key, value in kwargs.items():
            if value is None or value == "":
                raise ValueError(f"{key} cannot be None or empty")

    # Role methods - delegate to nested RoleClass
    async def store_roles_for_guild(self, guild_id, role_ids):
        return await self.db_manager.roles.store_roles_for_guild(guild_id, role_ids)

    async def get_roles_for_guild(self, guild_id):
        return await self.db_manager.roles.get_roles_for_guild(guild_id)

    # Inventory methods - delegate to nested InventoryClass
    async def get_user_inventory_count(self, guild_id: str, user_id: str, material_name: str) -> int:
        return await self.db_manager.inventory.get_user_inventory_count(guild_id, user_id, material_name)

    async def add_item_to_inventory(self, guild_id: str, user_id: str, material_name: str, quantity: int) -> None:
        return await self.db_manager.inventory.add_item_to_inventory(guild_id, user_id, material_name, quantity)

    # Tool methods - delegate to nested ToolClass
    async def get_existing_tool_id(self, guild_id: str, user_id: str, tool_name: str) -> str:
        return await self.db_manager.tools.get_existing_tool_id(guild_id, user_id, tool_name)

    async def get_quantity(self, guild_id: str, user_id: str, material_name: str) -> int:
        return await self.db_manager.tools.get_quantity(guild_id, user_id, material_name)

    async def add_tool_to_inventory(self, guild_id: str, user_id: str, material_name: str, quantity: int) -> None:
        return await self.db_manager.tools.add_tool_to_inventory(guild_id, user_id, material_name, quantity)

    async def remove_tool_from_inventory(self, guild_id: str, user_id: str, tool_name: str) -> None:
        return await self.db_manager.tools.remove_tool_from_inventory(guild_id, user_id, tool_name)

    async def create_un_tool_id(self, guild_id, user_id, tool):
        return await self.db_manager.tools.create_un_tool_id(guild_id, user_id, tool)

    async def get_un_tool_id(self, guild_id, user_id, tool):
        return await self.db_manager.tools.get_un_tool_id(guild_id, user_id, tool)

    # Server methods - delegate to nested ServerClass
    async def find_user_in_server(self, user_id: str, guild_id: str) -> bool:
        return await self.db_manager.server.find_user_in_server(user_id, guild_id)

    async def find_users_in_server(self, guild_id: str):
        return await self.db_manager.server.find_users_in_server(guild_id)

    async def add_user_to_server(self, user_id: str, guild_id: str):
        return await self.db_manager.server.add_user_to_server(user_id, guild_id)

    # Channel methods - delegate to nested ChannelClass
    async def get_random_channel_for_guild(self, guild_id: str, fallback_channel=None):
        return await self.db_manager.channels.get_random_channel_for_guild(guild_id, fallback_channel)

    async def store_channels_for_guild(self, guild_id: str, channel_ids: list):
        return await self.db_manager.channels.store_channels_for_guild(guild_id, channel_ids)

    async def get_most_active_channel(self, guild_id, threshold=5, message_limit=100, fallback_channel_id=None):
        return await self.db_manager.channels.get_most_active_channel(guild_id, threshold, message_limit, fallback_channel_id)

    # Balance methods - delegate to nested BalanceClass
    async def get_balance(self, user_id: str, guild_id: str):
        return await self.db_manager.balance.get_balance(user_id, guild_id)

    async def add_balance(self, user_id: str, guild_id: str, amount: int):
        return await self.db_manager.balance.add_balance(user_id, guild_id, amount)

    async def initialize_balance(self, user_id: str, guild_id: str):
        return await self.db_manager.balance.initialize_balance(user_id, guild_id)

    # Quest methods - delegate to nested QuestClass (no more complex patching needed!)
    async def remove_all_server_quests(self, guild_id: str) -> None:
        return await self.db_manager.quests.remove_all_server_quests(guild_id)

    async def get_server_quest_count(self, guild_id: str) -> int:
        return await self.db_manager.quests.get_server_quest_count(guild_id)

    async def get_beginner_quests(self, guild_id: str) -> List[Dict[str, Union[str, int]]]:
        return await self.db_manager.quests.get_beginner_quests(guild_id)

    async def set_quest_limit(self, guild_id: str, limit: int) -> None:
        return await self.db_manager.quests.set_quest_limit(guild_id, limit)

    async def get_quest_limit(self, guild_id: str) -> int:
        return await self.db_manager.quests.get_quest_limit(guild_id)

    async def find_users_with_quest(self, guild_id: str, quest_id: int):
        return await self.db_manager.quests.find_users_with_quest(guild_id, quest_id)

    async def find_quests_by_user_and_server(self, user_id: str, guild_id: str, interaction=None):
        return await self.db_manager.quests.find_quests_by_user_and_server(user_id, guild_id, interaction)

    async def insert_quest(self, guild_id: str, user_id: str, quest_data: dict, interaction=None):
        return await self.db_manager.quests.insert_quest(guild_id, user_id, quest_data, interaction)

    async def get_latest_quest_id(self, guild_id: str, user_id: str, interaction=None) -> int:
        return await self.db_manager.quests.get_latest_quest_id(guild_id, user_id, interaction)

    async def store_server_quest(self, guild_id: str, quest_data: dict):
        return await self.db_manager.quests.store_server_quest(guild_id, quest_data)

    async def server_quests(self, guild_id: str):
        return await self.db_manager.quests.server_quests(guild_id)

    # Simplified quest methods - no more complex patching needed!
    async def create_quest(self, guild_id: str, action: str, method: str, content: str, times: int, reward: int, interaction=None):
        return await self.db_manager.quests.create_quest(guild_id, action, method, content, times, reward, interaction)

    async def create_member_quest(self, guild_id: str, user_id: str, action: str, method: str, content: str, times: int, interaction=None):
        return await self.db_manager.quests.create_member_quest(guild_id, user_id, action, method, content, times, interaction)

    async def generate_random_quest_content(self, bot, author, guild_id):
        return await self.db_manager.quests.generate_random_quest_content(bot, author, guild_id)

    async def generate_random_reaction_content(self, guild_id):
        return await self.db_manager.quests.generate_random_reaction_content(guild_id)

    async def insert_quest_existing_path(self, guild_id: str, user_id: str, quest_data: dict, interaction=None):
        return await self.db_manager.quests.insert_quest_existing_path(guild_id, user_id, quest_data, interaction)

    async def add_new_quest(self, guild_id, message_author, action="send", method=None, chance=50):
        return await self.db_manager.quests.add_new_quest(guild_id, message_author, action, method, chance)

    async def delete_all_quests(self, guild_id, message_author):
        return await self.db_manager.quests.delete_all_quests(guild_id, message_author)

    async def delete_quest(self, guild_id: str, quest_id: int, interaction=None):
        return await self.db_manager.quests.delete_quest(guild_id, quest_id, interaction)

    async def delete_quest_for_user(self, guild_id: str, user_id: str, quest_id: int, interaction=None):
        return await self.db_manager.quests.delete_quest_for_user(guild_id, user_id, quest_id, interaction)

    async def update_quest_progress(self, guild_id: str, user_id: str, quest_id: int, progress: int):
        return await self.db_manager.quests.update_quest_progress(guild_id, user_id, quest_id, progress)






























#----------------------------------------------------




class InventoryView(discord.ui.View):
    def __init__(self, quest_data, guild_id, user_id, author):
        super().__init__(timeout=300)
        self.quest_data = quest_data
        self.guild_id = guild_id
        self.user_id = user_id
        self.author = author
        self.message = None

    async def start(self, ctx):
        try:
            # Create main inventory embed
            embed = discord.Embed(
                title=f"{self.author.display_name}'s Inventory",
                description="```ansi\n\u001b[35mSelect a category to view your items\u001b[0m```",
                color=primary_color(),
                timestamp=datetime.now(),
            )
            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text="Inventory")

            # Add category selector
            category_select = InventoryCategorySelect(
                self.quest_data, self.guild_id, self.user_id, self.author, self
            )
            self.add_item(category_select)

            self.message = await ctx.reply(embed=embed, view=self, mention_author=False)
        except Exception as e:
            await self.handle_error(ctx, e)

    @staticmethod
    async def handle_error(interaction, exception):
        traceback_msg = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        error_message = f"An error occurred: {exception}\n\n```{traceback_msg}```"
        print(traceback_msg)
        if hasattr(interaction, 'response'):
            await interaction.response.send_message(error_message, ephemeral=True)
        else:
            await interaction.reply(error_message, mention_author=False)


class InventoryCategorySelect(discord.ui.Select):
    def __init__(self, quest_data, guild_id, user_id, author, parent_view):
        options = [
            discord.SelectOption(
                emoji="🕵️",
                label="Spy Tools",
                description="Tools for espionage and tactical operations",
                value="spy_tools"
            ),
            discord.SelectOption(
                emoji="🎨",
                label="Profile Customization",
                description="Backgrounds, fonts, and decorative items",
                value="profile_customization"
            ),
            discord.SelectOption(
                emoji="💎",
                label="Collectables",
                description="Rare items and collectible treasures",
                value="collectables"
            ),
            discord.SelectOption(
                emoji="🎰",
                label="Gacha Games",
                description="Random item draws and loot boxes",
                value="gacha_games"
            ),
            discord.SelectOption(
                emoji="⚙️",
                label="Server Utils",
                description="Server management and utility tools",
                value="server_utils"
            ),
            discord.SelectOption(
                emoji="🐾",
                label="Pokemon Spawns",
                description="Pokemon decorations and spawn items",
                value="pokemon_spawns"
            )
        ]
        super().__init__(placeholder="📦 Select an inventory category", options=options)
        self.quest_data = quest_data
        self.guild_id = guild_id
        self.user_id = user_id
        self.author = author
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        try:
            # Check if user owns this interaction
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your inventory interface.", ephemeral=True
                )
                return

            category = self.values[0]
            
            if category == "spy_tools":
                await self.show_spy_tools(interaction)
            elif category == "profile_customization":
                await self.show_profile_customization(interaction)
            elif category == "collectables":
                await self.show_collectables(interaction)
            elif category == "gacha_games":
                await self.show_gacha_games(interaction)
            elif category == "server_utils":
                await self.show_server_utils(interaction)
            elif category == "pokemon_spawns":
                await self.show_pokemon_spawns(interaction)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

    async def show_spy_tools(self, interaction: discord.Interaction):
        try:
            # Get spy tools from inventory
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": self.guild_id, f"members.{self.user_id}": {"$exists": True}},
                {f"members.{self.user_id}.inventory.tool"},
            )

            tools = (
                user_data.get("members", {})
                .get(self.user_id, {})
                .get("inventory", {})
                .get("tool", {})
            )

            if not tools:
                embed = discord.Embed(
                    title="🕵️ Spy Tools Inventory",
                    description="You don't have any spy tools yet. Visit the shop to get some!",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
            else:
                embed = discord.Embed(
                    title="🕵️ Spy Tools Inventory",
                    description="Your collection of spy tools",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )

                for tool_name in tools.keys():
                    try:
                        # Get tool ID
                        un_tool_id = await self.quest_data.get_existing_tool_id(
                            self.guild_id, self.user_id, tool_name
                        )

                        if not un_tool_id:
                            un_tool_id = await self.quest_data.create_un_tool_id(
                                self.guild_id, self.user_id, tool_name
                            )

                        # Get quantity
                        quantity = await self.quest_data.get_quantity(
                            self.guild_id, self.user_id, tool_name
                        )

                        # Get emoji
                        emoji = self.get_tool_emoji(tool_name) or "🔧"

                        embed.add_field(
                            name=f"{tool_name.title()}",
                            value=f"`{un_tool_id}` : \t{emoji}\t`x{quantity}`",
                            inline=False,
                        )
                    except Exception as e:
                        logger.error(f"Error processing tool {tool_name}: {e}")

            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text="Spy Tools Inventory")
            
            # Update the main message instead of sending ephemeral
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching spy tools: {e}", ephemeral=True
            )

    async def show_profile_customization(self, interaction: discord.Interaction):
        try:
            # Get profile customization items from inventory
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": self.guild_id, f"members.{self.user_id}": {"$exists": True}},
                {f"members.{self.user_id}.inventory"},
            )

            inventory = (
                user_data.get("members", {})
                .get(self.user_id, {})
                .get("inventory", {})
            )

            # Look for profile customization items (backgrounds, fonts, items)
            profile_items = {}
            for category in ["backgrounds", "fonts", "items"]:
                if category in inventory:
                    profile_items[category] = inventory[category]

            if not profile_items:
                embed = discord.Embed(
                    title="🎨 Profile Customization Inventory",
                    description="You don't have any profile customization items yet. Visit the shop to get some!",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
            else:
                embed = discord.Embed(
                    title="🎨 Profile Customization Inventory",
                    description="Your collection of profile customization items",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )

                for category, items in profile_items.items():
                    if items:
                        items_list = []
                        for item_name, quantity in items.items():
                            emoji = "🖼️" if category == "backgrounds" else "🔤" if category == "fonts" else "🎯"
                            items_list.append(f"{emoji} {item_name.title()} `x{quantity}`")
                        
                        embed.add_field(
                            name=f"{category.title()}",
                            value="\n".join(items_list[:5]) + ("\n..." if len(items_list) > 5 else ""),
                            inline=False,
                        )

            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text="Profile Customization Inventory")
            
            # Update the main message instead of sending ephemeral
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching profile items: {e}", ephemeral=True
            )

    async def show_collectables(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💎 Collectables Inventory",
            description="Coming soon! Your collectible treasures will be displayed here.",
            color=primary_color(),
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=self.author.avatar.url)
        embed.set_footer(text="Collectables Inventory")
        
        # Update the main message instead of sending ephemeral
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    async def show_gacha_games(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎰 Gacha Games Inventory",
            description="Coming soon! Your gacha items and loot will be displayed here.",
            color=primary_color(),
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=self.author.avatar.url)
        embed.set_footer(text="Gacha Games Inventory")
        
        # Update the main message instead of sending ephemeral
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    async def show_server_utils(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚙️ Server Utils Inventory",
            description="Coming soon! Your server management tools will be displayed here.",
            color=primary_color(),
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=self.author.avatar.url)
        embed.set_footer(text="Server Utils Inventory")
        
        # Update the main message instead of sending ephemeral
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    async def show_pokemon_spawns(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🐾 Pokemon Spawns Inventory",
            description="Coming soon! Your Pokemon items and decorations will be displayed here.",
            color=primary_color(),
            timestamp=datetime.now(),
        )
        embed.set_thumbnail(url=self.author.avatar.url)
        embed.set_footer(text="Pokemon Spawns Inventory")
        
        # Update the main message instead of sending ephemeral
        await interaction.response.edit_message(embed=embed, view=self.parent_view)

    def get_tool_emoji(self, tool_name):
        """Get emoji for a tool - you'll need to implement this based on your existing logic"""
        # This should match your existing get_tool_emoji method
        tool_emojis = {
            "lockpick": "🔓",
            "camera": "📷",
            "microphone": "🎤",
            "binoculars": "🔭",
            "disguise": "🥸",
            # Add more tool emojis as needed
        }
        return tool_emojis.get(tool_name.lower(), "🔧")












#----------------------------------------------------







class ShopView(discord.ui.View):
    def __init__(self, bot, shop_data: Union[str, dict] = "data/commands/quest/shop.json"):
        super().__init__(timeout=300)
        self.bot = bot
        self.quest_data = Quest_Data(bot)

        if isinstance(shop_data, dict):
            self.shop_data = shop_data
            self.shop_data_path = None
        else:
            self.shop_data_path = shop_data
            self.shop_data = self.load_shop_data()

        self.materials_dict = {
            material["name"]: material.get("emoji", "")
            for material in self.shop_data.get("Materials", {}).get("items", [])
        }

    def load_shop_data(self) -> Dict[str, Any]:
        """Load shop data from JSON file"""
        try:
            with open(self.shop_data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Shop data file {self.shop_data_path} not found")
            return {}
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON from {self.shop_data_path}: {e}")
            return {}

    async def start(self, ctx):
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            balance = await self.quest_data.get_balance(user_id, guild_id)
            balance = "{:,}".format(balance)

            shop_embed = await ShopEmbed.start_shop_embed(self.bot, ctx, balance)

            # Add category selector
            category_select = ShopCategorySelect(
                self.shop_data, self.materials_dict, self.quest_data, user_id, guild_id
            )
            self.add_item(category_select)

            await ctx.send(embed=shop_embed, view=self)
        except Exception as e:
            await self.handle_error(ctx, e)

    @staticmethod
    async def handle_error(interaction, exception):
        traceback_msg = "".join(
            traceback.format_exception(
                type(exception), exception, exception.__traceback__
            )
        )
        error_message = f"An error occurred: {exception}\n\n```{traceback_msg}```"
        print(traceback_msg)
        await interaction.response.send_message(error_message, ephemeral=True)

class ShopCategorySelect(discord.ui.Select):
    def __init__(self, shop_data, materials_dict, quest_data, user_id, guild_id):
        options = [
            discord.SelectOption(
                emoji="🕵️",
                label="Spy Tools",
                description="Tools for espionage and tactical operations",
                value="spy_tools"
            ),
            discord.SelectOption(
                emoji="🎨",
                label="Profile Customization",
                description="Backgrounds, fonts, and decorative items",
                value="profile_customization"
            ),
            discord.SelectOption(
                emoji="🎰",
                label="Gacha Games",
                description="Random item draws and loot boxes",
                value="gacha_games"
            ),
            discord.SelectOption(
                emoji="🐾",
                label="Poketwo Spawns",
                description="Poketwo decorations and spawn layout",
                value="pokemon_spawns"
            )
        ]
        super().__init__(placeholder="🛒 Select a shop category", options=options)
        self.shop_data = shop_data
        self.materials_dict = materials_dict
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your shop interface.", ephemeral=True
                )
                return

            category = self.values[0]
            
            if category == "spy_tools":
                await self.show_spy_tools(interaction)
            elif category == "profile_customization":
                await self.show_profile_customization(interaction)
            elif category == "gacha_games":
                await self.show_gacha_games(interaction)
            elif category == "pokemon_spawns":
                await self.show_pokemon_spawns(interaction)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

    async def show_spy_tools(self, interaction: discord.Interaction):
        spy_tools = self.shop_data.get("SpyTools", {}).get("items", [])
        if not spy_tools:
            await interaction.response.send_message(
                "No spy tools available at the moment.", ephemeral=True
            )
            return

        select = SpyToolSelect(
            self.shop_data, self.materials_dict, self.quest_data, self.user_id, self.guild_id
        )
        
        embed = discord.Embed(
            title="🕵️ Spy Tools Shop",
            description="Select a spy tool to view details and purchase materials",
            color=primary_color()
        )
        embed.set_image(url='https://media.discordapp.net/attachments/1279353553110040596/1419515254928441457/a6acb170-e5e2-4067-8ef9-c86816de741e_removalai_preview.png?ex=68d20a1a&is=68d0b89a&hm=886f70b5200954e636d2421ef1dc0de8e27309062a712aaa586d36b87560384a&=&format=webp&quality=lossless&width=675&height=203')
        
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_profile_customization(self, interaction: discord.Interaction):
        profile_data = self.shop_data.get("ProfileCustomization", {})
        if not profile_data:
            await interaction.response.send_message(
                "No profile customization options available.", ephemeral=True
            )
            return

        select = ProfileFamilySelect(
            self.shop_data, self.quest_data, self.user_id, self.guild_id
        )
        
        embed = discord.Embed(
            title="🎨 Profile Customization Shop",
            description="Customize your profile with backgrounds, fonts, and items",
            color=primary_color()
        )
        embed.set_image(url='https://media.discordapp.net/attachments/1279353553110040596/1419486274531889262/04310b69-499a-4487-90ea-027bfce4a0aa_removalai_preview.png?ex=68d1ef1c&is=68d09d9c&hm=bdcfe7804bc82b0e7c1fb8e4fca55a24c2d89efdc535b2224590fca059984325&=&format=webp&quality=lossless&width=675&height=320')
        view = discord.ui.View()
        view.add_item(select)
        
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_gacha_games(self, interaction: discord.Interaction):
        gacha_games = self.shop_data.get("GachaGames", {}).get("items", [])
        if not gacha_games:
            await interaction.response.send_message(
                "No gacha games available at the moment.", ephemeral=True
            )
            return

        view = ItemListView(
            gacha_games, "GachaGames", "🎰", self.quest_data, self.user_id, self.guild_id
        )
        await view.update_view()
        
        embed = discord.Embed(
            title="🎰 Gacha Games",
            description="Try your luck with random item draws and loot boxes",
            color=primary_color()
        )
        embed.set_image(url="https://media.discordapp.net/attachments/1279353553110040596/1419526087402197032/AAHar4d7MANRf42MFGfA2njCtEHCWpykVRKDnJLC3meHNd3HyA6KVzcjTfiaF58RFnziXWuDf0swhWDC3kTrBb0JIqrzN5-0twFmxzxrBJEA9sAVinvI4LByafkDoMUL4UWa0tgruwHvxW5i0ESq45EewiR-3amR-MH5uTzga5xpatWp0zvgt75HteP9DjdqkUKkVg6xsiOZQy8RIY2vBW-w0jMvoK5pv3CCqMAyImtPQEHw68_RNHwvGkXd0C9GYu4d-m8zs-o8ERpPRdupKVdrAcPbV93QcyQ9YRId.png?ex=68d21430&is=68d0c2b0&hm=a117830714a0dc5fa87a468c238476b906936fcdc31ced2bbcd5ae426910ce7c&=&format=webp&quality=lossless")

        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_pokemon_spawns(self, interaction: discord.Interaction):
     pokemon_spawns = self.shop_data.get("PoketwoSpawns", {})
     if not pokemon_spawns:
        await interaction.response.send_message(
            "No Pokemon spawn items available at the moment.", ephemeral=True
        )
        return

     main_description = pokemon_spawns.get("main_description", "")
     sections = pokemon_spawns.get("sections", {})

     if not sections:
        await interaction.response.send_message(
            "No Pokemon spawn sections available at the moment.", ephemeral=True
        )
        return

     # build select using section keys
     select = PokemonSpawnSectionSelect(
        self.shop_data, self.quest_data, self.user_id, self.guild_id
     )

     embed = discord.Embed(
        title="🐾 Poketwo Spawns Shop",
        description=main_description or "Select a section to browse Pokemon spawn items",
        color=primary_color()
     )
     embed.set_image(url="https://media.discordapp.net/attachments/1279353553110040596/1419478776613699665/ad51d45f-70b8-4a52-99ff-f87592ce3d2c_removalai_preview.png")

     view = discord.ui.View()
     view.add_item(select)

     await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class ItemListView(discord.ui.View):
    def __init__(self, items, category, emoji, quest_data, user_id, guild_id):
        super().__init__(timeout=300)
        self.items = items
        self.category = category
        self.emoji = emoji
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.page = 0
        self.items_per_page = 10
        self.max_pages = (len(items) - 1) // self.items_per_page + 1 if items else 1

    async def create_shop_embed(self):
        """Create the shop embed with item list and purchase indicators"""
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        current_items = self.items[start_index:end_index]
        
        embed = discord.Embed(
            title=f"{self.emoji} {self.category} Shop",
            description=f"Browse and purchase items (Page {self.page + 1}/{self.max_pages})",
            color=primary_color()
        )
        
        item_list = []
        for i, item in enumerate(current_items):
            user_quantity = await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, item["name"]
            ) or 0
            
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            
            if user_quantity > 0:
                indicator = "✅"
                name_display = f"~~{item['name']}~~"
            elif user_balance >= item["points"]:
                indicator = "💰"
                name_display = item['name']
            else:
                indicator = "❌"
                name_display = item['name']
            
            item_emoji = item.get('emoji', '')
            price_display = f"{item['points']:,} pts"
            rarity = item.get('rarity', 'N/A')
            
            item_entry = f"{indicator} {item_emoji} **{name_display}** - {price_display} (Rarity: {rarity})"
            if user_quantity > 0:
                item_entry += f" (Owned: {user_quantity})"
            
            item_list.append(f"`{start_index + i + 1}.` {item_entry}")
        
        if item_list:
            embed.add_field(
                name="Items Available",
                value="\n".join(item_list),
                inline=False
            )
        
        legend = "> ✅ Owned | 💰 Can Purchase | ❌ Insufficient Points"
        embed.add_field(name="", value=legend, inline=False)
        
        user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
        embed.set_footer(text=f"Your Balance: {user_balance:,} Stella Points")
        
        return embed

    async def update_view(self):
        self.clear_items()
        
        if not self.items:
            return
        
        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        current_items = self.items[start_index:end_index]
        
        current_row = 0
        for i, item in enumerate(current_items):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, item["name"]
            ) or 0
            
            if user_quantity > 0:
                button_style = discord.ButtonStyle.green
                disabled = True
            elif user_balance >= item["points"]:
                button_style = discord.ButtonStyle.primary
                disabled = False
            else:
                button_style = discord.ButtonStyle.grey
                disabled = True
            
            button = discord.ui.Button(
                style=button_style,
                label=str(i + 1),
                custom_id=f"item_{start_index + i}",
                row=current_row,
                disabled=disabled
            )
            button.callback = self.item_callback
            self.add_item(button)
            
            if (i + 1) % 5 == 0:
                current_row += 1
        
        pagination_row = current_row + 1 if current_row < 4 else 4
        
        if self.max_pages > 1:
            if self.page > 0:
                prev_button = discord.ui.Button(
                    emoji="⬅️",
                    style=discord.ButtonStyle.secondary,
                    custom_id="prev_page",
                    row=pagination_row
                )
                prev_button.callback = self.prev_page_callback
                self.add_item(prev_button)
            
            if self.page < self.max_pages - 1:
                next_button = discord.ui.Button(
                    emoji="➡️",
                    style=discord.ButtonStyle.secondary,
                    custom_id="next_page",
                    row=pagination_row
                )
                next_button.callback = self.next_page_callback
                self.add_item(next_button)

    async def item_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your shop interface.", ephemeral=True
                )
                return

            item_index = int(interaction.data["custom_id"].split("_")[1])
            item = self.items[item_index]
            
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, item["name"]
            ) or 0
            
            if user_quantity > 0:
                embed = discord.Embed(
                    title="ℹ️ Already Owned",
                    description=f"You already own **{item['name']}** (Quantity: {user_quantity})",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            
            if user_balance >= item["points"]:
                await self.quest_data.add_balance(self.user_id, self.guild_id, -item["points"])
                await self.quest_data.add_item_to_inventory(
                    self.guild_id, self.user_id, item["name"], 1
                )
                
                embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=f"You've purchased **{item['name']}** for {item['points']:,} points!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Description", value=item["description"], inline=False)
                if "emoji" in item:
                    embed.add_field(name="Item", value=item["emoji"], inline=True)
                if "rarity" in item:
                    embed.add_field(name="Rarity", value=item["rarity"], inline=True)
                
                new_balance = user_balance - item["points"]
                embed.set_footer(text=f"Remaining balance: {new_balance:,} points")
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
                await self.refresh_shop_view(interaction)
                
            else:
                embed = discord.Embed(
                    title="❌ Insufficient Points",
                    description=f"You need {item['points']:,} points but only have {user_balance:,}.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

    async def refresh_shop_view(self, interaction):
        try:
            embed = await self.create_shop_embed()
            await self.update_view()
            original_message = interaction.message
            if original_message:
                await original_message.edit(embed=embed, view=self)
        except:
            pass

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.page -= 1
        embed = await self.create_shop_embed()
        await self.update_view()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.page += 1
        embed = await self.create_shop_embed()
        await self.update_view()
        await interaction.response.edit_message(embed=embed, view=self)

class Config:
    EMOJIS = {
        "backgrounds": "🖼️",
        "fonts": "🔤",
        "items": "🎯",
        "owned": "<:check:1399603549100441723>",
        "insufficient": "<:x_:1399603637105463386>",
        "purchase": "💰",
        "prev": "⬅️",
        "next": "➡️",
        "default_family": "❔",
        "shop": "🎨",
        "info": "ℹ️",
        "success": "✅",
        "error": "❌"
    }

class ProfileFamilySelect(Select):
    def __init__(self, shop_data, quest_data, user_id, guild_id):
        options = []
        profile_customization = shop_data.get("ProfileCustomization", {})
        
        for family in ["ForgerFamily", "WISE", "EdenAcademy", "Garden", "Extras"]:
            data = profile_customization.get(family, {})
            emoji = None
            for category in ["Backgrounds", "Fonts", "Items"]:
                items = data.get(category, [])
                if items:
                    emoji = items[0].get("emoji")
                    if emoji:
                        break
            if not emoji:
                emoji = Config.EMOJIS["default_family"]
            
            description = f"{family} themed items"
            options.append(discord.SelectOption(label=family, description=description, value=family, emoji=emoji))

        super().__init__(placeholder="Select a character family", options=options)
        self.shop_data = shop_data
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                await interaction.response.send_message("This is not your customization interface.", ephemeral=True)
                return

            family = self.values[0]
            profile_data = self.shop_data.get("ProfileCustomization", {}).get(family, {})
            if not profile_data:
                await interaction.response.send_message(f"No {family} customization options available.", ephemeral=True)
                return

            options = []
            for item_type in ["Backgrounds", "Fonts", "Items"]:
                if item_type in profile_data:
                    emoji = Config.EMOJIS[item_type.lower()]
                    description = f"{item_type} ({len(profile_data[item_type])} available)"
                    options.append(discord.SelectOption(label=item_type, description=description, value=item_type, emoji=emoji))

            type_select = ProfileTypeSelect(profile_data, family, self.quest_data, self.user_id, self.guild_id)
            type_select.options = options
            
            view = View()
            view.add_item(type_select)

            embed = discord.Embed(
                title=f"{Config.EMOJIS['shop']} {family} Customization",
                description="Choose the type of customization item you want to browse",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

class ProfileTypeSelect(Select):
    def __init__(self, profile_data, family, quest_data, user_id, guild_id):
        super().__init__(placeholder="Select item type")
        self.profile_data = profile_data
        self.family = family
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                await interaction.response.send_message("This is not your customization interface.", ephemeral=True)
                return

            item_type = self.values[0]
            items = self.profile_data.get(item_type, [])
            if not items:
                await interaction.response.send_message(f"No {item_type.lower()} available for {self.family}.", ephemeral=True)
                return

            item_view = ProfileItemView(items, item_type, self.quest_data, self.user_id, self.guild_id, self.family)
            embed = await item_view.create_shop_embed()
            await item_view.update_view()
            await interaction.response.edit_message(embed=embed, view=item_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

class ProfileItemView(View):
    def __init__(self, items, item_type, quest_data, user_id, guild_id, family):
        super().__init__(timeout=300)
        self.items = items
        self.item_type = item_type
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.family = family
        self.page = 0
        self.items_per_page = 10
        self.max_pages = (len(items) - 1) // self.items_per_page + 1

    async def create_shop_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        embed = discord.Embed(
            title=f"{Config.EMOJIS['shop']} {self.family} {self.item_type}",
            description=f"Browse and purchase {self.item_type.lower()} for your profile (Page {self.page + 1}/{self.max_pages})",
            color=primary_color()
        )

        item_list = []
        for i, item in enumerate(current_items):
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, item["name"]) or 0
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            if user_quantity > 0:
                indicator = Config.EMOJIS["owned"]
                name_display = f"~~{item['name']}~~"
            elif user_balance >= item["points"]:
                indicator = Config.EMOJIS["purchase"]
                name_display = item["name"]
            else:
                indicator = Config.EMOJIS["insufficient"]
                name_display = item["name"]

            price_display = f"{item['points']:,} pts"
            character = item.get("character", "N/A")
            item_entry = f"{indicator} **{name_display}** - {price_display}"
            if user_quantity > 0:
                item_entry += f" (Owned: {user_quantity})"
            item_entry += f"\n╰➺   *{character}* - {item['description'][:50]}...\n"
            item_list.append(f"`{start + i + 1}.` {item_entry}")

        if item_list:
            embed.add_field(name="Items Available", value="\n".join(item_list), inline=False)
        embed.add_field(name="", value=f"> {Config.EMOJIS['owned']} Owned | {Config.EMOJIS['purchase']} Can Purchase | {Config.EMOJIS['insufficient']} Insufficient Points", inline=False)
        embed.set_footer(text=f"Your Balance: {await self.quest_data.get_balance(self.user_id, self.guild_id):,} Stella Points")
        return embed

    async def update_view(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        for i, item in enumerate(current_items):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, item["name"]) or 0

            if user_quantity > 0:
                style, disabled = discord.ButtonStyle.green, True
            elif user_balance >= item["points"]:
                style, disabled = discord.ButtonStyle.primary, False
            else:
                style, disabled = discord.ButtonStyle.grey, True

            btn = Button(style=style, label=str(i + 1), custom_id=f"item_{start + i}", disabled=disabled)
            btn.callback = self.item_callback
            self.add_item(btn)

        if self.max_pages > 1:
            if self.page > 0:
                prev_btn = Button(emoji=Config.EMOJIS["prev"], style=discord.ButtonStyle.secondary, custom_id="prev_page")
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)
            if self.page < self.max_pages - 1:
                next_btn = Button(emoji=Config.EMOJIS["next"], style=discord.ButtonStyle.secondary, custom_id="next_page")
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

    async def item_callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                await interaction.response.send_message("This is not your shop interface.", ephemeral=True)
                return

            index = int(interaction.data["custom_id"].split("_")[1])
            item = self.items[index]
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, item["name"]) or 0

            if user_quantity > 0:
                return await interaction.response.send_message(embed=discord.Embed(
                    title=f"{Config.EMOJIS['info']} Already Owned",
                    description=f"You already own **{item['name']}** (Quantity: {user_quantity})",
                    color=discord.Color.blue()
                ), ephemeral=True)

            if user_balance >= item["points"]:
                await self.quest_data.add_balance(self.user_id, self.guild_id, -item["points"])
                await self.quest_data.add_item_to_inventory(self.guild_id, self.user_id, item["name"], 1)
                new_balance = user_balance - item["points"]
                embed = discord.Embed(
                    title=f"{Config.EMOJIS['success']} Purchase Successful!",
                    description=f"You've purchased **{item['name']}** for {item['points']:,} points!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Description", value=item["description"], inline=False)
                embed.add_field(name="Character", value=item.get("character", "N/A"), inline=True)
                embed.set_footer(text=f"Remaining balance: {new_balance:,} points")
                await interaction.response.edit_message(embed=embed, view=self)
                await self.refresh_shop_view(interaction)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title=f"{Config.EMOJIS['error']} Insufficient Points",
                    description=f"You need {item['points']:,} points but only have {user_balance:,}.",
                    color=discord.Color.red()
                ), ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def refresh_shop_view(self, interaction):
        try:
            embed = await self.create_shop_embed()
            await self.update_view()
            if interaction.message:
                await interaction.message.edit(embed=embed, view=self)
        except:
            pass

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.page -= 1
        embed = await self.create_shop_embed()
        await self.update_view()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.page += 1
        embed = await self.create_shop_embed()
        await self.update_view()
        await interaction.response.edit_message(embed=embed, view=self)

class MaterialsButton(discord.ui.View):
    def __init__(self, shop_data, quest_data, user_id, guild_id, original_embed=None):
        super().__init__(timeout=300)
        self.shop_data = shop_data
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.page = 0
        self.items_per_page = 25
        self.max_pages = (len(shop_data["Materials"]["items"]) - 1) // self.items_per_page + 1
        self.original_embed = original_embed
        self.materials_dict = {
            material["name"]: material.get("emoji", "")
            for material in self.shop_data.get("Materials", {}).get("items", [])
        }

    async def update_view(self):
        self.clear_items()

        material_checks = await asyncio.gather(
            *(
                self.check_material_indicator(material)
                for material in self.shop_data["Materials"]["items"]
            )
        )

        if all(material_checks):
            buy_button = discord.ui.Button(
                style=discord.ButtonStyle.green,
                label="Buy Tool",
                custom_id="buy_button",
                row=0,
                disabled=False,
            )
            buy_button.callback = self.buy_tool_callback
            self.add_item(buy_button)
        else:
            buy_button = discord.ui.Button(
                style=discord.ButtonStyle.grey,
                label="Buy Tool",
                custom_id="buy_button",
                row=0,
                disabled=True,
            )
            self.add_item(buy_button)

        tool_name = self.original_embed.title
        tool = next(
            (
                t
                for t in self.shop_data.get("SpyTools", {}).get("items", [])
                if t.get("name") == tool_name
            ),
            None,
        )

        if tool:
            required_materials = tool.get("materials", [])
        else:
            required_materials = []

        start_index = self.page * self.items_per_page
        end_index = start_index + self.items_per_page
        filtered_materials = [
            material for material in self.shop_data["Materials"]["items"]
            if material["name"] in [m.get("material") for m in required_materials]
        ][start_index:end_index]

        current_row = 1
        item_count = 0

        for material in filtered_materials:
            try:
                name = material.get("name", "Unknown Material")
                emoji = material.get("emoji", "")
                price = material.get("price", "")

                material_button = discord.ui.Button(
                    style=discord.ButtonStyle.primary,
                    emoji=emoji,
                    label=f"{price} stp",
                    custom_id=name,
                    row=current_row,
                )
                material_button.callback = self.material_callback
                self.add_item(material_button)
                item_count += 1

                if item_count % 5 == 0:
                    current_row += 1
                    item_count = 0

            except Exception as e:
                print(f"Error generating button for material: {name}, Emoji: {emoji}")
                print(f"Error: {e}")
                continue

        pagination_row = current_row if current_row > 1 else 2

        if self.page > 0:
            prev_button = discord.ui.Button(
                emoji="⬅️",
                style=discord.ButtonStyle.secondary,
                custom_id="prev_page",
                row=pagination_row,
            )
            prev_button.callback = self.prev_page_callback
            self.add_item(prev_button)

        if self.page < self.max_pages - 1:
            next_button = discord.ui.Button(
                emoji="➡️",
                style=discord.ButtonStyle.secondary,
                custom_id="next_page",
                row=pagination_row,
            )
            next_button.callback = self.next_page_callback
            self.add_item(next_button)

    async def refresh_embed(self, interaction: discord.Interaction):
        tool_name = self.original_embed.title
        tool = next(
            (
                t
                for t in self.shop_data.get("SpyTools", {}).get("items", [])
                if t.get("name") == tool_name
            ),
            None,
        )

        if not tool:
            await interaction.response.send_message(
                "Spy Tool not found.", ephemeral=True
            )
            return

        emoji = tool.get("emoji", "")
        description = tool.get("description", "No description available.")
        materials_list = "\n".join(
            [await self.format_materials(item) for item in tool.get("materials", [])]
        )
        user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

        shop_embed = discord.Embed(
            title=f"{tool_name}",
            description=f"{emoji} {description}",
            color=primary_color(),
        )
        shop_embed.add_field(
            name="Materials Required",
            value=materials_list or "No materials needed",
            inline=False,
        )
        user_balance = "{:,}".format(user_balance)
        shop_embed.set_footer(text=f"Stella Points: {user_balance}")

        await self.update_view()
        await interaction.response.edit_message(embed=shop_embed, view=self)

    async def check_material_indicator(self, material):
        material_name = material.get("name", "")
        tool_name = self.original_embed.title
        tool = next(
            (
                t
                for t in self.shop_data.get("SpyTools", {}).get("items", [])
                if t.get("name") == tool_name
            ),
            None,
        )
        
        if not tool:
            return False
            
        required_material = next(
            (m for m in tool.get("materials", []) if m.get("material") == material_name),
            None
        )
        
        if not required_material:
            return True
            
        required_quantity = required_material.get("quantity", 0)
        user_quantity = (
            await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, material_name
            )
            or 0
        )
        return user_quantity >= required_quantity

    async def format_materials(self, item):
        material_name = item.get("material", "")
        required_quantity = item.get("quantity", 0)
        user_quantity = await self.get_user_inventory_count(material_name) or 0

        if user_quantity == 0:
            indicator_emoji = "<:red:1261639413943762944>"
        elif user_quantity < required_quantity:
            indicator_emoji = "<:yellow:1261639412253724774>"
        else:
            indicator_emoji = "<:green:1261639410181476443>"

        return f"{indicator_emoji} {self.materials_dict.get(material_name, '')} **{material_name}** - {user_quantity}/{required_quantity}"

    async def get_user_inventory_count(self, material_name):
        material_count = await self.quest_data.get_user_inventory_count(
            self.guild_id, self.user_id, material_name
        )
        return material_count

    async def material_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your shop interface.", ephemeral=True
                )
                return

            material_name = interaction.data["custom_id"]
            material = next(
                (
                    m
                    for m in self.shop_data["Materials"]["items"]
                    if m.get("name") == material_name
                ),
                None,
            )

            if not material:
                await interaction.response.send_message(
                    "Material not found.", ephemeral=True
                )
                return

            price = material.get("price", 0)
            user_balance = await self.quest_data.get_balance(
                self.user_id, self.guild_id
            )

            if user_balance >= price:
                await self.quest_data.add_item_to_inventory(
                    self.guild_id, self.user_id, material_name, 1
                )
                spent = -price
                await self.quest_data.add_balance(self.user_id, self.guild_id, spent)

                await self.refresh_embed(interaction)
            else:
                await interaction.response.send_message(
                    f"You do not have enough points to purchase {material_name}.",
                    ephemeral=True,
                )

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

    async def buy_tool_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your shop interface.", ephemeral=True
                )
                return

            tool_name = self.original_embed.title
            tool = next(
                (
                    t
                    for t in self.shop_data.get("SpyTools", {}).get("items", [])
                    if t.get("name") == tool_name
                ),
                None,
            )

            if not tool:
                await interaction.response.send_message(
                    "Spy Tool not found.", ephemeral=True
                )
                return

            for material in tool.get("materials", []):
                material_name = material.get("material", "")
                required_quantity = material.get("quantity", 0)
                user_quantity = (
                    await self.quest_data.get_user_inventory_count(
                        self.guild_id, self.user_id, material_name
                    )
                    or 0
                )

                if user_quantity < required_quantity:
                    await interaction.response.send_message(
                        f"Not enough {material_name}. You need {required_quantity} but have {user_quantity}.",
                        ephemeral=True
                    )
                    return

            for material in tool.get("materials", []):
                material_name = material.get("material", "")
                required_quantity = material.get("quantity", 0)
                await self.quest_data.add_item_to_inventory(
                    self.guild_id, self.user_id, material_name, -required_quantity
                )

            await self.quest_data.add_item_to_inventory(
                self.guild_id, self.user_id, tool_name, 1
            )

            quantity = await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, tool_name
            )

            success_embed = discord.Embed(
                title="✅ Purchase Successful",
                description=f"**{tool_name}** has been added to your inventory.\nYou now have {quantity} of this tool.",
                color=discord.Color.green(),
            )

            await interaction.response.send_message(embed=success_embed, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.page -= 1
        await self.refresh_embed(interaction)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.page += 1
        await self.refresh_embed(interaction)

class SpyToolSelect(discord.ui.Select):
    def __init__(self, shop_data, materials_dict, quest_data, user_id, guild_id):
        options = [
            discord.SelectOption(
                label=tool["name"],
                description=tool["description"][:100],
                emoji=tool.get("emoji", "🕵️"),
                value=tool["name"]
            ) for tool in shop_data.get("SpyTools", {}).get("items", [])
        ]
        super().__init__(placeholder="Select a spy tool", options=options)
        self.shop_data = shop_data
        self.materials_dict = materials_dict
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your shop interface.", ephemeral=True
                )
                return

            tool_name = self.values[0]
            tool = next(
                (t for t in self.shop_data.get("SpyTools", {}).get("items", []) if t["name"] == tool_name),
                None
            )

            if not tool:
                await interaction.response.send_message(
                    "Spy Tool not found.", ephemeral=True
                )
                return

            emoji = tool.get("emoji", "")
            description = tool.get("description", "No description available.")
            materials_list = "\n".join(
                [await self.format_materials(item) for item in tool.get("materials", [])]
            )
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            shop_embed = discord.Embed(
                title=f"{tool_name}",
                description=f"{emoji} {description}",
                color=primary_color(),
            )
            shop_embed.add_field(
                name="Materials Required",
                value=materials_list or "No materials needed",
                inline=False,
            )
            user_balance = "{:,}".format(user_balance)
            shop_embed.set_footer(text=f"Stella Points: {user_balance}")

            view = MaterialsButton(
                self.shop_data,
                self.quest_data,
                self.user_id,
                self.guild_id,
                shop_embed
            )
            await view.update_view()

            await interaction.response.send_message(embed=shop_embed, view=view, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

    async def format_materials(self, item):
        material_name = item.get("material", "")
        required_quantity = item.get("quantity", 0)
        user_quantity = (
            await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, material_name
            ) or 0
        )

        if user_quantity == 0:
            indicator_emoji = "<:red:1261639413943762944>"
        elif user_quantity < required_quantity:
            indicator_emoji = "<:yellow:1261639412253724774>"
        else:
            indicator_emoji = "<:green:1261639410181476443>"

        return f"{indicator_emoji} {self.materials_dict.get(material_name, '')} **{material_name}** - {user_quantity}/{required_quantity}"

class CollectablesGenerator:
    @staticmethod
    def generate_collectable():
        """Generate a unique collectable with a rarity seed value"""
        base_names = [
            "Anya's Peanut", "Loid's Disguise Kit", "Yor's Thorn Dagger", "Bond's Collar Tag",
            "Franky's Gadget Blueprint", "Sylvia's Directive Scroll", "Fiona's Nightfall Veil",
            "Chimera Plush Variant", "WISE Encryption Device", "Forger Family Photo"
        ]
        prefixes = ["Legendary", "Epic", "Rare", "Uncommon", "Common"]
        suffixes = ["Relic", "Artifact", "Treasure", "Memento", "Heirloom"]
        
        # Generate unique ID
        collectable_id = str(uuid.uuid4())
        
        # Randomly combine elements for name
        name_parts = [
            random.choice(prefixes),
            random.choice(base_names),
            random.choice(suffixes)
        ]
        name = " ".join(name_parts)
        
        # Generate rarity seed (0 to 100)
        rarity_seed = random.uniform(0, 100)
        if rarity_seed >= 95:
            rarity = "Legendary"
            points = 50000
        elif rarity_seed >= 85:
            rarity = "Epic"
            points = 30000
        elif rarity_seed >= 70:
            rarity = "Rare"
            points = 15000
        elif rarity_seed >= 50:
            rarity = "Uncommon"
            points = 8000
        else:
            rarity = "Common"
            points = 4000
        
        # Generate description
        description = f"A {rarity.lower()} collectable inspired by Spy x Family. ID: {collectable_id[:8]}"
        
        return {
            "id": collectable_id,
            "name": name,
            "description": description,
            "emoji": "💎",
            "points": points,
            "rarity": rarity
        }

class GachaGameView(discord.ui.View):
    def __init__(self, gacha_games, quest_data, user_id, guild_id):
        super().__init__(timeout=300)
        self.gacha_games = gacha_games
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def update_view(self):
        self.clear_items()
        for i, game in enumerate(self.gacha_games):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            button = discord.ui.Button(
                style=discord.ButtonStyle.primary if user_balance >= game["points"] else discord.ButtonStyle.grey,
                label=f"{game['name']} ({game['points']:,} pts)",
                custom_id=f"gacha_{i}",
                emoji=game.get("emoji", "🎰"),
                disabled=user_balance < game["points"]
            )
            button.callback = self.gacha_callback
            self.add_item(button)

    async def gacha_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your gacha interface.", ephemeral=True
                )
                return

            index = int(interaction.data["custom_id"].split("_")[1])
            game = self.gacha_games[index]
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            if user_balance < game["points"]:
                await interaction.response.send_message(
                    f"You need {game['points']:,} points but only have {user_balance:,}.",
                    ephemeral=True
                )
                return

            # Deduct points
            await self.quest_data.add_balance(self.user_id, self.guild_id, -game["points"])

            # Generate random collectable
            collectable = CollectablesGenerator.generate_collectable()
            await self.quest_data.add_item_to_inventory(
                self.guild_id, self.user_id, collectable["name"], 1
            )

            embed = discord.Embed(
                title="🎰 Gacha Result",
                description=f"You opened a **{game['name']}** and received:\n**{collectable['name']}** ({collectable['rarity']})!",
                color=discord.Color.green()
            )
            embed.add_field(name="Description", value=collectable["description"], inline=False)
            embed.set_footer(text=f"Remaining balance: {user_balance - game['points']:,} points")

            await interaction.response.send_message(embed=embed, ephemeral=True)
            await self.refresh_view(interaction)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def refresh_view(self, interaction):
        try:
            embed = discord.Embed(
                title="🎰 Gacha Games",
                description="Try your luck with random item draws and loot boxes",
                color=primary_color()
            )
            await self.update_view()
            await interaction.message.edit(embed=embed, view=self)
        except:
            pass

class PokemonSpawnSectionSelect(discord.ui.Select):
    def __init__(self, shop_data, quest_data, user_id, guild_id):
        options = []
        pokemon_spawns = shop_data.get("PoketwoSpawns", {}).get("sections", {})
        
        for section_name, section_items in pokemon_spawns.items():
            emoji = None
            if section_items:
                emoji = section_items[0].get("emoji")
            if not emoji:
                emoji = "🐾"
            
            description = f"{section_name} ({len(section_items)} available)"
            options.append(discord.SelectOption(label=section_name, description=description, value=section_name, emoji=emoji))

        super().__init__(placeholder="Select a section", options=options)
        self.shop_data = shop_data
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                await interaction.response.send_message("This is not your shop interface.", ephemeral=True)
                return

            section = self.values[0]
            pokemon_spawns = self.shop_data.get("PoketwoSpawns", {}).get("sections", {})
            items = pokemon_spawns.get(section, [])
            if not items:
                await interaction.response.send_message(f"No items available in {section}.", ephemeral=True)
                return

            item_view = PokemonSpawnItemView(items, section, self.quest_data, self.user_id, self.guild_id)
            embed = await item_view.create_shop_embed()
            await item_view.update_view()
            await interaction.response.edit_message(embed=embed, view=item_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

class PokemonSpawnItemView(discord.ui.View):
    def __init__(self, items, section, quest_data, user_id, guild_id):
        super().__init__(timeout=300)
        self.items = items
        self.section = section
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.page = 0
        self.items_per_page = 10
        self.max_pages = (len(items) - 1) // self.items_per_page + 1

    async def create_shop_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        embed = discord.Embed(
            title=f"🐾 {self.section}",
            description=f"Browse and purchase {self.section.lower()} items for your profile (Page {self.page + 1}/{self.max_pages})",
            color=primary_color()
        )

        item_list = []
        for i, item in enumerate(current_items):
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, item["name"]) or 0
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            if user_quantity > 0:
                indicator = "✅"
                name_display = f"~~{item['name']}~~"
            elif user_balance >= item["points"]:
                indicator = "💰"
                name_display = item["name"]
            else:
                indicator = "❌"
                name_display = item['name']

            price_display = f"{item['points']:,} pts"
            theme = item.get("theme", "N/A")
            item_entry = f"{indicator} **{name_display}** - {price_display}"
            if user_quantity > 0:
                item_entry += f" (Owned: {user_quantity})"
            item_entry += f"\n╰➺   *{theme}* - {item['description'][:50]}...\n"
            item_list.append(f"`{start + i + 1}.` {item_entry}")

        if item_list:
            embed.add_field(name="Items Available", value="\n".join(item_list), inline=False)
        embed.add_field(name="", value="> ✅ Owned | 💰 Can Purchase | ❌ Insufficient Points", inline=False)
        embed.set_footer(text=f"Your Balance: {await self.quest_data.get_balance(self.user_id, self.guild_id):,} Stella Points")
        return embed

    async def update_view(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        current_row = 0
        for i, item in enumerate(current_items):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, item["name"]) or 0

            if user_quantity > 0:
                style, disabled = discord.ButtonStyle.green, True
            elif user_balance >= item["points"]:
                style, disabled = discord.ButtonStyle.primary, False
            else:
                style, disabled = discord.ButtonStyle.grey, True

            btn = Button(style=style, label=str(i + 1), custom_id=f"item_{start + i}", disabled=disabled)
            btn.callback = self.item_callback
            self.add_item(btn)

            if (i + 1) % 5 == 0:
                current_row += 1

        if self.max_pages > 1:
            pagination_row = current_row + 1 if current_row < 4 else 4
            if self.page > 0:
                prev_btn = Button(emoji="⬅️", style=discord.ButtonStyle.secondary, custom_id="prev_page", row=pagination_row)
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)
            if self.page < self.max_pages - 1:
                next_btn = Button(emoji="➡️", style=discord.ButtonStyle.secondary, custom_id="next_page", row=pagination_row)
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

    async def item_callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                await interaction.response.send_message("This is not your shop interface.", ephemeral=True)
                return

            index = int(interaction.data["custom_id"].split("_")[1])
            item = self.items[index]
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, item["name"]) or 0

            if user_quantity > 0:
                return await interaction.response.send_message(embed=discord.Embed(
                    title="ℹ️ Already Owned",
                    description=f"You already own **{item['name']}** (Quantity: {user_quantity})",
                    color=discord.Color.blue()
                ), ephemeral=True)

            if user_balance >= item["points"]:
                await self.quest_data.add_balance(self.user_id, self.guild_id, -item["points"])
                await self.quest_data.add_item_to_inventory(self.guild_id, self.user_id, item["name"], 1)
                new_balance = user_balance - item["points"]
                embed = discord.Embed(
                    title="✅ Purchase Successful!",
                    description=f"You've purchased **{item['name']}** for {item['points']:,} points!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Description", value=item["description"], inline=False)
                embed.add_field(name="Theme", value=item.get("theme", "N/A"), inline=True)
                if item.get("season"):
                    embed.add_field(name="Season", value=item["season"], inline=True)
                embed.set_footer(text=f"Remaining balance: {new_balance:,} points")
                await interaction.response.edit_message(embed=embed, view=self)
                await self.refresh_shop_view(interaction)
            else:
                await interaction.response.send_message(embed=discord.Embed(
                    title="❌ Insufficient Points",
                    description=f"You need {item['points']:,} points but only have {user_balance:,}.",
                    color=discord.Color.red()
                ), ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    async def refresh_shop_view(self, interaction):
        try:
            embed = await self.create_shop_embed()
            await self.update_view()
            if interaction.message:
                await interaction.message.edit(embed=embed, view=self)
        except:
            pass

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.page -= 1
        embed = await self.create_shop_embed()
        await self.update_view()
        await interaction.response.edit_message(embed=embed, view=self)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.page += 1
        embed = await self.create_shop_embed()
        await self.update_view()
        await interaction.response.edit_message(embed=embed, view=self)


class GachaGameView(discord.ui.View):
    def __init__(self, quest_data, user_id, guild_id, gacha_item):
        super().__init__(timeout=300)
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.gacha_item = gacha_item

    async def pull_gacha(self):
        """Simulate a gacha pull"""
        if self.gacha_item["name"] == "Mystery Spy Box":
            possible_items = self.quest_data.shop_data.get("SpyTools", []) + \
                           self.quest_data.shop_data.get("Collectables", []) + \
                           self.quest_data.shop_data.get("Materials", [])
        elif self.gacha_item["name"] == "Lucky Forger Capsule":
            possible_items = []
            forger_data = self.quest_data.shop_data.get("ProfileCustomization", {}).get("ForgerFamily", {})
            for item_type in ["Backgrounds", "Fonts", "Items"]:
                possible_items.extend(forger_data.get(item_type, []))
        elif self.gacha_item["name"] == "WISE Gacha Capsule":
            possible_items = []
            wise_data = self.quest_data.shop_data.get("ProfileCustomization", {}).get("WISE", {})
            for item_type in ["Backgrounds", "Fonts", "Items"]:
                possible_items.extend(wise_data.get(item_type, []))
        else:
            possible_items = []

        if not possible_items:
            return None

        weights = [1 / (item.get("points", 1000) / 1000) for item in possible_items]
        item = random.choices(possible_items, weights=weights, k=1)[0]
        
        # Chance to get a unique collectable
        if random.random() < 0.3:  # 30% chance for unique collectable
            item = CollectablesGenerator.generate_collectable()
        
        return item

    async def update_view(self):
        self.clear_items()
        pull_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Pull Gacha",
            custom_id="pull_gacha",
            row=0
        )
        pull_button.callback = self.pull_callback
        self.add_item(pull_button)

    async def pull_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your gacha interface.", ephemeral=True
                )
                return

            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            if user_balance < self.gacha_item["points"]:
                embed = discord.Embed(
                    title="❌ Insufficient Points",
                    description=f"You need {self.gacha_item['points']:,} points to pull from **{self.gacha_item['name']}**.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await self.quest_data.add_balance(self.user_id, self.guild_id, -self.gacha_item["points"])
            item = await self.pull_gacha()
            
            if not item:
                embed = discord.Embed(
                    title="❌ Gacha Error",
                    description="No items available in this gacha.",
                    color=discord.Color.red()
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await self.quest_data.add_item_to_inventory(
                self.guild_id, self.user_id, item["name"], 1
            )
            
            embed = discord.Embed(
                title="🎉 Gacha Pull Result!",
                description=f"You received **{item['name']}** from **{self.gacha_item['name']}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="Description", value=item["description"], inline=False)
            if "emoji" in item:
                embed.add_field(name="Item", value=item["emoji"], inline=True)
            if "rarity" in item:
                embed.add_field(name="Rarity", value=item["rarity"], inline=True)
            
            new_balance = user_balance - self.gacha_item["points"]
            embed.set_footer(text=f"Remaining balance: {new_balance:,} points")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )