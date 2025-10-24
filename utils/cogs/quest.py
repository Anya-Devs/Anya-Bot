
import os
import math
import datetime
import random
import string
import aiofiles
import typing

from datetime import datetime, timezone

import traceback
import asyncio
import random
from io import BytesIO
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor
from motor.motor_asyncio import AsyncIOMotorClient


 

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


logger = logging.getLogger(__name__)


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
        self.shop_file = Path("data/commands/quest/shop.json")

        # Load shop.json data and emoji map
        self.shop_data: dict = {}
        self._tool_emoji_map: dict = {}
        self._load_shop_json()

    # -------------------------------
    # Shop JSON handling
    # -------------------------------
    def _normalize_name(self, s: str) -> str:
        """Lowercase and strip non-alphanumerics for robust matching."""
        return re.sub(r"[^a-z0-9]", "", (s or "").lower())

    def _load_shop_json(self) -> dict:
        """Load shop.json and build internal tool->emoji mapping."""
        try:
            if not self.shop_file.exists():
                logger.warning("shop.json missing at %s", self.shop_file)
                self.shop_data = {}
                self._tool_emoji_map = {}
                return self.shop_data

            with self.shop_file.open("r", encoding="utf-8") as fh:
                self.shop_data = json.load(fh)
        except Exception:
            logger.exception("Failed to load shop.json")
            self.shop_data = {}

        self._tool_emoji_map = self._build_tool_emoji_map(self.shop_data)
        return self.shop_data

    def _build_tool_emoji_map(self, shop_data: dict) -> dict:
        """Walk shop_data and return a dict mapping normalized tool names -> emoji strings."""
        m = {}
        if not isinstance(shop_data, dict):
            return m

        for category_val in shop_data.values():
            if not isinstance(category_val, dict):
                continue
            items = category_val.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                name = item.get("name")
                emoji = item.get("emoji")
                if not name or not emoji:
                    continue
                m[name.lower()] = emoji
                m[self._normalize_name(name)] = emoji
        return m

    def reload_shop(self) -> dict:
        """Reload shop.json at runtime after edits."""
        return self._load_shop_json()

    def get_tool_emoji(self, tool_name: str) -> str | None:
        """
        Return the emoji string for a tool name from shop.json.
        Returns None if not found (caller should fallback).
        """
        if not tool_name:
            return None
        return (
            self._tool_emoji_map.get(tool_name.lower())
            or self._tool_emoji_map.get(self._normalize_name(tool_name))
        )

    # -------------------------------
    # Validation
    # -------------------------------
    @staticmethod
    async def validate_input(**kwargs):
        for key, value in kwargs.items():
            if value is None or value == "":
                raise ValueError(f"{key} cannot be None or empty")

    # -------------------------------
    # Role methods
    # -------------------------------
    async def store_roles_for_guild(self, guild_id, role_ids):
        return await self.db_manager.roles.store_roles_for_guild(guild_id, role_ids)

    async def get_roles_for_guild(self, guild_id):
        return await self.db_manager.roles.get_roles_for_guild(guild_id)

    # -------------------------------
    # Inventory methods
    # -------------------------------
    async def get_user_inventory_count(
        self, guild_id: str, user_id: str, category: str, item_name: str
    ) -> int:
        return await self.db_manager.inventory.get_user_inventory_count(
            guild_id, user_id, category, item_name
        )

    async def add_item_to_inventory(
        self, guild_id: str, user_id: str, category: str, item_name: str, quantity: int
    ) -> None:
        return await self.db_manager.inventory.add_item_to_inventory(
            guild_id, user_id, category, item_name, quantity
        )

    async def remove_item_from_inventory(
        self, guild_id: str, user_id: str, category: str, item_name: str, quantity: int
    ) -> bool:
        return await self.db_manager.inventory.remove_item_from_inventory(
            guild_id, user_id, category, item_name, quantity
        )

    async def reset_inventory_item(
        self, guild_id: str, user_id: str, category: str, item_name: str
    ) -> None:
        return await self.db_manager.inventory.reset_inventory_item(
            guild_id, user_id, category, item_name
        )

    # -------------------------------
    # Tool methods
    # -------------------------------
    async def get_existing_tool_id(self, guild_id: str, user_id: str, tool_name: str) -> str:
        return await self.db_manager.tools.get_existing_tool_id(guild_id, user_id, tool_name)

    async def get_material_quantity(self, guild_id: str, user_id: str, material_name: str) -> int:
        return await self.db_manager.tools.get_material_quantity(guild_id, user_id, material_name)

    async def add_material_to_inventory(
        self, guild_id: str, user_id: str, material_name: str, quantity: int
    ) -> None:
        return await self.db_manager.tools.add_material_to_inventory(
            guild_id, user_id, material_name, quantity
        )

    async def remove_tool_from_inventory(self, guild_id: str, user_id: str, tool_name: str) -> None:
        return await self.db_manager.tools.remove_tool_from_inventory(guild_id, user_id, tool_name)

    async def create_un_tool_id(self, guild_id, user_id, tool):
        return await self.db_manager.tools.create_un_tool_id(guild_id, user_id, tool)

    async def get_un_tool_id(self, guild_id, user_id, tool):
        return await self.db_manager.tools.get_un_tool_id(guild_id, user_id, tool)

    # -------------------------------
    # Server methods
    # -------------------------------
    async def find_user_in_server(self, user_id: str, guild_id: str) -> bool:
        return await self.db_manager.server.find_user_in_server(user_id, guild_id)

    async def find_users_in_server(self, guild_id: str):
        return await self.db_manager.server.find_users_in_server(guild_id)

    async def add_user_to_server(self, user_id: str, guild_id: str):
        return await self.db_manager.server.add_user_to_server(user_id, guild_id)

    # -------------------------------
    # Channel methods
    # -------------------------------
    async def get_random_channel_for_guild(self, guild_id: str, fallback_channel=None):
        return await self.db_manager.channels.get_random_channel_for_guild(guild_id, fallback_channel)

    async def store_channels_for_guild(self, guild_id: str, channel_ids: list):
        return await self.db_manager.channels.store_channels_for_guild(guild_id, channel_ids)

    async def get_most_active_channel(
        self, guild_id: str, threshold=5, message_limit=100, fallback_channel_id=None
    ):
        return await self.db_manager.channels.get_most_active_channel(
            guild_id, threshold, message_limit, fallback_channel_id
        )

    # -------------------------------
    # Balance methods
    # -------------------------------
    async def get_balance(self, user_id: str, guild_id: str):
        return await self.db_manager.balance.get_balance(user_id, guild_id)

    async def add_balance(self, user_id: str, guild_id: str, amount: int):
        return await self.db_manager.balance.add_balance(user_id, guild_id, amount)

    async def initialize_balance(self, user_id: str, guild_id: str):
        return await self.db_manager.balance.initialize_balance(user_id, guild_id)

    # -------------------------------
    # Quest methods
    # -------------------------------
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

    async def create_quest(
        self, guild_id: str, action: str, method: str, content: str, times: int, reward: int, interaction=None
    ):
        return await self.db_manager.quests.create_quest(
            guild_id, action, method, content, times, reward, interaction
        )

    async def create_member_quest(
        self, guild_id: str, user_id: str, action: str, method: str, content: str, times: int, interaction=None
    ):
        return await self.db_manager.quests.create_member_quest(
            guild_id, user_id, action, method, content, times, interaction
        )

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





















EMBED_CONFIG = {
    "primary_color": 0x1E90FF,  # Default color
    "error_color": 0xFF0000,
    "profile_title": "{display_name}'s Profile",
    "story_title": "{display_name}'s Life Story - Page {page}",
    "end_of_stories_title": "End of Stories",
    "end_of_stories_desc": "No more stories to display.",
    "error_title": "Profile Error",
    "error_desc": "An error occurred while generating the profile embed.",
    "customize_title": "Customize Profile",
    "customize_desc": "Select an option to edit:",
    "story_manage_title": "Manage Life Stories",
    "story_manage_desc": "You have {num_stories} stories.\nSelect action:",
    "story_cost": 1000,
    "fields": {
        "bio_page": [
            {"name": "Name", "key": "display_name", "inline": True},
            {"name": "Age", "key": "age", "inline": True},
            {"name": "Member Since", "key": "duration", "inline": True},
            {"name": "Sexuality", "key": "sexuality", "inline": True},
            {"name": "About Me", "key": "bio", "inline": False},
        ],
        "story_page": [
            {"name": "Story", "key": "story", "inline": False},
        ],
    },
    "footer": {
        "bio": "Bio Page | Stella Points: {stella_points:,}",
        "story": "Story Page {page} | Stella Points: {stella_points:,}",
    },
}



logger = logging.getLogger(__name__)
_URL_RE = re.compile(
    r"^(https?://)"                         # scheme
    r"([A-Za-z0-9\-_~]+\.)+[A-Za-z]{2,}"    # domain
    r"([:/?#][^\s]*)?$", re.IGNORECASE
)



