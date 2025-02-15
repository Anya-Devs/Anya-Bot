
import os
import traceback
import json

import cv2
import numpy as np
import aiohttp
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


from Imports.discord_imports import *
from Data.const import primary_color, error_custom_embed, Help_Select_Embed_Mapping
from Imports.log_imports import logger


class Help_Thumbnails:
    def __init__(self, json_file_path):
        self.json_file_path = json_file_path
        self.help_embed = self.load_images()

    def load_images(self):
        """Loads the images from the JSON file."""
        try:
            with open(self.json_file_path, "r") as f:
                data = json.load(f)
                return data.get("help_embed", {})
        except (FileNotFoundError, json.JSONDecodeError):
            
            return {
                "anime": {"thumbnail_url": None},
                "information": {"thumbnail_url": None},
                "system": {"thumbnail_url": None, "image_url": None},
                "quest": {"thumbnail_url": None},
                "ai": {"thumbnail_url": None},
                "pokemon": {"thumbnail_url": None},
            }

    def save_images(self):
        """Saves the current help_embed images data back to the JSON file."""
        os.makedirs(os.path.dirname(self.json_file_path), exist_ok=True)
        with open(self.json_file_path, "w") as f:
            json.dump({"help_embed": self.help_embed}, f, indent=4)

    def update_image_url(self, cog_name, url):
        """Updates the image URL for a specific cog in the help_embed."""
        cog_name = cog_name.lower()
        if cog_name in self.help_embed:
            self.help_embed[cog_name]["thumbnail_url"] = url
            self.save_images()
            return f"Updated {cog_name} thumbnail URL successfully."
        else:
            return f"Cog '{cog_name}' not found."

    def get_image_url(self, cog_name):
        """Returns the image URL for the given cog."""
        cog_name = cog_name.lower()
        return self.help_embed.get(cog_name, {}).get("thumbnail_url", None)