class ProfileView(View):
    class ProfileEditModal(Modal):
        def __init__(
            self,
            profile_view,
            title: str,
            input_label: str,
            placeholder: str,
            default: str = "",
            style=discord.TextStyle.short,
            max_length: int = 1024,
            parse_func=str,
            empty_allowed: bool = False,
            parse_error_msg: str = "Invalid input. Please enter a valid value."
        ):
            super().__init__(title=title)
            self.profile_view = profile_view
            self.input_label = input_label
            self.parse_func = parse_func
            self.empty_allowed = empty_allowed
            self.parse_error_msg = parse_error_msg
            self.input = TextInput(
                label=input_label,
                placeholder=placeholder,
                default=default,
                style=style,
                max_length=max_length,
            )
            self.add_item(self.input)

        async def on_submit(self, interaction: discord.Interaction):
            value_str = self.input.value.strip()
            try:
                parsed = self.parse_func(value_str)
            except ValueError:
                logger.warning(f"Invalid input in {self.__class__.__name__}: {value_str}")
                await interaction.response.send_message(self.parse_error_msg, ephemeral=True)
                return

            if (not parsed) and not self.empty_allowed:
                logger.warning(f"Empty input not allowed in {self.__class__.__name__}: {value_str}")
                await interaction.response.send_message(f"{self.input_label} cannot be empty.", ephemeral=True)
                return

            try:
                await self.update_profile(parsed)
                await self.profile_view.load_profile()
                await self.profile_view._update_profile_message(interaction)
                await interaction.response.send_message(f"{self.input_label} updated successfully!", ephemeral=True)
                logger.info(f"{self.input_label} updated successfully for user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Error in {self.__class__.__name__} on_submit for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

        async def update_profile(self, value):
            raise NotImplementedError("Subclasses must implement update_profile")

    class AgeEditModal(ProfileEditModal):
        def __init__(self, profile_view):
            default = str(profile_view.age) if profile_view.age != "Not set" else ""
            super().__init__(
                profile_view,
                "Edit Age",
                "Age",
                "Enter your age (number)",
                default,
                discord.TextStyle.short,
                3,
                int,
                False,
                "Please enter a valid number for age."
            )

        async def update_profile(self, value):
            self.profile_view.age = value
            await self.profile_view.save_profile(age=value)

    class SexualityEditModal(ProfileEditModal):
        def __init__(self, profile_view):
            default = profile_view.sexuality if profile_view.sexuality != "Not set" else ""
            super().__init__(
                profile_view,
                "Edit Sexuality",
                "Sexuality",
                "Enter your sexuality",
                default,
                discord.TextStyle.short,
                50,
                str,
                True
            )

        async def update_profile(self, value):
            value = value or "Not set"
            self.profile_view.sexuality = value
            await self.profile_view.save_profile(sex=value)

    class BioEditModal(ProfileEditModal):
        def __init__(self, profile_view):
            default = profile_view.bio if profile_view.bio != "No bio set." else ""
            super().__init__(
                profile_view,
                "Edit Bio",
                "Bio",
                "Tell us a little about yourself...",
                default,
                discord.TextStyle.paragraph,
                1024,
                str,
                True
            )

        async def update_profile(self, value):
            value = value or "No bio set."
            self.profile_view.bio = value
            await self.profile_view.save_profile(bio=value)

    class SetBannerModal(ProfileEditModal):
        def __init__(self, profile_view):
            default = profile_view.banner_url if profile_view.banner_url else ""
            super().__init__(
                profile_view,
                "Set Banner Image",
                "Banner URL",
                "Enter image URL",
                default,
                discord.TextStyle.short,
                500,
                str,
                True
            )

        async def update_profile(self, value):
            value = value or None
            self.profile_view.banner_url = value
            await self.profile_view.save_profile(banner_url=value)

    class AddStoryModal(Modal):
        def __init__(self, profile_view):
            super().__init__(title="Add Life Story")
            self.profile_view = profile_view
            self.title_input = TextInput(
                label="Title",
                placeholder="Enter story title",
                style=discord.TextStyle.short,
                max_length=100,
                default="Untitled"
            )
            self.add_item(self.title_input)
            self.content_input = TextInput(
                label="Story (max 4000 characters)",
                placeholder="Share a story from your life (up to 4000 characters)...",
                style=discord.TextStyle.paragraph,
                max_length=4000,
            )
            self.add_item(self.content_input)

        async def on_submit(self, interaction: discord.Interaction):
            title = self.title_input.value.strip() or "Untitled"
            content = self.content_input.value.strip()[:4000]
            if not content:
                logger.warning(f"Empty story content submitted by user {interaction.user.id}")
                await interaction.response.send_message("Story content cannot be empty.", ephemeral=True)
                return
            try:
                logger.debug(f"Adding story for user {interaction.user.id}: title={title}, content_length={len(content)}")
                self.profile_view.stories.append({"title": title, "content": content, "image_urls": []})
                self.profile_view.total_pages = max(1, 1 + len(self.profile_view.stories))
                await self.profile_view.save_profile(stories=self.profile_view.stories)
                await self.profile_view.load_profile()
                await self.profile_view._update_profile_message(interaction)
                await interaction.response.send_message("Life story added successfully!", ephemeral=True)
                logger.info(f"Story added successfully for user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Error in AddStoryModal on_submit for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    class EditStoryModal(Modal):
        def __init__(self, profile_view, index: int):
            super().__init__(title=f"Edit Life Story {index + 1}")
            self.profile_view = profile_view
            self.index = index
            current = profile_view.stories[index]
            self.title_input = TextInput(
                label="Title",
                placeholder="Enter story title",
                style=discord.TextStyle.short,
                max_length=100,
                default=current['title']
            )
            self.add_item(self.title_input)
            self.content_input = TextInput(
                label="Story (max 4000 characters)",
                placeholder="Edit your story (up to 4000 characters)...",
                style=discord.TextStyle.paragraph,
                max_length=4000,
                default=current['content'][:4000]
            )
            self.add_item(self.content_input)

        async def on_submit(self, interaction: discord.Interaction):
            title = self.title_input.value.strip() or "Untitled"
            content = self.content_input.value.strip()[:4000]
            if not content:
                logger.warning(f"Empty story content submitted by user {interaction.user.id}")
                await interaction.response.send_message("Story content cannot be empty.", ephemeral=True)
                return
            try:
                logger.debug(f"Editing story {self.index + 1} for user {interaction.user.id}: title={title}, content_length={len(content)}")
                self.profile_view.stories[self.index]['title'] = title
                self.profile_view.stories[self.index]['content'] = content
                await self.profile_view.save_profile(stories=self.profile_view.stories)
                await self.profile_view.load_profile()
                await self.profile_view._update_profile_message(interaction)
                await interaction.response.send_message("Life story updated successfully!", ephemeral=True)
                logger.info(f"Story {self.index + 1} updated successfully for user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Error in EditStoryModal on_submit for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)

    class AddStoryImageModal(ProfileEditModal):
        def __init__(self, profile_view, index: int):
            self.index = index
            super().__init__(
                profile_view,
                title=f"Add Image to Story {index + 1}",
                input_label="Image URL",
                placeholder="Enter image URL",
                default="",
                style=discord.TextStyle.short,
                max_length=500,
                parse_func=str,
                empty_allowed=False,
                parse_error_msg="Please enter a valid URL (must start with http/https)."
            )

        async def on_submit(self, interaction: discord.Interaction):
            value = self.input.value.strip()
            if not value:
                logger.warning(f"Empty image URL submitted by user {interaction.user.id}")
                await interaction.response.send_message("Image URL cannot be empty.", ephemeral=True)
                return
            if not _URL_RE.match(value):
                logger.warning(f"Invalid URL submitted by user {interaction.user.id}: {value}")
                await interaction.response.send_message(self.parse_error_msg, ephemeral=True)
                return
            try:
                logger.debug(f"Adding image to story {self.index + 1}: url={value} (user {interaction.user.id})")
                story = self.profile_view.stories[self.index]
                if 'image_urls' not in story or not isinstance(story['image_urls'], list):
                    story['image_urls'] = []
                story['image_urls'].append(value)
                await self.profile_view.save_profile(stories=self.profile_view.stories)
                await self.profile_view.load_profile()
                await self.profile_view._update_profile_message(interaction)
                await interaction.response.send_message("Image added to story.", ephemeral=True)
                logger.info(f"Added image to story {self.index + 1} for user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Error in AddStoryImageModal on_submit for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message("An error occurred while adding image.", ephemeral=True)

    class EditStoryNumberModal(Modal):
        def __init__(self, profile_view, action: str):
            super().__init__(title=f"{action} Story Number")
            self.profile_view = profile_view
            self.action = action
            num_stories = len(self.profile_view.stories)
            self.story_input = TextInput(
                label="Story Number",
                placeholder=f"Enter story number (1-{num_stories})",
                style=discord.TextStyle.short,
                max_length=3,
            )
            self.add_item(self.story_input)

        async def on_submit(self, interaction: discord.Interaction):
            try:
                story_num = int(self.story_input.value)
                num_stories = len(self.profile_view.stories)
                logger.debug(f"Story number submitted by user {interaction.user.id}: {story_num}, num_stories={num_stories}, action={self.action}")
                if 1 <= story_num <= num_stories:
                    index = story_num - 1
                    view = View(timeout=300)
                    button = self.ConfirmModalButton(self.profile_view, self.action, index)
                    view.add_item(button)
                    embed = discord.Embed(
                        title=f"Confirm {self.action} Story {story_num}",
                        description=f"Click the button below to {self.action.lower()} story {story_num}.",
                        color=int("131416", 16),
                    )
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
                    logger.info(f"Sent confirmation message for {self.action} story {story_num} for user {interaction.user.id}")
                else:
                    logger.warning(f"Invalid story number {story_num} submitted by user {interaction.user.id}, must be between 1 and {num_stories}")
                    await interaction.response.send_message(f"Invalid story number. Must be between 1 and {num_stories}.", ephemeral=True)
            except ValueError:
                logger.warning(f"Invalid number input by user {interaction.user.id}: {self.story_input.value}")
                await interaction.response.send_message("Please enter a valid number.", ephemeral=True)
            except Exception as e:
                logger.error(f"Error in EditStoryNumberModal on_submit for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message("An error occurred while processing story number.", ephemeral=True)

        class ConfirmModalButton(Button):
            def __init__(self, profile_view, action: str, index: int):
                super().__init__(label=f"{action} Story", style=discord.ButtonStyle.primary)
                self.profile_view = profile_view
                self.action = action
                self.index = index

            async def callback(self, interaction: discord.Interaction):
                try:
                    logger.debug(f"ConfirmModalButton clicked for {self.action} story {self.index + 1} by user {interaction.user.id}")
                    if self.action == "Edit":
                        modal = self.profile_view.EditStoryModal(self.profile_view, self.index)
                    elif self.action == "Add Image to":
                        modal = self.profile_view.AddStoryImageModal(self.profile_view, self.index)
                    await interaction.response.send_modal(modal)
                    logger.info(f"Opened {self.action} modal for story {self.index + 1} for user {interaction.user.id}")
                except Exception as e:
                    logger.error(f"Error in ConfirmModalButton callback for user {interaction.user.id}: {e}")
                    traceback.print_exc()
                    await interaction.response.send_message("An error occurred while opening the modal.", ephemeral=True)

    class NavigationButton(Button):
        def __init__(self, profile_view, direction: str, disabled: bool = False):
            emoji = '◀️' if direction == 'prev' else '▶️'
            super().__init__(emoji=emoji, style=discord.ButtonStyle.secondary, disabled=disabled)
            self.profile_view = profile_view
            self.direction = direction
            logger.debug(f"Initialized NavigationButton: direction={direction}, disabled={disabled}")

        async def callback(self, interaction: discord.Interaction):
            logger.info(f"NavigationButton ({self.direction}) clicked by user {interaction.user.id}")
            if interaction.user.id != self.profile_view.member.id and interaction.user.id != self.profile_view.ctx.author.id:
                logger.warning(f"Unauthorized navigation attempt by user {interaction.user.id}")
                await interaction.response.send_message("You can only navigate profiles you invoked or own.", ephemeral=True)
                return
            delta = -1 if self.direction == 'prev' else 1
            self.profile_view.current_page += delta
            try:
                await self.profile_view._update_page(interaction)
                logger.info(f"Navigated to page {self.profile_view.current_page} for user {interaction.user.id}")
            except ValueError as ve:
                self.profile_view.current_page -= delta
                logger.error(f"ValueError in NavigationButton callback: {ve}")
                await interaction.response.send_message(str(ve), ephemeral=True)
            except Exception as e:
                self.profile_view.current_page -= delta
                logger.error(f"Error in NavigationButton callback for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message("An error occurred while navigating.", ephemeral=True)

    class CustomizeButton(Button):
        def __init__(self, profile_view):
            super().__init__(label="Customize", style=discord.ButtonStyle.primary)
            self.profile_view = profile_view
            logger.debug(f"Initialized CustomizeButton for member {self.profile_view.member.id}")

        async def callback(self, interaction: discord.Interaction):
            logger.info(f"CustomizeButton clicked by user {interaction.user.id}")
            if interaction.user.id != self.profile_view.member.id:
                logger.warning(f"Unauthorized customize attempt by user {interaction.user.id}")
                await interaction.response.send_message("Only the profile owner can customize this profile.", ephemeral=True)
                return
            customize_embed = discord.Embed(
                title=EMBED_CONFIG["customize_title"],
                description=EMBED_CONFIG["customize_desc"],
                color=EMBED_CONFIG["primary_color"],
            )
            view = self.profile_view.CustomizeSelectView(self.profile_view)
            await interaction.response.send_message(embed=customize_embed, view=view, ephemeral=True)
            logger.debug(f"Sent customize embed and view to user {interaction.user.id}")

    class StoriesButton(Button):
        def __init__(self, profile_view):
            super().__init__(label="Stories", style=discord.ButtonStyle.success)
            self.profile_view = profile_view
            logger.debug(f"Initialized StoriesButton for member {self.profile_view.member.id}")

        async def callback(self, interaction: discord.Interaction):
            try:
                logger.info(f"StoriesButton clicked by user {interaction.user.id} for member {self.profile_view.member.id}")
                stories = self.profile_view.stories
                is_owner = interaction.user.id == self.profile_view.member.id
                logger.debug(f"Stories count: {len(stories)}, is_owner: {is_owner}, current_page: {self.profile_view.current_page}, total_pages: {self.profile_view.total_pages}")

                if not stories and not is_owner:
                    logger.info("No stories available and user is not the owner, sending message")
                    await interaction.response.send_message("No stories available.", ephemeral=True)
                    return

                embed = discord.Embed(
                    title=EMBED_CONFIG["story_manage_title"] if is_owner else "Life Stories",
                    color=int("131416", 16),
                )
                if is_owner:
                    embed.description = EMBED_CONFIG["story_manage_desc"].format(num_stories=len(stories))
                else:
                    embed.description = "Select a chapter to view."
                logger.debug(f"Embed created: title={embed.title}, description={embed.description}")

                view = View(timeout=300)
                if stories:
                    options = [
                        discord.SelectOption(label=f"Ch {i+1}: {s['title']}", value=str(i+1)) for i, s in enumerate(stories)
                    ]
                    logger.debug(f"Created {len(options)} story options: {[opt.label for opt in options]}")
                    jump_select = Select(placeholder="Jump to chapter...", options=options)
                    jump_select.callback = self.profile_view.jump_callback
                    view.add_item(jump_select)
                else:
                    logger.debug("No stories, skipping jump_select")

                if is_owner:
                    action_options = [
                        discord.SelectOption(label="Add New Story", emoji="➕", value="add"),
                    ]
                    if stories:
                        action_options.append(discord.SelectOption(label="Edit Existing Story", emoji="✏️", value="edit"))
                        action_options.append(discord.SelectOption(label="Add Image to Story", emoji="🖼️", value="add_image"))
                    logger.debug(f"Created action options for owner: {[opt.label for opt in action_options]}")
                    action_select = Select(placeholder="Manage actions...", options=action_options)
                    action_select.callback = self.profile_view.story_action_callback
                    view.add_item(action_select)
                else:
                    logger.debug("User is not owner, skipping action_select")

                logger.info(f"Sending stories embed with view for user {interaction.user.id}")
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Error in StoriesButton callback for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message("An error occurred while accessing stories.", ephemeral=True)

    class CustomizeSelectView(View):
        def __init__(self, profile_view):
            super().__init__(timeout=300)
            self.profile_view = profile_view
            options = [
                discord.SelectOption(label="Edit Age", emoji="📅", value="age"),
                discord.SelectOption(label="Edit Sexuality", emoji="❤️", value="sexuality"),
                discord.SelectOption(label="Edit Bio", emoji="📝", value="bio"),
                discord.SelectOption(label="Set Banner Image", emoji="🖼️", value="banner"),
            ]
            select = Select(placeholder="Choose what to edit", options=options)
            select.callback = self.select_callback
            self.add_item(select)
            logger.debug(f"Initialized CustomizeSelectView with {len(options)} options")

        async def select_callback(self, interaction: discord.Interaction):
            try:
                value = interaction.data['values'][0]
                logger.debug(f"Customize select callback: value={value} for user {interaction.user.id}")
                if value == "age":
                    modal = self.profile_view.AgeEditModal(self.profile_view)
                elif value == "sexuality":
                    modal = self.profile_view.SexualityEditModal(self.profile_view)
                elif value == "bio":
                    modal = self.profile_view.BioEditModal(self.profile_view)
                elif value == "banner":
                    modal = self.profile_view.SetBannerModal(self.profile_view)
                await interaction.response.send_modal(modal)
                logger.info(f"Opened {value} modal for user {interaction.user.id}")
            except Exception as e:
                logger.error(f"Error in CustomizeSelectView select_callback for user {interaction.user.id}: {e}")
                traceback.print_exc()
                await interaction.response.send_message("An error occurred while opening the modal.", ephemeral=True)

    def __init__(self, ctx, member, stella_points, quest_data):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.member = member
        self.stella_points = stella_points
        self.quest_data = quest_data
        self.age = "Not set"
        self.sexuality = "Not set"
        self.bio = "No bio set."
        self.banner_url = None
        self.stories = []
        self.current_page = 0
        self.total_pages = 1
        self.message = None
        try:
            self.mongo_client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
            self.db = self.mongo_client["Commands"]["Profiles"]
            self.old_db = self.mongo_client["Commands"]["Servers"]
            logger.debug(f"Database connection successful in ProfileView init for member {self.member.id}")
            self.update_buttons()
        except Exception as e:
            logger.error(f"Database connection error in ProfileView init: {e}")
            traceback.print_exc()
            raise

    async def save_profile(self, age=None, sex=None, bio=None, banner_url=None, stories=None):
        try:
            member_id = str(self.member.id)
            logger.debug(f"Attempting to save profile for member {member_id}")
            doc = await self.db.find_one({"member_id": member_id})
            existing_profile = doc.get("profile", {}) if doc else {}
            update_fields = {}
            if age is not None and age != existing_profile.get("age"):
                update_fields["age"] = age
            if sex is not None and sex != existing_profile.get("sexuality"):
                update_fields["sexuality"] = sex
            if bio is not None and bio != existing_profile.get("bio"):
                update_fields["bio"] = bio
            if banner_url is not None and banner_url != existing_profile.get("banner_url"):
                update_fields["banner_url"] = banner_url
            if stories is not None and stories != existing_profile.get("stories"):
                update_fields["stories"] = stories
            if not update_fields:
                logger.debug(f"No changes to profile for member {member_id}")
                return False
            result = await self.db.update_one(
                {"member_id": member_id},
                {"$set": {"profile." + key: value for key, value in update_fields.items()}},
                upsert=True,
            )
            if result.modified_count > 0 or result.upserted_id:
                logger.info(f"Profile updated for member {member_id}: {update_fields}")
            else:
                logger.warning(f"Update attempted but no changes applied for member {member_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving profile for member {member_id}: {e}")
            traceback.print_exc()
            raise

    async def load_profile(self):
        try:
            member_id = str(self.member.id)
            guild_id = str(self.ctx.guild.id)
            logger.debug(f"Loading profile for member {member_id} in guild {guild_id}")

            old_doc = await self.old_db.find_one(
                {"guild_id": guild_id, f"members.{member_id}.profile": {"$exists": True}}
            )
            if old_doc and "members" in old_doc and member_id in old_doc["members"]:
                old_profile = old_doc["members"][member_id].get("profile", {})
                logger.info(f"Found guild-specific profile for member {member_id} in guild {guild_id}, migrating to global Profiles")
                try:
                    await self.db.update_one(
                        {"member_id": member_id},
                        {"$set": {"profile": old_profile}},
                        upsert=True
                    )
                    logger.info(f"Migrated profile for member {member_id} from guild {guild_id} to global Profiles")
                    await self.old_db.update_one(
                        {"guild_id": guild_id},
                        {"$unset": {f"members.{member_id}.profile": ""}}
                    )
                    logger.debug(f"Removed guild-specific profile for member {member_id} from guild {guild_id}")
                except Exception as e:
                    logger.error(f"Error migrating profile for member {member_id} from guild {guild_id}: {e}")
                    traceback.print_exc()

            doc = await self.db.find_one({"member_id": member_id})
            if doc and "profile" in doc:
                profile = doc["profile"]
                self.age = profile.get("age", "Not set")
                self.sexuality = profile.get("sexuality", "Not set")
                self.bio = profile.get("bio", "No bio set.")
                self.banner_url = profile.get("banner_url", None)
                stories = profile.get("stories", [])
                self.stories = []
                for s in stories:
                    if isinstance(s, str):
                        self.stories.append({"title": "Untitled", "content": s[:4000], "image_urls": []})
                    elif isinstance(s, dict) and "title" in s and "content" in s:
                        self.stories.append({
                            "title": s.get("title", "Untitled"),
                            "content": s.get("content", "")[:4000],
                            "image_urls": s.get("image_urls", [])
                        })
                    else:
                        logger.warning(f"Invalid story format for member {member_id}: {s}")
                self.total_pages = max(1, 1 + len(self.stories))
                logger.debug(f"Loaded profile for {member_id}: age={self.age}, sexuality={self.sexuality}, bio={self.bio}, banner_url={self.banner_url}, stories_count={len(self.stories)}")
            else:
                logger.debug(f"No profile found for member {member_id}, using defaults")
        except Exception as e:
            logger.error(f"Error loading profile for member {self.member.id}: {e}")
            traceback.print_exc()
            raise

    def generate_embeds(self, page):
        try:
            logger.debug(f"Generating embeds for page {page} for member {self.member.id}")
            now = datetime.now(timezone.utc)
            delta = now - self.member.joined_at
            years = delta.days // 365
            months = (delta.days % 365) // 30
            duration = f"{years} years, {months} months" if years or months else "Recently joined"
            
            if page == 0:
                embed = discord.Embed(
                    title=EMBED_CONFIG["profile_title"].format(display_name=self.member.display_name),
                    color=EMBED_CONFIG["primary_color"],
                    timestamp=now,
                )
                fields = EMBED_CONFIG["fields"]["bio_page"]
                field_values = {
                    "display_name": self.member.display_name,
                    "age": str(self.age) if self.age != "Not set" else "Not set",
                    "duration": duration,
                    "sexuality": self.sexuality if self.sexuality != "Not set" else "Not set",
                    "bio": self.bio if self.bio != "No bio set." else "No bio set.",
                }
                for field in fields:
                    embed.add_field(
                        name=field["name"],
                        value=field_values[field["key"]] or "Not set",
                        inline=field["inline"],
                    )
                if self.banner_url:
                    embed.set_image(url=self.banner_url)
                embed.set_thumbnail(url=self.member.avatar.url if self.member.avatar else None)
                footer_text = EMBED_CONFIG["footer"]["bio"].format(stella_points=self.stella_points)
                embed.set_footer(text=footer_text)
                logger.debug(f"Generated bio page embed for member {self.member.id}")
                return [embed]
            else:
                story_index = page - 1
                if story_index < len(self.stories):
                    story = self.stories[story_index]
                    main_embed = discord.Embed(
                        title=EMBED_CONFIG["story_title"].format(display_name=self.member.display_name, chapter=page, title=story['title']),
                        description=story['content'][:4000] or "No content.",
                        color=EMBED_CONFIG["primary_color"],
                        timestamp=now,
                    )
                    footer_text = EMBED_CONFIG["footer"]["story"].format(chapter=page, stella_points=self.stella_points)
                    main_embed.set_footer(text=footer_text)
                    main_embed.set_thumbnail(url=self.member.avatar.url if self.member.avatar else None)
                    embeds = [main_embed]
                    image_urls = story.get('image_urls', [])
                    if image_urls:
                        main_embed.set_image(url=image_urls[0])
                        for url in image_urls[1:]:
                            img_embed = discord.Embed(color=EMBED_CONFIG["primary_color"]).set_image(url=url)
                            embeds.append(img_embed)
                    logger.debug(f"Generated {len(embeds)} embeds for story page {page}, story_index={story_index}")
                    return embeds
                else:
                    embed = discord.Embed(
                        title=EMBED_CONFIG["end_of_stories_title"],
                        description=EMBED_CONFIG["end_of_stories_desc"],
                        color=EMBED_CONFIG["primary_color"],
                        timestamp=now,
                    )
                    footer_text = EMBED_CONFIG["footer"]["story"].format(chapter=page, stella_points=self.stella_points)
                    embed.set_footer(text=footer_text)
                    logger.debug(f"Generated end-of-stories embed for page {page}")
                    return [embed]
        except Exception as e:
            logger.error(f"Error in generate_embeds for member {self.member.id}: {e}")
            traceback.print_exc()
            fallback_embed = discord.Embed(
                title=EMBED_CONFIG["error_title"],
                description=EMBED_CONFIG["error_desc"],
                color=EMBED_CONFIG["error_color"],
                timestamp=datetime.now(timezone.utc),
            )
            return [fallback_embed]

    def update_buttons(self):
        try:
            logger.info(f"Updating buttons: current_page={self.current_page}, total_pages={self.total_pages}, member={self.member.id}")
            self.clear_items()
            logger.debug("Cleared existing items from view")
            self.add_item(self.CustomizeButton(self))
            logger.debug("Added CustomizeButton")
            self.add_item(self.StoriesButton(self))
            logger.debug("Added StoriesButton")
            if self.current_page > 0:
                prev_disabled = self.current_page <= 1
                next_disabled = self.current_page >= self.total_pages - 1
                logger.debug(f"Navigation buttons: prev_disabled={prev_disabled}, next_disabled={next_disabled}")
                self.add_item(self.NavigationButton(self, 'prev', prev_disabled))
                self.add_item(self.NavigationButton(self, 'next', next_disabled))
            else:
                logger.debug("On bio page (current_page=0), skipping navigation buttons")
        except Exception as e:
            logger.error(f"Error in update_buttons for member {self.member.id}: {e}")
            traceback.print_exc()

    async def _update_page(self, interaction):
        try:
            logger.debug(f"Updating page to {self.current_page} for user {interaction.user.id}")
            if self.current_page > 0 and interaction.user.id != self.member.id:
                cost = EMBED_CONFIG["story_cost"]
                viewer_id = str(interaction.user.id)
                viewer_balance = await self.quest_data.get_balance(viewer_id)
                logger.debug(f"Checking balance for user {viewer_id}: balance={viewer_balance}, cost={cost}")
                if viewer_balance < cost:
                    logger.warning(f"Insufficient Stella Points for user {viewer_id}: needed {cost}, had {viewer_balance}")
                    raise ValueError(f"Insufficient Stella Points. Need {cost} to view this story page.")
                await self.quest_data.add_balance(viewer_id, -cost)
                logger.debug(f"Deducted {cost} Stella Points from user {viewer_id}")
            embeds = self.generate_embeds(self.current_page)
            self.update_buttons()
            await interaction.response.edit_message(embeds=embeds, view=self)
            logger.info(f"Page {self.current_page} updated successfully for user {interaction.user.id}")
        except Exception as e:
            logger.error(f"Error in _update_page for user {interaction.user.id}: {e}")
            traceback.print_exc()
            raise

    async def _update_profile_message(self, interaction=None):
        try:
            logger.debug(f"Updating profile message for member {self.member.id}, current_page={self.current_page}")
            embeds = self.generate_embeds(self.current_page)
            self.update_buttons()
            if self.message is None or not await self.message.channel.fetch_message(self.message.id):
                logger.warning(f"Message invalid or deleted for member {self.member.id}, sending new message")
                self.message = await self.ctx.send(embeds=embeds, view=self)
            else:
                await self.message.edit(embeds=embeds, view=self)
            logger.debug("Profile message updated successfully")
        except Exception as e:
            logger.error(f"Error updating profile message for member {self.member.id}: {e}")
            traceback.print_exc()
            if interaction:
                await interaction.response.send_message("Failed to update profile message.", ephemeral=True)

    async def jump_callback(self, interaction: discord.Interaction):
        try:
            value = interaction.data['values'][0]
            page = int(value)
            logger.info(f"Jump callback triggered by user {interaction.user.id}, jumping to page {page}")
            self.current_page = page
            if page > 0 and interaction.user.id != self.member.id:
                cost = EMBED_CONFIG["story_cost"]
                viewer_id = str(interaction.user.id)
                viewer_balance = await self.quest_data.get_balance(viewer_id)
                logger.debug(f"Checking balance for user {viewer_id}: balance={viewer_balance}, cost={cost}")
                if viewer_balance < cost:
                    logger.warning(f"Insufficient Stella Points for user {viewer_id}: needed {cost}, had {viewer_balance}")
                    raise ValueError(f"Insufficient Stella Points. Need {cost} to view this story page.")
                await self.quest_data.add_balance(viewer_id, -cost)
                logger.debug(f"Deducted {cost} Stella Points from user {viewer_id}")
            embeds = self.generate_embeds(page)
            logger.debug(f"Generated {len(embeds)} embeds for page {page}")
            self.update_buttons()
            logger.debug("Updated buttons for jump")
            await self.message.edit(embeds=embeds, view=self)
            logger.info(f"Message edited with new embeds and view for page {page}")
            await interaction.response.send_message(f"Jumped to chapter {page}", ephemeral=True)
        except ValueError as ve:
            logger.error(f"ValueError in jump_callback for user {interaction.user.id}: {ve}")
            await interaction.response.send_message(str(ve), ephemeral=True)
        except Exception as e:
            logger.error(f"Error in jump_callback for user {interaction.user.id}: {e}")
            traceback.print_exc()
            await interaction.response.send_message("An error occurred while jumping to chapter.", ephemeral=True)

    async def story_action_callback(self, interaction: discord.Interaction):
        try:
            value = interaction.data['values'][0]
            logger.info(f"Story action callback triggered by user {interaction.user.id}, action={value}")
            if value == "add":
                logger.debug("Opening AddStoryModal")
                modal = self.AddStoryModal(self)
                await interaction.response.send_modal(modal)
            elif value == "edit":
                if len(self.stories) == 0:
                    logger.warning("No stories to edit")
                    await interaction.response.send_message("No stories to edit.", ephemeral=True)
                    return
                logger.debug("Opening EditStoryNumberModal for edit")
                modal = self.EditStoryNumberModal(self, "Edit")
                await interaction.response.send_modal(modal)
            elif value == "add_image":
                if len(self.stories) == 0:
                    logger.warning("No stories to add image to")
                    await interaction.response.send_message("No stories to add image to.", ephemeral=True)
                    return
                logger.debug("Opening EditStoryNumberModal for add_image")
                modal = self.EditStoryNumberModal(self, "Add Image to")
                await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"Error in story_action_callback for user {interaction.user.id}: {e}")
            traceback.print_exc()
            await interaction.response.send_message("An error occurred while processing your request.", ephemeral=True)

    async def start(self, ctx):
        try:
            logger.debug(f"Starting ProfileView for member {self.member.id} in guild {ctx.guild.id}")
            await self.load_profile()
            embeds = self.generate_embeds(self.current_page)
            kwargs = {"embeds": embeds, "view": self}
            self.message = await ctx.reply(**kwargs)
            logger.info(f"ProfileView started for member {self.member.id}")
        except ValueError as ve:
            logger.error(f"ValueError in ProfileView start for member {self.member.id}: {ve}")
            error_embed = discord.Embed(
                title=EMBED_CONFIG["error_title"],
                description=str(ve),
                color=EMBED_CONFIG["error_color"],
            )
            await ctx.reply(embed=error_embed)
        except Exception as e:
            logger.error(f"Error in ProfileView start for member {self.member.id}: {e}")
            traceback.print_exc()
            error_embed = discord.Embed(
                title=EMBED_CONFIG["error_title"],
                description=f"An error occurred while starting profile: {e}",
                color=EMBED_CONFIG["error_color"],
            )
            await ctx.reply(embed=error_embed)















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
                emoji="🎰",
                label="Gacha Games",
                description="Random item draws and loot boxes",
                value="gacha_games"
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
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your inventory interface.", ephemeral=True
                )
                return

            # Clear all items and re-add only the category select menu to reset the view
            self.parent_view.clear_items()
            self.parent_view.add_item(self)

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
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            # Fetch both tools and materials under spytools
            user_data = await server_collection.find_one(
                {"guild_id": self.guild_id, f"members.{self.user_id}": {"$exists": True}},
                {f"members.{self.user_id}.inventory.spytools": 1},
            )

            spytools_inventory = (
                user_data.get("members", {})
                .get(self.user_id, {})
                .get("inventory", {})
                .get("spytools", {})
            )

            tools = spytools_inventory.get("tools", {})
            materials = spytools_inventory.get("materials", {})

            if not tools and not materials:
                embed = discord.Embed(
                    title="🕵️ Spy Tools Inventory",
                    description="You don't have any spy tools or materials yet. Visit the shop to get some!",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
            else:
                embed = discord.Embed(
                    title="🕵️ Spy Tools Inventory",
                    description="Your collection of spy tools and materials",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )

                # Show tools
                if tools:
                    embed.add_field(
                        name="🔧 Tools",
                        value="",
                        inline=False
                    )
                    for tool_name in tools.keys():
                        try:
                            un_tool_id = await self.quest_data.get_existing_tool_id(
                                self.guild_id, self.user_id, tool_name
                            )
                            if not un_tool_id:
                                un_tool_id = await self.quest_data.create_un_tool_id(
                                    self.guild_id, self.user_id, tool_name
                                )

                            quantity = await self.quest_data.get_user_inventory_count(
                                self.guild_id, self.user_id, "spytools.tools", tool_name
                            )

                            emoji = self.quest_data.get_tool_emoji(tool_name) or "🔧"

                            embed.add_field(
                                name=f"{tool_name.title()}",
                                value=f"`{un_tool_id}` : \t{emoji}\t`x{quantity}`",
                                inline=False,
                            )
                        except Exception as e:
                            logger.error(f"Error processing tool {tool_name}: {e}")

                # Show materials
                if materials:
                    embed.add_field(
                        name="🛠️ Materials",
                        value="",
                        inline=False
                    )
                    for material_name, quantity in materials.items():
                        if quantity > 0:
                            material_emoji = self.quest_data.get_material_emoji(material_name) or "🛠️"  # Assume method exists
                            embed.add_field(
                                name=f"{material_name.title()}",
                                value=f"{material_emoji} `x{quantity}`",
                                inline=False,
                            )

            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text="Spy Tools Inventory")
            
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching spy tools: {e}", ephemeral=True
            )

    async def show_profile_customization(self, interaction: discord.Interaction):
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": self.guild_id, f"members.{self.user_id}": {"$exists": True}},
                {f"members.{self.user_id}.inventory.profile": 1},
            )

            profile_inventory = (
                user_data.get("members", {})
                .get(self.user_id, {})
                .get("inventory", {})
                .get("profile", {})
            )

            profile_items = {}
            for category in ["backgrounds", "fonts", "items"]:
                if category in profile_inventory:
                    profile_items[category] = profile_inventory[category]

            if not profile_items:
                embed = discord.Embed(
                    title="🎨 Profile Customization Inventory",
                    description="You don't have any profile customization items yet. Visit the shop to get some!",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
                await interaction.response.edit_message(embed=embed, view=self.parent_view)
            else:
                embed = discord.Embed(
                    title="🎨 Profile Customization Inventory",
                    description="Select a subcategory to view your items",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
                embed.set_thumbnail(url=self.author.avatar.url)
                embed.set_footer(text="Profile Customization Inventory")

                # Add profile subcategory select menu
                profile_subcategory_select = ProfileSubcategorySelect(
                    profile_items, self.guild_id, self.user_id, self.author, self.parent_view
                )
                self.parent_view.add_item(profile_subcategory_select)

                await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching profile items: {e}", ephemeral=True
            )

    async def show_gacha_games(self, interaction: discord.Interaction):
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": self.guild_id, f"members.{self.user_id}": {"$exists": True}},
                {f"members.{self.user_id}.inventory.gacha.games": 1},
            )

            games = (
                user_data.get("members", {})
                .get(self.user_id, {})
                .get("inventory", {})
                .get("gacha", {})
                .get("games", {})
            )

            if not games:
                embed = discord.Embed(
                    title="🎰 Gacha Games Inventory",
                    description="You don't have any gacha games yet. Visit the shop to get some!",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
            else:
                embed = discord.Embed(
                    title="🎰 Gacha Games Inventory",
                    description="Your collection of gacha games",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )

                for game_name, quantity in games.items():
                    if quantity > 0:
                        emoji = "🎰"  # Or fetch specific emoji
                        embed.add_field(
                            name=f"{game_name.title()}",
                            value=f"{emoji} `x{quantity}`",
                            inline=False,
                        )

            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text="Gacha Games Inventory")
            
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching gacha games: {e}", ephemeral=True
            )

    async def show_pokemon_spawns(self, interaction: discord.Interaction):
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": self.guild_id, f"members.{self.user_id}": {"$exists": True}},
                {f"members.{self.user_id}.inventory.pokemon.spawns": 1},
            )

            spawns = (
                user_data.get("members", {})
                .get(self.user_id, {})
                .get("inventory", {})
                .get("pokemon", {})
                .get("spawns", {})
            )

            if not spawns:
                embed = discord.Embed(
                    title="🐾 Pokemon Spawns Inventory",
                    description="You don't have any Pokemon spawn items yet. Visit the shop to get some!",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )
            else:
                embed = discord.Embed(
                    title="🐾 Pokemon Spawns Inventory",
                    description="Your collection of Pokemon spawn items",
                    color=primary_color(),
                    timestamp=datetime.now(),
                )

                for item_name, quantity in spawns.items():
                    if quantity > 0:
                        embed.add_field(
                            name=f"{item_name.title()}",
                            value=f"🐾 `x{quantity}`",
                            inline=False,
                        )

            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text="Pokemon Spawns Inventory")
            
            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching Pokemon spawns: {e}", ephemeral=True
            )


class ProfileSubcategorySelect(discord.ui.Select):
    def __init__(self, profile_items, guild_id, user_id, author, parent_view):
        options = [
            discord.SelectOption(
                emoji="🖼️",
                label="Backgrounds",
                description=f"You own {sum(profile_items.get('backgrounds', {}).values())} backgrounds",
                value="backgrounds"
            ),
            discord.SelectOption(
                emoji="🔤",
                label="Fonts",
                description=f"You own {sum(profile_items.get('fonts', {}).values())} fonts",
                value="fonts"
            ),
            discord.SelectOption(
                emoji="🎯",
                label="Items",
                description=f"You own {sum(profile_items.get('items', {}).values())} items",
                value="items"
            ),
        ]
        super().__init__(placeholder="🎨 Select a profile customization category", options=options)
        self.profile_items = profile_items
        self.guild_id = guild_id
        self.user_id = user_id
        self.author = author
        self.parent_view = parent_view
        self.current_page = 0
        self.items_per_page = 5

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your inventory interface.", ephemeral=True
                )
                return

            category = self.values[0]
            items = self.profile_items.get(category, {})
            items_list = [(name, qty) for name, qty in items.items() if qty > 0]
            total_pages = (len(items_list) + self.items_per_page - 1) // self.items_per_page

            embed = discord.Embed(
                title=f"🎨 {category.title()} Inventory",
                description=f"Your collection of {category}",
                color=primary_color(),
                timestamp=datetime.now(),
            )
            embed.set_thumbnail(url=self.author.avatar.url)
            embed.set_footer(text=f"Page {self.current_page + 1}/{max(total_pages, 1)}")

            if not items_list:
                embed.description = f"You don't have any {category} yet. Visit the shop to get some!"
            else:
                start_idx = self.current_page * self.items_per_page
                end_idx = start_idx + self.items_per_page
                for item_name, quantity in items_list[start_idx:end_idx]:
                    emoji = "🖼️" if category == "backgrounds" else "🔤" if category == "fonts" else "🎯"
                    embed.add_field(
                        name=f"{item_name.title()}",
                        value=f"{emoji} `x{quantity}`",
                        inline=False,
                    )

            # Update view with pagination buttons
            self.parent_view.clear_items()
            self.parent_view.add_item(InventoryCategorySelect(
                self.parent_view.quest_data, self.guild_id, self.user_id, self.author, self.parent_view
            ))
            self.parent_view.add_item(self)
            if total_pages > 1:
                self.parent_view.add_item(PaginationButton("⬅️", "prev", self, disabled=self.current_page == 0))
                self.parent_view.add_item(PaginationButton("➡️", "next", self, disabled=self.current_page == total_pages - 1))

            await interaction.response.edit_message(embed=embed, view=self.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while fetching {category}: {e}", ephemeral=True
            )