class Select(discord.ui.Select):
    def __init__(self, cog_commands, bot, primary_color):
        options = [
            discord.SelectOption(
                label=cog_name.replace("_", " "),
                value=cog_name,
                emoji=Help_Select_Embed_Mapping.emojis.get(cog_name.lower()),
            )
            for cog_name in cog_commands.keys()
            if cog_name.lower() not in ["recommendation", "memo_game", "guide"]
        ]

        if not options:
            options = [
                discord.SelectOption(
                    label="No Categories Available", value="none")
            ]
        super().__init__(
            placeholder="[option]", max_values=1, min_values=1, options=options
        )
        self.cog_commands = cog_commands
        self.bot = bot
        self.page = 0  
        self.primary_color = primary_color
        self.command_mapping_file = "Data/commands/help/command_map.json"
        self.set_thumbnail_file = "Data/commands/help/help_embed_images.json"

    def _ensure_file_exists(self):
        """Ensures the command mapping file exists."""
        os.makedirs(os.path.dirname(self.command_mapping_file), exist_ok=True)
        if not os.path.exists(self.command_mapping_file):
            with open(self.command_mapping_file, "w") as f:
                json.dump({}, f, indent=4)

    def _load_command_mapping(self):
        """Loads the command mapping JSON."""
        self._ensure_file_exists()
        with open(self.command_mapping_file, "r") as f:
            return json.load(f)

    def _save_command_mapping(self, mapping):
        """Saves the updated command mapping JSON."""
        with open(self.command_mapping_file, "w") as f:
            json.dump(mapping, f, indent=4)

    def _update_command_mapping(self):
        """Updates the command mapping by syncing with cog commands."""
        mapping = self._load_command_mapping()
        for cog_name in self.cog_commands.keys():
            if cog_name not in mapping:
                mapping[cog_name] = {}
            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [
                    cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cmd in cog_commands:
                    if cmd.name not in mapping[cog_name]:
                        mapping[cog_name][cmd.name] = "---------"
        self._save_command_mapping(mapping)

    async def callback(self, interaction: discord.Interaction):
        try:
            self._update_command_mapping()

            cog_name = self.values[0]
            if cog_name == "none":
                await interaction.response.send_message(
                    "No categories available.", ephemeral=True
                )
                return

            cog_info = self.cog_commands.get(cog_name)
            color = self.primary_color
            emoji = Help_Select_Embed_Mapping.emojis.get(cog_name.lower())

            
            self.cog_embed1 = discord.Embed(
                title=f'Category - {emoji} {cog_name.replace("_", " ")}',
                description=f'{Help_Select_Embed_Mapping.embeds[cog_name.lower()]["description"] or ""}',
                color=color,
            )
            self.cog_embed2 = discord.Embed(description="", color=color)

            
            help_embed_manager = Help_Thumbnails(
                self.set_thumbnail_file)
            thumbnail_url = help_embed_manager.get_image_url(cog_name)

            if thumbnail_url:
                self.cog_embed2.set_thumbnail(url=thumbnail_url)
            else:
                logger.warning(f"No thumbnail URL found for cog '{cog_name}'.")

            
            image_path = "Data/commands/help/set_image/cog_image.png"
            file = None
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    file = discord.File(f, filename="cog_image.png")
                self.cog_embed2.set_image(url="attachment://cog_image.png")

            
            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [
                    cmd for cmd in cog.get_commands() if not cmd.hidden]
                if cog_commands:
                    command_mapping = self._load_command_mapping().get(cog_name, {})
                    
                    commands_info = "```\n"
                    
                    sorted_commands = sorted(cog_commands, key=lambda cmd: cmd.name)
                    for cmd in sorted_commands:
                        cmd_args = [
                            (
                                f"[{param.name}]"
                                if param.default is not param.empty
                                else f"<{param.name}>"
                            )
                            for param in cmd.clean_params.values()
                        ]
                        args_str = " ".join(cmd_args)  
                        command_info = (
                            f"{cmd.name} {args_str}"
                        )
                        commands_info += f"{command_info}\n"
                    commands_info += "```"
                    
                    self.cog_embed2.description = commands_info
                else:
                    logger.info(f"No visible commands found for cog: {cog_name}")
            else:
                logger.info(f"Cog not found: {cog_name}")

            
            if file:
                await interaction.response.edit_message(
                    embed=self.cog_embed2, attachments=[file]
                )
            else:
                await interaction.response.edit_message(
                    embed=self.cog_embed2, attachments=[]
                )

            logger.info("Message edited successfully.")
        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            logger.debug(f"An error occurred: {traceback_str}")
            pass
        
        
class HelpMenu(discord.ui.View):
    def __init__(self, bot, primary_color, select_view, *, timeout=None):
        super().__init__(timeout=timeout)

        self.bot = bot
        self.primary_color = primary_color

        cog_commands = {}  
        self.add_item(select_view)
        


class Options_ImageGenerator:
    def __init__(self, cog_name):
        """Initialize the ImageGenerator with cog-specific data and load resources."""
        
        self.font_path_header = (
            "Data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        )
        self.font_path_base = (
            "Data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        )
        self.character_path = (
            "Data/commands/help/menu/initial/style/assets/character.png"
        )
        self.background_path = (
            "Data/commands/help/menu/initial/style/assets/background.png"
        )

        
        self.header_font_size = 35
        self.base_font_size = 12

        
        self.header_font_color = "white"
        self.base_font_color = "black"

        
        self.character_scale = 0.4

        
        self.cog_name = cog_name
        self.header_text = f"{cog_name.replace('_', ' ')}"
        self.description_text = self._wrap_text(
            f"{Help_Select_Embed_Mapping.embeds[cog_name.lower()]['description'] or '...'}",
            max_width=500,
        )

        
        self.character_pos = (5, 5)
        self.text_x_offset = 10
        self.text_y_offset = 27
        self.text_spacing = 20

        
        self.color_replacements_map = {
            
            
        }

        
        self._load_resources()
        self._apply_color_replacements()

    def _load_resources(self):
        """Load the fonts and images required for generating the image."""
        self.header_font = ImageFont.truetype(
            self.font_path_header, self.header_font_size
        )
        self.base_font = ImageFont.truetype(
            self.font_path_base, self.base_font_size)
        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")

        
        self._resize_character()

    def _resize_character(self):
        """Resize the character image to a percentage of its original size."""
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height))

    def _apply_color_replacements(self):
        """Replace specific colors in the background image with colors from replacement images, solid colors, or transparency."""
        bg_array = np.array(self.background)

        for old_hex, replacement in self.color_replacements_map.items():
            old_color = tuple(int(old_hex[i: i + 2], 16) for i in (0, 2, 4))
            if replacement == "transparent":  
                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                
                bg_array[mask > 0] = [0, 0, 0, 0]
            elif replacement.startswith("http"):  
                replacement_img = self._download_image(replacement)
                replacement_img = replacement_img.resize(
                    (self.background.width, self.background.height)
                )
                replacement_array = np.array(replacement_img)[:, :, :3]

                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                bg_array[mask > 0, :3] = replacement_array[mask > 0]
            else:  
                replacement_color = tuple(
                    int(replacement[i: i + 2], 16) for i in (1, 3, 5)
                )
                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                bg_array[mask > 0, :3] = replacement_color

        self.background = Image.fromarray(bg_array, "RGBA")

    def _wrap_text(self, text, max_width):
        """Wrap text to fit within the specified width."""
        lines = []
        words = text.split()
        current_line = []

        draw = ImageDraw.Draw(
            Image.new("RGBA", (1, 1))
        )  
        font = ImageFont.truetype(
            self.font_path_base, self.base_font_size
        )  

        for word in words:
            current_line.append(word)
            line_width = draw.textbbox(
                (0, 0), " ".join(current_line), font=font)[2]
            if line_width > max_width:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]

        if current_line:
            lines.append(" ".join(current_line))

        return "\n".join(lines)

    def _draw_text(self, draw, text_x, text_y):
        """Draw all text on the image."""
        
        draw.text(
            (text_x, text_y),
            self.header_text,
            font=self.header_font,
            fill=self.header_font_color,
        )
        text_y += self.header_font.size + self.text_spacing

        
        draw.text(
            (text_x, text_y),
            self.description_text,
            font=self.base_font,
            fill=self.base_font_color,
        )

    @staticmethod
    def _download_image(url):
        """Download an image from a URL."""
        response = requests.get(url)
        response.raise_for_status()  
        return Image.open(BytesIO(response.content)).convert("RGBA")

    def create_image(self):
        """Generate the complete image with the background, character, and text."""
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)

        
        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        
        text_x = self.character.width + self.text_x_offset
        text_y = self.text_y_offset
        self._draw_text(draw, text_x, text_y)

        return bg

    def save_image(self, file_path):
        """Save the generated image to the given file path."""
        img = self.create_image()
        img.save(file_path)
        return file_path

    def show_image(self):
        """Display the generated image within the notebook (for Jupyter environments)."""
        img = self.create_image()
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        display(IPImage(img_bytes.getvalue()))