class PaginationButton(discord.ui.Button):
    def __init__(self, emoji, action, select_menu, disabled=False):
        super().__init__(style=discord.ButtonStyle.primary, emoji=emoji, disabled=disabled)
        self.action = action
        self.select_menu = select_menu

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(self.select_menu.user_id) != int(interaction.user.id):
                await interaction.response.send_message(
                    "This is not your inventory interface.", ephemeral=True
                )
                return

            if self.action == "prev":
                self.select_menu.current_page -= 1
            elif self.action == "next":
                self.select_menu.current_page += 1

            # Rebuild the embed for the current category
            category = self.select_menu.values[0] if self.select_menu.values else "backgrounds"
            items = self.select_menu.profile_items.get(category, {})
            items_list = [(name, qty) for name, qty in items.items() if qty > 0]
            total_pages = (len(items_list) + self.select_menu.items_per_page - 1) // self.select_menu.items_per_page

            embed = discord.Embed(
                title=f"🎨 {category.title()} Inventory",
                description=f"Your collection of {category}",
                color=primary_color(),
                timestamp=datetime.now(),
            )
            embed.set_thumbnail(url=self.select_menu.author.avatar.url)
            embed.set_footer(text=f"Page {self.select_menu.current_page + 1}/{max(total_pages, 1)}")

            if not items_list:
                embed.description = f"You don't have any {category} yet. Visit the shop to get some!"
            else:
                start_idx = self.select_menu.current_page * self.select_menu.items_per_page
                end_idx = start_idx + self.select_menu.items_per_page
                for item_name, quantity in items_list[start_idx:end_idx]:
                    emoji = "🖼️" if category == "backgrounds" else "🔤" if category == "fonts" else "🎯"
                    embed.add_field(
                        name=f"{item_name.title()}",
                        value=f"{emoji} `x{quantity}`",
                        inline=False,
                    )

            # Update view with pagination buttons
            self.select_menu.parent_view.clear_items()
            self.select_menu.parent_view.add_item(InventoryCategorySelect(
                self.select_menu.parent_view.quest_data, self.guild_id, self.select_menu.user_id, self.select_menu.author, self.select_menu.parent_view
            ))
            self.select_menu.parent_view.add_item(self.select_menu)
            if total_pages > 1:
                self.select_menu.parent_view.add_item(PaginationButton("⬅️", "prev", self.select_menu, disabled=self.select_menu.current_page == 0))
                self.select_menu.parent_view.add_item(PaginationButton("➡️", "next", self.select_menu, disabled=self.select_menu.current_page == total_pages - 1))

            await interaction.response.edit_message(embed=embed, view=self.select_menu.parent_view)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                f"An error occurred while navigating: {e}", ephemeral=True
            )



#----------------------------------------------------------

class ShopConfig:
    """Unified configuration class for Discord shop system styling and constants"""
    
    # Color scheme
    COLORS = {
        "primary": primary_color(),
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.orange(),
        "info": discord.Color.blurple(),
        "secondary": discord.Color.greyple()
    }
    
    # Emoji constants
    EMOJIS = {
        # Shop categories
        "spy_tools": "🕵️",
        "profile_customization": "🎨",
        "gacha_games": "🎰",
        "pokemon_spawns": "🐾",
        "shop": "🛒",
        
        # Profile customization
        "backgrounds": "🖼️",
        "fonts": "🔤",
        "items": "🎯",
        "default_family": "❔",
        
        # Status indicators
        "owned": "✅",
        "can_purchase": "💰",
        "insufficient": "❌",
        "warning": "⚠️",
        "success": "✅",
        "error": "❌",
        "info": "ℹ️",
        
        # Navigation
        "prev": "⬅️",
        "next": "➡️",
        
        # Materials
        "materials": "🛠️",
        "red_indicator": "<:red:1261639413943762944>",
        "yellow_indicator": "<:yellow:1261639412253724774>",
        "green_indicator": "<:green:1261639410181476443>",

        # Gacha
        "gacha": "🎲"
    }
    
    # Standard embed templates
    @staticmethod
    def create_base_embed(title: str, description: str, color: discord.Color = None) -> discord.Embed:
        """Create a standardized embed with consistent formatting"""
        if color is None:
            color = ShopConfig.COLORS["primary"]
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        return embed
    
    @staticmethod
    def create_shop_embed(title: str, description: str, balance: int = None) -> discord.Embed:
        """Create a shop-specific embed with balance footer"""
        embed = ShopConfig.create_base_embed(title, description, ShopConfig.COLORS["primary"])
        if balance is not None:
            embed.set_footer(text=f"Your Balance: {balance:,} Stella Points")
        return embed
    
    @staticmethod
    def create_success_embed(title: str, description: str) -> discord.Embed:
        """Create a success message embed"""
        return ShopConfig.create_base_embed(title, description, ShopConfig.COLORS["success"])
    
    @staticmethod
    def create_error_embed(title: str, description: str) -> discord.Embed:
        """Create an error message embed"""
        return ShopConfig.create_base_embed(title, description, ShopConfig.COLORS["error"])
    
    @staticmethod
    def create_info_embed(title: str, description: str) -> discord.Embed:
        """Create an info message embed"""
        return ShopConfig.create_base_embed(title, description, ShopConfig.COLORS["info"])
    
    # Select menu configurations
    SELECT_CONFIGS = {
        "shop_category": {
            "placeholder": f"{EMOJIS['shop']} Select a shop category",
            "options": [
                {
                    "emoji": EMOJIS["spy_tools"],
                    "label": "Spy Tools",
                    "description": "Tools for espionage and tactical operations",
                    "value": "spy_tools"
                },
                {
                    "emoji": EMOJIS["profile_customization"],
                    "label": "Profile Customization",
                    "description": "Backgrounds, fonts, and decorative items",
                    "value": "profile_customization"
                },
                {
                    "emoji": EMOJIS["gacha_games"],
                    "label": "Gacha Games",
                    "description": "Random item draws and loot boxes",
                    "value": "gacha_games"
                },
                {
                    "emoji": EMOJIS["pokemon_spawns"],
                    "label": "Poketwo Spawns",
                    "description": "Poketwo decorations and spawn layout",
                    "value": "pokemon_spawns"
                }
            ]
        },
        "profile_family": {
            "placeholder": "Select a character family"
        },
        "profile_type": {
            "placeholder": "Select item type"
        },
        "spy_tool": {
            "placeholder": "Select a spy tool"
        },
        "pokemon_section": {
            "placeholder": "Select a section"
        }
    }
    
    # Button styling configurations
    BUTTON_STYLES = {
        "owned": {
            "style": discord.ButtonStyle.green,
            "disabled": True
        },
        "can_purchase": {
            "style": discord.ButtonStyle.primary,
            "disabled": False
        },
        "insufficient": {
            "style": discord.ButtonStyle.grey,
            "disabled": True
        },
        "navigation": {
            "style": discord.ButtonStyle.secondary,
            "disabled": False
        },
        "buy_enabled": {
            "style": discord.ButtonStyle.green,
            "disabled": False
        },
        "buy_disabled": {
            "style": discord.ButtonStyle.grey,
            "disabled": True
        }
    }
    
    # Standard error messages
    ERROR_MESSAGES = {
        "not_your_interface": "This is not your shop interface.",
        "item_not_found": "Item not found.",
        "insufficient_points": "You do not have enough points to purchase this item.",
        "already_owned": "You already own this item.",
        "no_items_available": "No items available at the moment.",
        "generic_error": "An error occurred. Please try again."
    }
    
    # Success messages
    SUCCESS_MESSAGES = {
        "purchase_successful": "Purchase Successful!",
        "item_added": "Item has been added to your inventory."
    }
    
    # Pagination settings
    PAGINATION = {
        "items_per_page": 10,
        "max_buttons_per_row": 5,
        "max_rows": 4
    }
    
    # Shop images
    SHOP_IMAGES = {
        "spy_tools": "https://media.discordapp.net/attachments/1279353553110040596/1419515254928441457/a6acb170-e5e2-4067-8ef9-c86816de741e_removalai_preview.png",
        "profile_customization": "https://media.discordapp.net/attachments/1279353553110040596/1419486274531889262/04310b69-499a-4487-90ea-027bfce4a0aa_removalai_preview.png",
        "pokemon_spawns": "https://media.discordapp.net/attachments/1279353553110040596/1419478776613699665/ad51d45f-70b8-4a52-99ff-f87592ce3d2c_removalai_preview.png",
        "gacha_games": "https://media.discordapp.net/attachments/1279353553110040596/1419526087402197032/AAHar4d7MANRf42MFGfA2njCtEHCWpykVRKDnJLC3meHNd3HyA6KVzcjTfiaF58RFnziXWuDf0swhWDC3kTrBb0JIqrzN5-0twFmxzxrBJEA9sAVinvI4LByafkDoMUL4UWa0tgruwHvxW5i0ESq45EewiR-3amR-MH5uTzga5xpatWp0zvgt75HteP9DjdqkUKkVg6xsiOZQy8RIY2vBW-w0jMvoK5pv3CCqMAyImtPQEHw68_RNHwvGkXd0C9GYu4d-m8zs-o8ERpPRdupKVdrAcPbV93QcyQ9YRId.png?ex=68de9a70&is=68dd48f0&hm=deb800d36a71b27f105d7c2bf081aed8c011078d2ca64c45a9fdcbb75a839008&=&format=webp&quality=lossless&width=839&height=839"
    }
    
    @staticmethod
    def get_status_indicator(user_quantity: int, required_quantity: int = 1, user_balance: int = 0, item_price: int = 0) -> str:
        """Get appropriate status indicator emoji based on item status"""
        if user_quantity >= required_quantity:
            return ShopConfig.EMOJIS["owned"]
        elif user_balance >= item_price:
            return ShopConfig.EMOJIS["can_purchase"]
        else:
            return ShopConfig.EMOJIS["insufficient"]
    
    @staticmethod
    def get_material_indicator(user_quantity: int, required_quantity: int) -> str:
        """Get material status indicator"""
        if user_quantity == 0:
            return ShopConfig.EMOJIS["red_indicator"]
        elif user_quantity < required_quantity:
            return ShopConfig.EMOJIS["yellow_indicator"]
        else:
            return ShopConfig.EMOJIS["green_indicator"]
    
    @staticmethod
    def get_button_config(user_quantity: int, user_balance: int, item_price: int) -> Dict[str, Any]:
        """Get button configuration based on item status"""
        if user_quantity > 0:
            return ShopConfig.BUTTON_STYLES["owned"]
        elif user_balance >= item_price:
            return ShopConfig.BUTTON_STYLES["can_purchase"]
        else:
            return ShopConfig.BUTTON_STYLES["insufficient"]
    
    @staticmethod
    def format_balance(balance: int) -> str:
        """Format balance with proper comma separation"""
        return f"{balance:,}"
    
    @staticmethod
    def format_price(price: int) -> str:
        """Format price display"""
        return f"{price:,} pts" if price > 0 else "Free"
    
    @staticmethod
    def create_legend_text() -> str:
        """Create standard legend text for shop displays"""
        return f"> {ShopConfig.EMOJIS['owned']} Owned | {ShopConfig.EMOJIS['can_purchase']} Can Purchase | {ShopConfig.EMOJIS['insufficient']} Insufficient Points"