class ImageGenerator:
    def __init__(self, ctx):
        """Initialize the ImageGenerator with user-specific data and load resources."""
        self.user_name = ctx.author.display_name

        
        self.font_path_header = (
            "Data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        )
        self.font_path_base = (
            "Data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        )
        self.character_path = (
            "Data/commands/help/menu/initial/style/assets/character.png"
        )
        self.background_path = (
            "Data/commands/help/menu/initial/style/assets/background.png"
        )

        
        self.color_replacements_map = {
            
            
            
        }

        
        self.header_font_size = 35
        self.base_font_size = 22
        self.command_font_size = 13

        
        self.header_font_color = "white"
        self.base_font_color = "black"
        self.command_font_color = "white"

        
        self.character_scale = 0.4

        
        self.text1 = self._truncate_text(
            f"{ctx.me.display_name} Help", 350
        )  
        self.text2_options = [
            "how can I help you today?",
            "need help with something?",
            "what can I do for you?",
            "how may I assist you?",
        ]
        self.text2 = f"Hello {self.user_name}, {random.choice(self.text2_options)}"
        self.text3 = "Command: [option]?"

        
        self.character_pos = (5, 5)
        self.text_x_offset = 10
        self.text_y_offset = 25
        self.text_spacing = 20

        self.command_text_margin = 40
        self.command_text_bottom_margin = 30

        
        self._load_resources()

    def _truncate_text(self, text, max_width):
        """Truncate text to fit within the specified width."""
        draw = ImageDraw.Draw(
            Image.new("RGBA", (1, 1))
        )  
        font = ImageFont.truetype(
            self.font_path_header, self.header_font_size
        )  

        
        while draw.textbbox((0, 0), text, font=font)[2] > max_width:
            text = text[:-1]  
            if len(text) == 0:  
                break
        return text

    def _load_resources(self):
        """Load the fonts and images required for generating the help menu image."""
        self.font = ImageFont.truetype(
            self.font_path_header, self.header_font_size)
        self.base_font = ImageFont.truetype(
            self.font_path_base, self.base_font_size)
        self.command_font = ImageFont.truetype(
            self.font_path_base, self.command_font_size
        )
        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")

        
        if self.color_replacements_map:
            self._apply_color_replacements()

        self._resize_character()

    @staticmethod
    def _download_image(url):
        """Download an image from a URL and return it as a PIL Image."""
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    def _apply_color_replacements(self):
        """Replace specific colors in the background image with colors from replacement images, solid colors, or transparency."""
        bg_array = np.array(self.background)

        for old_hex, replacement in self.color_replacements_map.items():
            old_color = tuple(int(old_hex[i: i + 2], 16) for i in (0, 2, 4))
            if replacement == "transparent":  
                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                
                bg_array[mask > 0] = [0, 0, 0, 0]
            elif replacement.startswith("http"):  
                replacement_img = self._download_image(replacement)
                replacement_img = replacement_img.resize(
                    (self.background.width, self.background.height)
                )
                replacement_array = np.array(replacement_img)[:, :, :3]

                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                bg_array[mask > 0, :3] = replacement_array[mask > 0]
            else:  
                replacement_color = tuple(
                    int(replacement[i: i + 2], 16) for i in (1, 3, 5)
                )
                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                bg_array[mask > 0, :3] = replacement_color

        self.background = Image.fromarray(bg_array, "RGBA")

    def _resize_character(self):
        """Resize the character image to a percentage of its original size."""
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height))

    def _draw_text(self, draw, text_x, text_y):
        """Draw all text on the image."""
        draw.text(
            (text_x, text_y), self.text1, font=self.font, fill=self.header_font_color
        )
        text_y += self.font.size + self.text_spacing
        draw.text(
            (text_x, text_y), self.text2, font=self.base_font, fill=self.base_font_color
        )
        text_y += self.base_font.size + self.text_spacing

        textbbox = draw.textbbox((0, 0), self.text3, font=self.command_font)
        w, h = textbbox[2] - textbbox[0], textbbox[3] - textbbox[1]
        draw.text(
            (
                self.background.width - w - self.command_text_margin,
                self.background.height - h - self.command_text_bottom_margin,
            ),
            self.text3,
            font=self.command_font,
            fill=self.command_font_color,
        )

    def create_image(self):
        """Generate the complete image with the background, character, and text."""
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)

        
        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        
        text_x = self.character.width + self.text_x_offset
        text_y = self.text_y_offset
        self._draw_text(draw, text_x, text_y)

        return bg

    def save_image(self, file_path):
        """Save the generated image to the given file path."""
        img = self.create_image()
        img.save(file_path)
        return file_path

    def show_image(self):
        """Display the generated image within the notebook (for Jupyter environments)."""
        img = self.create_image()
        img_bytes = BytesIO()
        img.save(img_bytes, format="PNG")
        display(IPImage(img_bytes.getvalue()))


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cog_commands = {}
        self.command_mapping_file = "Data/commands/help/command_map.json"

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.command_mapping_file), exist_ok=True)
        if not os.path.exists(self.command_mapping_file):
            with open(self.command_mapping_file, "w") as f:
                json.dump({}, f, indent=4)

    def _load_command_mapping(self):
        self._ensure_file_exists()
        with open(self.command_mapping_file, "r") as f:
            return json.load(f)

    def _save_command_mapping(self, mapping):
        with open(self.command_mapping_file, "w") as f:
            json.dump(mapping, f, indent=4)

    def _update_command_mapping(self):
        mapping = self._load_command_mapping()
        for cog_name in self.cog_commands.keys():
            if cog_name not in mapping:
                mapping[cog_name] = {}
            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [
                    cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cmd in cog_commands:
                    if cmd.name not in mapping[cog_name]:
                        mapping[cog_name][cmd.name] = " "
        self._save_command_mapping(mapping)

    @staticmethod
    def format_cog_commands(cog_name, cog_commands, command_mapping):
        embed = discord.Embed(
            title=f"Commands for {cog_name}", color=primary_color_value
        )
        embed.description = (
            " "  
        )

        for cmd_name in cog_commands:
            cmd = command_mapping.get(cmd_name)
            if cmd is None:
                continue  

            if not hasattr(cmd, "clean_params"):
                continue  

            cmd_args = [
                (
                    f"[{param.name}]"
                    if param.default is not param.empty
                    else f"<{param.name}>"
                )
                for param in cmd.clean_params.values()
            ]
            args_str = " ".join(cmd_args)
            command_info = f"...{cmd.name} {args_str}"

            embed.add_field(
                name=cmd_name, value=f"```{command_info}```", inline=False)

        return embed

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        try:
            cog_commands = {}
            command_mapping = self._load_command_mapping()

            
            bot_avatar_url = str(self.bot.user.avatar.with_size(128))
            async with aiohttp.ClientSession() as session:
                async with session.get(bot_avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.reply("Failed to get bot avatar.")
                    data = await resp.read()
            avatar_image = Image.open(BytesIO(data))
            temp_image_dir = "Data/Images"
            temp_image_path = os.path.join(temp_image_dir, "bot_icon.png")
            os.makedirs(temp_image_dir, exist_ok=True)
            avatar_image.save(temp_image_path)
            primary_color_value = primary_color(temp_image_path)
        except Exception as e:
            logger.error(f"Error getting primary color: {e}")
            await ctx.reply(
                embed=await error_custom_embed(self.bot, ctx, e, title="Primary Color")
            )
            return

        if command_name:
            command = self.bot.get_command(command_name)
            if command:
                command_string = f"{command.qualified_name} {command.signature.replace('[', '<').replace(']', '>').replace('=None', '')}"
                usage = f"{ctx.prefix}{command_string}"
                help_embed = discord.Embed(
                    title=command.qualified_name,
                    color=primary_color_value,
                    description=f"> **{command.help}**",
                )
                help_embed.add_field(
                    name="Usage", value=f"```{usage}```", inline=True)
                await ctx.send(embed=help_embed)
            else:
                await ctx.send("Invalid command name. Please provide a valid command.")
        else:
            try:
                for cog_name, cog_object in self.bot.cogs.items():
                    if isinstance(cog_object, commands.Cog):
                        commands_in_cog = [
                            cmd for cmd in cog_object.get_commands() if not cmd.hidden
                        ]
                        if commands_in_cog:
                            cog_commands[cog_name] = commands_in_cog

                self.cog_commands = cog_commands
                self._update_command_mapping()

                
                image_generator = ImageGenerator(ctx=ctx)
                image_file_path = "Data/commands/help/set_image/image.png"
                image_generator.save_image(file_path=image_file_path)

                
                with open(image_file_path, "rb") as file:
                    help_embed = discord.Embed(
                        color=primary_color_value,
                        description=(
                            f"Use `{ctx.prefix}help <command>` to get more information about a specific command.\n\n"
                            f"- For more help, visit the [support server](https://discord.gg/9QTMkjsteF)."
                        ),
                    )

                    select_view = Select(
                        self.cog_commands, self.bot, primary_color_value
                    )
                    options = HelpMenu(
                        self.bot, primary_color_value, select_view)

                    help_embed.set_image(url="attachment://image.png")
                    await ctx.send(
                        embed=help_embed,
                        file=discord.File(file, "image.png"),
                        view=options,
                        reference=ctx.message,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )

                
                if os.path.exists(image_file_path):
                    os.remove(image_file_path)

            except Exception as e:
                logger.error(f"Error sending HelpMenu: {e}")
                await ctx.reply(
                    embed=await error_custom_embed(self.bot, ctx, e, title="Help")
                )
                return


def setup(bot):
    bot.add_cog(Help(bot))