#---------------------------------------------------------------------------------

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
            material["name"]: material.get("emoji", ShopConfig.EMOJIS["materials"])
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
        
        error_embed = ShopConfig.create_error_embed(
            f"{ShopConfig.EMOJIS['error']} Error",
            ShopConfig.ERROR_MESSAGES["generic_error"]
        )
        
        try:
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
        except:
            await interaction.followup.send(embed=error_embed, ephemeral=True)

class ShopCategorySelect(discord.ui.Select):
    def __init__(self, shop_data, materials_dict, quest_data, user_id, guild_id):
        config = ShopConfig.SELECT_CONFIGS["shop_category"]
        options = [
            discord.SelectOption(**option_config)
            for option_config in config["options"]
        ]
        
        super().__init__(placeholder=config["placeholder"], options=options)
        self.shop_data = shop_data
        self.materials_dict = materials_dict
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
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
            await ShopView.handle_error(interaction, e)

    async def show_spy_tools(self, interaction: discord.Interaction):
        spy_tools = self.shop_data.get("SpyTools", {}).get("items", [])
        if not spy_tools:
            error_embed = ShopConfig.create_info_embed(
                f"{ShopConfig.EMOJIS['info']} No Items",
                ShopConfig.ERROR_MESSAGES["no_items_available"]
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        select = SpyToolSelect(
            self.shop_data, self.materials_dict, self.quest_data, self.user_id, self.guild_id
        )
        
        embed = ShopConfig.create_shop_embed(
            f"{ShopConfig.EMOJIS['spy_tools']} Spy Tools Shop",
            "Select a spy tool to view details and purchase materials"
        )
        embed.set_image(url=ShopConfig.SHOP_IMAGES["spy_tools"])
        
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_profile_customization(self, interaction: discord.Interaction):
        profile_data = self.shop_data.get("ProfileCustomization", {})
        if not profile_data:
            error_embed = ShopConfig.create_info_embed(
                f"{ShopConfig.EMOJIS['info']} No Items",
                ShopConfig.ERROR_MESSAGES["no_items_available"]
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        select = ProfileFamilySelect(
            self.shop_data, self.quest_data, self.user_id, self.guild_id
        )
        
        embed = ShopConfig.create_shop_embed(
            f"{ShopConfig.EMOJIS['profile_customization']} Profile Customization Shop",
            "Customize your profile with backgrounds, fonts, and items"
        )
        embed.set_image(url=ShopConfig.SHOP_IMAGES["profile_customization"])
        
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def show_gacha_games(self, interaction: discord.Interaction):
        gacha_data = self.shop_data.get("GachaGames", {})
        if not gacha_data:
            error_embed = ShopConfig.create_info_embed(
                f"{ShopConfig.EMOJIS['info']} No Items",
                ShopConfig.ERROR_MESSAGES["no_items_available"]
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        items = gacha_data.get("items", [])
        if not items:
            error_embed = ShopConfig.create_info_embed(
                f"{ShopConfig.EMOJIS['info']} No Items",
                "No gacha games available at the moment."
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        gacha_view = GachaGameView(items, self.quest_data, self.user_id, self.guild_id)
        embed = await gacha_view.create_shop_embed()
        await gacha_view.update_view()
        await interaction.response.send_message(embed=embed, view=gacha_view, ephemeral=True)

    async def show_pokemon_spawns(self, interaction: discord.Interaction):
        pokemon_spawns = self.shop_data.get("PoketwoSpawns", {})
        if not pokemon_spawns:
            error_embed = ShopConfig.create_info_embed(
                f"{ShopConfig.EMOJIS['info']} No Items",
                ShopConfig.ERROR_MESSAGES["no_items_available"]
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        main_description = pokemon_spawns.get("main_description", "")
        sections = pokemon_spawns.get("sections", {})

        if not sections:
            error_embed = ShopConfig.create_info_embed(
                f"{ShopConfig.EMOJIS['info']} No Sections",
                "No Pokemon spawn sections available at the moment."
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        select = PokemonSpawnSectionSelect(
            self.shop_data, self.quest_data, self.user_id, self.guild_id
        )

        embed = ShopConfig.create_shop_embed(
            f"{ShopConfig.EMOJIS['pokemon_spawns']} Poketwo Spawns Shop",
            main_description or "Select a section to browse Pokemon spawn items"
        )
        embed.set_image(url=ShopConfig.SHOP_IMAGES["pokemon_spawns"])

        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ProfileFamilySelect(discord.ui.Select):
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
                emoji = ShopConfig.EMOJIS["default_family"]
            
            description = f"{family} themed items"
            options.append(discord.SelectOption(label=family, description=description, value=family, emoji=emoji))

        super().__init__(placeholder=ShopConfig.SELECT_CONFIGS["profile_family"]["placeholder"], options=options)
        self.shop_data = shop_data
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    "This is not your customization interface."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            family = self.values[0]
            profile_data = self.shop_data.get("ProfileCustomization", {}).get(family, {})
            if not profile_data:
                error_embed = ShopConfig.create_info_embed(
                    f"{ShopConfig.EMOJIS['info']} No Items",
                    f"No {family} customization options available."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            options = []
            for item_type in ["Backgrounds", "Fonts", "Items"]:
                if item_type in profile_data:
                    emoji = ShopConfig.EMOJIS[item_type.lower()]
                    description = f"{item_type} ({len(profile_data[item_type])} available)"
                    options.append(discord.SelectOption(label=item_type, description=description, value=item_type, emoji=emoji))

            type_select = ProfileTypeSelect(profile_data, family, self.quest_data, self.user_id, self.guild_id)
            type_select.options = options
            
            view = discord.ui.View()
            view.add_item(type_select)

            embed = ShopConfig.create_shop_embed(
                f"{ShopConfig.EMOJIS['profile_customization']} {family} Customization",
                "Choose the type of customization item you want to browse"
            )
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

class ProfileTypeSelect(discord.ui.Select):
    def __init__(self, profile_data, family, quest_data, user_id, guild_id):
        super().__init__(placeholder=ShopConfig.SELECT_CONFIGS["profile_type"]["placeholder"])
        self.profile_data = profile_data
        self.family = family
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    "This is not your customization interface."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            item_type = self.values[0]
            items = self.profile_data.get(item_type, [])
            if not items:
                error_embed = ShopConfig.create_info_embed(
                    f"{ShopConfig.EMOJIS['info']} No Items",
                    f"No {item_type.lower()} available for {self.family}."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            item_view = ProfileItemView(items, item_type, self.quest_data, self.user_id, self.guild_id, self.family)
            embed = await item_view.create_shop_embed()
            await item_view.update_view()
            await interaction.response.edit_message(embed=embed, view=item_view)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

class ProfileItemView(discord.ui.View):
    def __init__(self, items, item_type, quest_data, user_id, guild_id, family):
        super().__init__(timeout=300)
        self.items = items
        self.item_type = item_type
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.family = family
        self.page = 0
        self.items_per_page = ShopConfig.PAGINATION["items_per_page"]
        self.max_pages = (len(items) - 1) // self.items_per_page + 1

    def _get_category_for_item_type(self, item_type):
        """Map item types to database categories using dot notation"""
        mapping = {
            "Backgrounds": "profile.backgrounds",
            "Fonts": "profile.fonts", 
            "Items": "profile.items"
        }
        return mapping.get(item_type, "profile.items")

    async def create_shop_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        embed = ShopConfig.create_shop_embed(
            f"{ShopConfig.EMOJIS['profile_customization']} {self.family} {self.item_type}",
            f"Browse and purchase {self.item_type.lower()} for your profile (Page {self.page + 1}/{self.max_pages})"
        )

        item_list = []
        category = self._get_category_for_item_type(self.item_type)
        
        for i, item in enumerate(current_items):
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, category, item["name"]) or 0
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            indicator = ShopConfig.get_status_indicator(user_quantity, 1, user_balance, item["points"])
            name_display = f"~~{item['name']}~~" if user_quantity > 0 else item["name"]
            price_display = ShopConfig.format_price(item["points"])
            character = item.get("character", "N/A")
            
            item_entry = f"{indicator} **{name_display}** - {price_display}"
            if user_quantity > 0:
                item_entry += f" (Owned: {user_quantity})"
            item_entry += f"\n╰>   *{character.replace('_','')}* - {item['description'][:50]}...\n"
            item_list.append(f"`{start + i + 1}.` {item_entry}")

        if item_list:
            embed.add_field(name="Items Available", value="\n".join(item_list), inline=False)
        
        embed.add_field(name="", value=ShopConfig.create_legend_text(), inline=False)
        
        balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
        embed.set_footer(text=f"Your Balance: {ShopConfig.format_balance(balance)} Stella Points")
        return embed

    async def update_view(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]
        category = self._get_category_for_item_type(self.item_type)

        for i, item in enumerate(current_items):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, category, item["name"]) or 0

            button_config = ShopConfig.get_button_config(user_quantity, user_balance, item["points"])
            
            btn = discord.ui.Button(
                style=button_config["style"],
                label=str(i + 1),
                custom_id=f"item_{start + i}",
                disabled=button_config["disabled"]
            )
            btn.callback = self.item_callback
            self.add_item(btn)

        # Add pagination buttons
        if self.max_pages > 1:
            if self.page > 0:
                prev_btn = discord.ui.Button(
                    emoji=ShopConfig.EMOJIS["prev"],
                    style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                    custom_id="prev_page"
                )
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)
            
            if self.page < self.max_pages - 1:
                next_btn = discord.ui.Button(
                    emoji=ShopConfig.EMOJIS["next"],
                    style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                    custom_id="next_page"
                )
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

    async def item_callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            index = int(interaction.data["custom_id"].split("_")[1])
            item = self.items[index]
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            category = self._get_category_for_item_type(self.item_type)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, category, item["name"]) or 0

            if user_quantity > 0:
                info_embed = ShopConfig.create_info_embed(
                    f"{ShopConfig.EMOJIS['info']} Already Owned",
                    f"You already own **{item['name']}** (Quantity: {user_quantity})"
                )
                return await interaction.response.send_message(embed=info_embed, ephemeral=True)

            if user_balance >= item["points"]:
                await self.quest_data.add_balance(self.user_id, self.guild_id, -item["points"])
                await self.quest_data.add_item_to_inventory(self.guild_id, self.user_id, category, item["name"], 1)
                new_balance = user_balance - item["points"]
                
                embed = await self.create_shop_embed()
                embed.title = f"{ShopConfig.EMOJIS['success']} {ShopConfig.SUCCESS_MESSAGES['purchase_successful']}"
                embed.description = f"You've purchased **{item['name']}** for {ShopConfig.format_price(item['points'])}!\n\n{embed.description}"
                embed.add_field(name="Description", value=item["description"], inline=False)
                embed.add_field(name="Character", value=item.get("character", "N/A"), inline=True)
                embed.set_footer(text=f"Remaining balance: {ShopConfig.format_balance(new_balance)} points")
                
                await self.update_view()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Insufficient Points",
                    f"You need {ShopConfig.format_price(item['points'])} but only have {ShopConfig.format_balance(user_balance)}."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

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

class SpyToolSelect(discord.ui.Select):
    def __init__(self, shop_data, materials_dict, quest_data, user_id, guild_id):
        options = [
            discord.SelectOption(
                label=tool["name"],
                description=tool["description"][:100],
                emoji=tool.get("emoji", ShopConfig.EMOJIS["spy_tools"]),
                value=tool["name"]
            ) for tool in shop_data.get("SpyTools", {}).get("items", [])
        ]
        super().__init__(placeholder=ShopConfig.SELECT_CONFIGS["spy_tool"]["placeholder"], options=options)
        self.shop_data = shop_data
        self.materials_dict = materials_dict
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            tool_name = self.values[0]
            tool = next(
                (t for t in self.shop_data.get("SpyTools", {}).get("items", []) if t["name"] == tool_name),
                None
            )

            if not tool:
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Not Found",
                    ShopConfig.ERROR_MESSAGES["item_not_found"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            emoji = tool.get("emoji", ShopConfig.EMOJIS["spy_tools"])
            description = tool.get("description", "No description available.")
            materials_list = "\n".join(
                [await self.format_materials(item) for item in tool.get("materials", [])]
            )
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            shop_embed = ShopConfig.create_shop_embed(
                tool_name,
                f"{emoji} {description}",
                user_balance
            )
            shop_embed.add_field(
                name="Materials Required",
                value=materials_list or "No materials needed",
                inline=False
            )

            view = MaterialsButtonView(
                self.shop_data,
                self.quest_data,
                self.user_id,
                self.guild_id,
                shop_embed
            )
            await view.update_view()

            await interaction.response.send_message(embed=shop_embed, view=view, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

    async def format_materials(self, item):
        material_name = item.get("material", "")
        required_quantity = item.get("quantity", 0)
        user_quantity = (
            await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, "spytools.materials", material_name
            ) or 0
        )

        indicator_emoji = ShopConfig.get_material_indicator(user_quantity, required_quantity)
        material_emoji = self.materials_dict.get(material_name, ShopConfig.EMOJIS["materials"])

        return f"{indicator_emoji} {material_emoji} **{material_name}** - {user_quantity}/{required_quantity}"

class MaterialsButtonView(discord.ui.View):
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
            material["name"]: material.get("emoji", ShopConfig.EMOJIS["materials"])
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

        # Buy tool button
        if all(material_checks):
            buy_config = ShopConfig.BUTTON_STYLES["buy_enabled"]
        else:
            buy_config = ShopConfig.BUTTON_STYLES["buy_disabled"]

        buy_button = discord.ui.Button(
            style=buy_config["style"],
            label="Buy Tool",
            custom_id="buy_button",
            row=0,
            disabled=buy_config["disabled"]
        )
        buy_button.callback = self.buy_tool_callback
        self.add_item(buy_button)

        # Material buttons
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
                emoji = material.get("emoji", ShopConfig.EMOJIS["materials"])
                price = material.get("price", "")

                material_button = discord.ui.Button(
                    style=ShopConfig.BUTTON_STYLES["can_purchase"]["style"],
                    emoji=emoji,
                    label=f"{price} stp",
                    custom_id=name,
                    row=current_row,
                )
                material_button.callback = self.material_callback
                self.add_item(material_button)
                item_count += 1

                if item_count % ShopConfig.PAGINATION["max_buttons_per_row"] == 0:
                    current_row += 1
                    item_count = 0

            except Exception as e:
                print(f"Error generating button for material: {name}, Emoji: {emoji}")
                print(f"Error: {e}")
                continue

        # Pagination buttons
        pagination_row = current_row if current_row > 1 else 2

        if self.page > 0:
            prev_button = discord.ui.Button(
                emoji=ShopConfig.EMOJIS["prev"],
                style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                custom_id="prev_page",
                row=pagination_row,
            )
            prev_button.callback = self.prev_page_callback
            self.add_item(prev_button)

        if self.page < self.max_pages - 1:
            next_button = discord.ui.Button(
                emoji=ShopConfig.EMOJIS["next"],
                style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                custom_id="next_page",
                row=pagination_row,
            )
            next_button.callback = self.next_page_callback
            self.add_item(next_button)

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
                self.guild_id, self.user_id, "spytools.materials", material_name
            )
            or 0
        )
        return user_quantity >= required_quantity

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
            error_embed = ShopConfig.create_error_embed(
                f"{ShopConfig.EMOJIS['error']} Not Found",
                ShopConfig.ERROR_MESSAGES["item_not_found"]
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)
            return

        emoji = tool.get("emoji", ShopConfig.EMOJIS["spy_tools"])
        description = tool.get("description", "No description available.")
        materials_list = "\n".join(
            [await self.format_materials(item) for item in tool.get("materials", [])]
        )
        user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

        shop_embed = ShopConfig.create_shop_embed(
            tool_name,
            f"{emoji} {description}",
            user_balance
        )
        shop_embed.add_field(
            name="Materials Required",
            value=materials_list or "No materials needed",
            inline=False,
        )

        await self.update_view()
        await interaction.response.edit_message(embed=shop_embed, view=self)

    async def format_materials(self, item):
        material_name = item.get("material", "")
        required_quantity = item.get("quantity", 0)
        user_quantity = await self.get_user_inventory_count(material_name) or 0

        indicator_emoji = ShopConfig.get_material_indicator(user_quantity, required_quantity)
        material_emoji = self.materials_dict.get(material_name, ShopConfig.EMOJIS["materials"])

        return f"{indicator_emoji} {material_emoji} **{material_name}** - {user_quantity}/{required_quantity}"

    async def get_user_inventory_count(self, material_name):
        material_count = await self.quest_data.get_user_inventory_count(
            self.guild_id, self.user_id, "spytools.materials", material_name
        )
        return material_count

    async def material_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
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
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Not Found",
                    ShopConfig.ERROR_MESSAGES["item_not_found"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            price = material.get("price", 0)
            user_balance = await self.quest_data.get_balance(
                self.user_id, self.guild_id
            )

            if user_balance >= price:
                await self.quest_data.add_item_to_inventory(
                    self.guild_id, self.user_id, "spytools.materials", material_name, 1
                )
                spent = -price
                await self.quest_data.add_balance(self.user_id, self.guild_id, spent)

                await self.refresh_embed(interaction)
            else:
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Insufficient Points",
                    f"You do not have enough points to purchase {material_name}."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

    async def buy_tool_callback(self, interaction: discord.Interaction):
        try:
            if int(self.user_id) != int(interaction.user.id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
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
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Not Found",
                    ShopConfig.ERROR_MESSAGES["item_not_found"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            # Check if user has all required materials
            for material in tool.get("materials", []):
                material_name = material.get("material", "")
                required_quantity = material.get("quantity", 0)
                user_quantity = (
                    await self.quest_data.get_user_inventory_count(
                        self.guild_id, self.user_id, "spytools.materials", material_name
                    )
                    or 0
                )

                if user_quantity < required_quantity:
                    error_embed = ShopConfig.create_error_embed(
                        f"{ShopConfig.EMOJIS['error']} Insufficient Materials",
                        f"Not enough {material_name}. You need {required_quantity} but have {user_quantity}."
                    )
                    await interaction.response.send_message(embed=error_embed, ephemeral=True)
                    return

            # Consume materials and add tool
            for material in tool.get("materials", []):
                material_name = material.get("material", "")
                required_quantity = material.get("quantity", 0)
                await self.quest_data.add_item_to_inventory(
                    self.guild_id, self.user_id, "spytools.materials", material_name, -required_quantity
                )

            await self.quest_data.add_item_to_inventory(
                self.guild_id, self.user_id, "spytools.tools", tool_name, 1
            )

            quantity = await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, "spytools.tools", tool_name
            )

            success_embed = ShopConfig.create_success_embed(
                f"{ShopConfig.EMOJIS['success']} {ShopConfig.SUCCESS_MESSAGES['purchase_successful']}",
                f"**{tool_name}** has been added to your inventory.\nYou now have {quantity} of this tool."
            )

            await interaction.response.send_message(embed=success_embed, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

    async def prev_page_callback(self, interaction: discord.Interaction):
        self.page -= 1
        await self.refresh_embed(interaction)

    async def next_page_callback(self, interaction: discord.Interaction):
        self.page += 1
        await self.refresh_embed(interaction)

class GachaGameView(discord.ui.View):
    def __init__(self, items, quest_data, user_id, guild_id):
        super().__init__(timeout=300)
        self.items = items
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.page = 0
        self.items_per_page = ShopConfig.PAGINATION["items_per_page"]
        self.max_pages = (len(items) - 1) // self.items_per_page + 1

    async def create_shop_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        embed = ShopConfig.create_shop_embed(
            f"{ShopConfig.EMOJIS['gacha_games']} Gacha Games",
            f"Browse and purchase gacha games (Page {self.page + 1}/{self.max_pages})"
        )
        embed.set_image(url=ShopConfig.SHOP_IMAGES["gacha_games"])

        item_list = []
        user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

        for i, item in enumerate(current_items):
            name = item.get("name", "Unknown Game")
            emoji = item.get("emoji", ShopConfig.EMOJIS["gacha"])
            points = item.get("points", 0)
            description = item.get("description", "")
            
            try:
                user_quantity = await self.quest_data.get_user_inventory_count(
                    self.guild_id, self.user_id, "gacha.games", name
                ) or 0
            except Exception as e:
                print(f"Error fetching inventory count for {name}: {e}")
                user_quantity = 0

            indicator = ShopConfig.get_status_indicator(user_quantity, 1, user_balance, points)
            name_display = f"~~{name}~~" if user_quantity > 0 else name
            price_display = ShopConfig.format_price(points)

            item_entry = f"{indicator} {emoji} **{name_display}** - {price_display}"
            if user_quantity > 0:
                item_entry += f" (Owned: {user_quantity})"
            item_entry += f"\n╰> *{description[:50]}...*\n"
            item_list.append(f"`{start + i + 1}.` {item_entry}")

        if item_list:
            embed.add_field(name="Games Available", value="\n".join(item_list), inline=False)
        else:
            embed.add_field(name="Games Available", value="No games found.", inline=False)
        
        embed.add_field(name="", value=ShopConfig.create_legend_text(), inline=False)
        embed.set_footer(text=f"Your Balance: {ShopConfig.format_balance(user_balance)} Stella Points")
        return embed

    async def update_view(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        current_row = 0
        for i, item in enumerate(current_items):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            points = item.get("points", 0)
            
            try:
                user_quantity = await self.quest_data.get_user_inventory_count(
                    self.guild_id, self.user_id, "gacha.games", item.get("name", "")
                ) or 0
            except Exception as e:
                print(f"Error fetching inventory count: {e}")
                user_quantity = 0

            button_config = ShopConfig.get_button_config(user_quantity, user_balance, points)
            
            btn = discord.ui.Button(
                style=button_config["style"],
                label=str(i + 1),
                custom_id=f"item_{start + i}",
                disabled=button_config["disabled"]
            )
            btn.callback = self.item_callback
            self.add_item(btn)

            if (i + 1) % ShopConfig.PAGINATION["max_buttons_per_row"] == 0:
                current_row += 1

        # Pagination buttons
        if self.max_pages > 1:
            pagination_row = current_row + 1 if current_row < ShopConfig.PAGINATION["max_rows"] else ShopConfig.PAGINATION["max_rows"]
            if self.page > 0:
                prev_btn = discord.ui.Button(
                    emoji=ShopConfig.EMOJIS["prev"],
                    style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                    custom_id="prev_page",
                    row=pagination_row
                )
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)
            
            if self.page < self.max_pages - 1:
                next_btn = discord.ui.Button(
                    emoji=ShopConfig.EMOJIS["next"],
                    style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                    custom_id="next_page",
                    row=pagination_row
                )
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

    async def item_callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            index = int(interaction.data["custom_id"].split("_")[1])
            item = self.items[index]
            name = item.get("name", "Unknown Game")
            points = item.get("points", 0)
            
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(
                self.guild_id, self.user_id, "gacha.games", name
            ) or 0

            if user_quantity > 0:
                info_embed = ShopConfig.create_info_embed(
                    f"{ShopConfig.EMOJIS['info']} Already Owned",
                    f"You already own **{name}** (Quantity: {user_quantity})"
                )
                return await interaction.response.send_message(embed=info_embed, ephemeral=True)

            if user_balance >= points:
                await self.quest_data.add_balance(self.user_id, self.guild_id, -points)
                await self.quest_data.add_item_to_inventory(
                    self.guild_id, self.user_id, "gacha.games", name, 1
                )
                new_balance = user_balance - points
                
                embed = await self.create_shop_embed()
                embed.title = f"{ShopConfig.EMOJIS['success']} {ShopConfig.SUCCESS_MESSAGES['purchase_successful']}"
                embed.description = f"You've purchased **{name}** for {ShopConfig.format_price(points)}!\n\n{embed.description}"
                embed.add_field(name="Description", value=item.get("description", "No description available"), inline=False)
                embed.set_footer(text=f"Remaining balance: {ShopConfig.format_balance(new_balance)} points")
                
                await self.update_view()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Insufficient Points",
                    f"You need {ShopConfig.format_price(points)} but only have {ShopConfig.format_balance(user_balance)}."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

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

class PokemonSpawnSectionSelect(discord.ui.Select):
    def __init__(self, shop_data, quest_data, user_id, guild_id):
        options = []
        pokemon_spawns = shop_data.get("PoketwoSpawns", {}).get("sections", {})
        
        for section_name, section_items in pokemon_spawns.items():
            emoji = None
            if section_items:
                emoji = section_items[0].get("emoji")
            if not emoji:
                emoji = ShopConfig.EMOJIS["pokemon_spawns"]
            
            description = f"{section_name} ({len(section_items)} available)"
            options.append(discord.SelectOption(label=section_name, description=description, value=section_name, emoji=emoji))

        super().__init__(placeholder=ShopConfig.SELECT_CONFIGS["pokemon_section"]["placeholder"], options=options)
        self.shop_data = shop_data
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            section = self.values[0]
            pokemon_spawns = self.shop_data.get("PoketwoSpawns", {}).get("sections", {})
            items = pokemon_spawns.get(section, [])
            if not items:
                error_embed = ShopConfig.create_info_embed(
                    f"{ShopConfig.EMOJIS['info']} No Items",
                    f"No items available in {section}."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            item_view = PokemonSpawnItemView(items, section, self.quest_data, self.user_id, self.guild_id)
            embed = await item_view.create_shop_embed()
            await item_view.update_view()
            await interaction.response.edit_message(embed=embed, view=item_view)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

class PokemonSpawnItemView(discord.ui.View):
    def __init__(self, items, section, quest_data, user_id, guild_id):
        super().__init__(timeout=300)
        self.items = items
        self.section = section
        self.quest_data = quest_data
        self.user_id = user_id
        self.guild_id = guild_id
        self.page = 0
        self.items_per_page = ShopConfig.PAGINATION["items_per_page"]
        self.max_pages = (len(items) - 1) // self.items_per_page + 1

    async def create_shop_embed(self):
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        embed = ShopConfig.create_shop_embed(
            f"{ShopConfig.EMOJIS['pokemon_spawns']} {self.section}",
            f"Browse and purchase {self.section.lower()} items for your profile (Page {self.page + 1}/{self.max_pages})"
        )

        item_list = []
        for i, item in enumerate(current_items):
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, "pokemon.spawns", item["name"]) or 0
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)

            indicator = ShopConfig.get_status_indicator(user_quantity, 1, user_balance, item["points"])
            name_display = f"~~{item['name']}~~" if user_quantity > 0 else item["name"]
            price_display = ShopConfig.format_price(item["points"])
            theme = item.get("theme", "N/A")
            
            item_entry = f"{indicator} **{name_display}** - {price_display}"
            if user_quantity > 0:
                item_entry += f" (Owned: {user_quantity})"
            item_entry += f"\n╰>   *{theme.replace("_","")}* - {item['description'][:50]}...\n"
            item_list.append(f"`{start + i + 1}.` {item_entry}")

        if item_list:
            embed.add_field(name="Items Available", value="\n".join(item_list), inline=False)
        
        embed.add_field(name="", value=ShopConfig.create_legend_text(), inline=False)
        
        balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
        embed.set_footer(text=f"Your Balance: {ShopConfig.format_balance(balance)} Stella Points")
        return embed

    async def update_view(self):
        self.clear_items()
        start = self.page * self.items_per_page
        end = start + self.items_per_page
        current_items = self.items[start:end]

        current_row = 0
        for i, item in enumerate(current_items):
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, "pokemon.spawns", item["name"]) or 0

            button_config = ShopConfig.get_button_config(user_quantity, user_balance, item["points"])
            
            btn = discord.ui.Button(
                style=button_config["style"],
                label=str(i + 1),
                custom_id=f"item_{start + i}",
                disabled=button_config["disabled"]
            )
            btn.callback = self.item_callback
            self.add_item(btn)

            if (i + 1) % ShopConfig.PAGINATION["max_buttons_per_row"] == 0:
                current_row += 1

        # Pagination buttons
        if self.max_pages > 1:
            pagination_row = current_row + 1 if current_row < ShopConfig.PAGINATION["max_rows"] else ShopConfig.PAGINATION["max_rows"]
            if self.page > 0:
                prev_btn = discord.ui.Button(
                    emoji=ShopConfig.EMOJIS["prev"],
                    style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                    custom_id="prev_page",
                    row=pagination_row
                )
                prev_btn.callback = self.prev_page_callback
                self.add_item(prev_btn)
            
            if self.page < self.max_pages - 1:
                next_btn = discord.ui.Button(
                    emoji=ShopConfig.EMOJIS["next"],
                    style=ShopConfig.BUTTON_STYLES["navigation"]["style"],
                    custom_id="next_page",
                    row=pagination_row
                )
                next_btn.callback = self.next_page_callback
                self.add_item(next_btn)

    async def item_callback(self, interaction: discord.Interaction):
        try:
            if int(interaction.user.id) != int(self.user_id):
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Access Denied",
                    ShopConfig.ERROR_MESSAGES["not_your_interface"]
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
                return

            index = int(interaction.data["custom_id"].split("_")[1])
            item = self.items[index]
            user_balance = await self.quest_data.get_balance(self.user_id, self.guild_id)
            user_quantity = await self.quest_data.get_user_inventory_count(self.guild_id, self.user_id, "pokemon.spawns", item["name"]) or 0

            if user_quantity > 0:
                info_embed = ShopConfig.create_info_embed(
                    f"{ShopConfig.EMOJIS['info']} Already Owned",
                    f"You already own **{item['name']}** (Quantity: {user_quantity})"
                )
                return await interaction.response.send_message(embed=info_embed, ephemeral=True)

            if user_balance >= item["points"]:
                await self.quest_data.add_balance(self.user_id, self.guild_id, -item["points"])
                await self.quest_data.add_item_to_inventory(self.guild_id, self.user_id, "pokemon.spawns", item["name"], 1)
                new_balance = user_balance - item["points"]
                
                embed = await self.create_shop_embed()
                embed.title = f"{ShopConfig.EMOJIS['success']} {ShopConfig.SUCCESS_MESSAGES['purchase_successful']}"
                embed.description = f"You've purchased **{item['name']}** for {ShopConfig.format_price(item['points'])}!\n\n{embed.description}"
                embed.add_field(name="Description", value=item["description"], inline=False)
                embed.add_field(name="Theme", value=item.get("theme", "N/A"), inline=True)
                if item.get("season"):
                    embed.add_field(name="Season", value=item["season"], inline=True)
                embed.set_footer(text=f"Remaining balance: {ShopConfig.format_balance(new_balance)} points")
                
                await self.update_view()
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                error_embed = ShopConfig.create_error_embed(
                    f"{ShopConfig.EMOJIS['error']} Insufficient Points",
                    f"You need {ShopConfig.format_price(item['points'])} but only have {ShopConfig.format_balance(user_balance)}."
                )
                await interaction.response.send_message(embed=error_embed, ephemeral=True)

        except Exception as e:
            await ShopView.handle_error(interaction, e)

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
























































