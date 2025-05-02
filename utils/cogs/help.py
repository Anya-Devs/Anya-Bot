 
import os
import traceback
import json
import inspect

import cv2
import numpy as np
import aiohttp
import random
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont


from Imports.discord_imports import *
from Data.const import *
from Imports.log_imports import logger


class Select(discord.ui.Select):
    def __init__(self, bot, primary_color, ctx):
        self.bot = bot
        self.primary_color = primary_color
        self.ctx = ctx
        self.module_to_cogs = self.map_modules_to_cogs()
        self.set_thumbnail_file = "Data/commands/help/help_embed_images.json"

        options = []
        for module, cogs in self.module_to_cogs.items():
            first_cog = cogs[0] if cogs else None
            cog_name = first_cog.qualified_name if first_cog else "unknown"
            emoji = Help_Select_Embed_Mapping.emojis.get(cog_name.lower())

            options.append(
                discord.SelectOption(
                    label=module.replace("_", " ").replace(".py", "").capitalize(),
                    value=module,
                    emoji=emoji
                )
            )

        if not options:
            options = [discord.SelectOption(label="No Modules Available", value="none")]

        super().__init__(placeholder="[Select a module]", max_values=1, min_values=1, options=options)

    def map_modules_to_cogs(self):
        module_map = {}
        for cog in self.bot.cogs.values():
            if any(not cmd.hidden for cmd in cog.get_commands()):
                module = inspect.getmodule(cog.__class__).__name__.split('.')[-1]
                module_map.setdefault(module, []).append(cog)
        return module_map

    def build_fields_for_module(self, module):
        cogs = self.module_to_cogs.get(module, [])
        fields = []

        for cog in cogs:
            cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
            if not cog_commands:
                continue

            command_lines = []
            for cmd in cog_commands:
                cmd_args = [
                    f"[{param.name}]" if param.default is not param.empty else f"<{param.name}>"
                    for param in cmd.clean_params.values()
                ]
                if len(cmd_args) > 3:
                    cmd_args = cmd_args[:3] + ['...']
                cmd_args_str = ' '.join(cmd_args)
                command_line = f"`{cmd.name}`"   #{self.ctx.prefix}{cmd.name} {cmd_args_str}".strip()
                command_lines.append(command_line)

            fields.append((cog.qualified_name, " ".join(command_lines)))

        return fields

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_module = self.values[0]
            if selected_module == "none":
                await interaction.response.send_message("No modules available.", ephemeral=True)
                return

            embed = discord.Embed(description="", color=self.primary_color)

            fields = self.build_fields_for_module(selected_module)
            if fields:
                for name, value in fields:
                    embed.add_field(name=name, value=value, inline=True)
            else:
                embed.description = "No visible commands found for this module."

            file = None
            first_cog = self.module_to_cogs[selected_module][0] if self.module_to_cogs[selected_module] else None
            cog_name = first_cog.qualified_name if first_cog else "unknown"

            help_embed_manager = Help_Thumbnails(self.set_thumbnail_file)
            thumbnail_url = help_embed_manager.get_image_url(cog_name)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

            image_generator = Options_ImageGenerator(cog_name)
            image_path = "Data/images/help_images/cog_image.png"
            saved_image_path = image_generator.save_image(image_path)

            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    file = discord.File(f, filename="cog_image.png")
                embed.set_image(url="attachment://cog_image.png")

            if file:
                await interaction.response.edit_message(embed=embed, attachments=[file])
            else:
                await interaction.response.edit_message(embed=embed)

        except Exception:
            traceback.print_exc()



class HelpMenu(discord.ui.View):
    def __init__(self, bot, primary_color, select_view,*, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.primary_color = primary_color
        cog_commands = {}  
        self.add_item(select_view)
        





class Options_ImageGenerator:
    def __init__(self, cog_name, image_width=800, image_height=800):
        self.font_path_header = "Data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        self.font_path_base = "Data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        self.character_path = "Data/commands/help/menu/initial/style/assets/character.png"
        self.background_path = "Data/commands/help/menu/initial/style/assets/background.png"

        self.character_scale = 0.4
        self.image_width = image_width
        self.image_height = image_height
        self.header_font_size = int(image_width * 0.04)
        self.base_font_size = int(image_width * 0.0199)

        self.header_font_color = "white"
        self.base_font_color = "black"

        self.cog_name = cog_name
        self.header_text = f"{cog_name.replace('_', ' ')}"

        self.text_wrap_max = image_width * (0.63)
        self.description_text = self._wrap_text(
            f"{Help_Select_Embed_Mapping.embeds[cog_name.lower()]['description'] or '...'}",
            max_width=self.text_wrap_max,
        )

        self.character_pos = (5, 5)
        self.text_x_offset = 10
        self.text_y_offset = 27
        self.text_spacing = 20

        self.color_replacements_map = {}
        self.min_font_size = 5  
        
        self._load_resources()
        self._apply_color_replacements()

    def _load_resources(self):
        self.header_font = ImageFont.truetype(self.font_path_header, self.header_font_size)
        self.base_font = ImageFont.truetype(self.font_path_base, self.base_font_size)
        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")
        self._resize_character()

    def _resize_character(self):
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height))

    def _apply_color_replacements(self):
        bg_array = np.array(self.background)
        for old_hex, replacement in self.color_replacements_map.items():
            old_color = tuple(int(old_hex[i:i + 2], 16) for i in (0, 2, 4))
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
                    int(replacement[i:i + 2], 16) for i in (1, 3, 5)
                )
                mask = cv2.inRange(
                    bg_array[:, :, :3],
                    np.array(old_color) - 10,
                    np.array(old_color) + 10,
                )
                bg_array[mask > 0, :3] = replacement_color

        self.background = Image.fromarray(bg_array, "RGBA")

    def _wrap_text(self, text, max_width):
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

    def adjust_font_size_for_text(self, text, max_width):
        """Adjust the font size dynamically to prevent overflow."""
        draw = ImageDraw.Draw(
            Image.new("RGBA", (1, 1))
        )
        font_size = self.base_font_size
        font = ImageFont.truetype(self.font_path_base, font_size)

        while True:
            # Wrap the text based on the current font size
            wrapped_text = self._wrap_text(text, max_width)
            # Check the width of the longest line
            lines = wrapped_text.split("\n")
            longest_line = max(lines, key=lambda line: draw.textbbox((0, 0), line, font=font)[2])
            if draw.textbbox((0, 0), longest_line, font=font)[2] <= max_width or font_size <= self.min_font_size:
                break
            font_size -= 1
            font = ImageFont.truetype(self.font_path_base, font_size)

        return font_size

    def _draw_text(self, draw, text_x, text_y):
        # Adjust base font size dynamically
        dynamic_font_size = self.adjust_font_size_for_text(self.description_text, self.text_wrap_max)
        dynamic_font = ImageFont.truetype(self.font_path_base, dynamic_font_size)

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
            font=dynamic_font,
            fill=self.base_font_color,
        )

    def calculate_image_height(self):
        text_lines = self.description_text.split("\n")
        text_height = len(text_lines) * (self.base_font.getbbox(text_lines[0])[3] + self.text_spacing)
        return text_height + 2 * self.text_y_offset

    def create_image(self):
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)

        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        text_x = self.character.width + self.text_x_offset
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


    
class ImageGenerator:
    def __init__(self, ctx):
        """Initialize the ImageGenerator with user-specific data and load resources."""
        self.user_name = ctx.author.display_name

        # Font Paths
        self.font_path_header = "Data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        self.font_path_base = "Data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        
        # Image Paths
        self.character_path = "Data/commands/help/menu/initial/style/assets/character.png"
        self.background_path = "Data/commands/help/menu/initial/style/assets/background.png"

        # Scaling factor for larger images
        self.scale_factor = 1.5  # Adjust as needed (1.5x original size)

        # Font Sizes (Scaled)
        self.header_font_size = int(35 * self.scale_factor)
        self.base_font_size = int(22 * self.scale_factor)
        self.command_font_size = int(13 * self.scale_factor)

        # Font Colors
        self.header_font_color = "white"
        self.base_font_color = "black"
        self.command_font_color = "white"

        # Character Scale
        self.character_scale = 0.6  # Increased for better proportion

        # Text
        self.text1 = self._truncate_text(f"{ctx.me.display_name} Help", 350 * self.scale_factor)
        self.text2_options = [
            "how can I help you today?",
            "need help with something?",
            "what can I do for you?",
            "how may I assist you?",
        ]
        self.text2 = f"Hello {self.user_name}, {random.choice(self.text2_options)}"
        self.text3 = "Command: [option]?"

        # Positions & Margins (Scaled)
        self.character_pos = (int(5 * self.scale_factor), int(5 * self.scale_factor))
        self.text_x_offset = int(10 * self.scale_factor)
        self.text_y_offset = int(25 * self.scale_factor)
        self.text_spacing = int(20 * self.scale_factor)
        self.command_text_margin = int(40 * self.scale_factor)
        self.command_text_bottom_margin = int(30 * self.scale_factor)

        self._load_resources()

    def _truncate_text(self, text, max_width):
        """Truncate text to fit within the specified width."""
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))  # Dummy image for text measurement
        font = ImageFont.truetype(self.font_path_header, self.header_font_size)

        while draw.textbbox((0, 0), text, font=font)[2] > max_width:
            text = text[:-1]  
            if len(text) == 0:  
                break
        return text

    def _load_resources(self):
        """Load the fonts and images required for generating the help menu image."""
        self.font = ImageFont.truetype(self.font_path_header, self.header_font_size)
        self.base_font = ImageFont.truetype(self.font_path_base, self.base_font_size)
        self.command_font = ImageFont.truetype(self.font_path_base, self.command_font_size)

        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")

        # Resize background
        new_bg_size = (int(self.background.width * self.scale_factor), int(self.background.height * self.scale_factor))
        self.background = self.background.resize(new_bg_size, Image.LANCZOS)

        # Resize character
        self._resize_character()

    def _resize_character(self):
        """Resize the character image proportionally."""
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height), Image.LANCZOS)

    def _draw_text(self, draw, text_x, text_y):
        """Draw all text on the image."""
        draw.text((text_x, text_y), self.text1, font=self.font, fill=self.header_font_color)
        text_y += self.font.size + self.text_spacing
        draw.text((text_x, text_y), self.text2, font=self.base_font, fill=self.base_font_color)
        text_y += self.base_font.size + self.text_spacing

        # Command Text (Bottom-Right)
        textbbox = draw.textbbox((0, 0), self.text3, font=self.command_font)
        w, h = textbbox[2] - textbbox[0], textbbox[3] - textbbox[1]
        draw.text(
            (self.background.width - w - self.command_text_margin, self.background.height - h - self.command_text_bottom_margin),
            self.text3,
            font=self.command_font,
            fill=self.command_font_color,
        )

    def create_image(self):
        """Generate the complete image with the background, character, and text."""
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)

        # Paste Character
        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        # Draw Text
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
        img.show()


class Help_Thumbnails:
    def __init__(self, json_file_path):
        self.json_file_path = json_file_path
        self.help_embed = self.load_images()

    def load_images(self):
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
        os.makedirs(os.path.dirname(self.json_file_path), exist_ok=True)
        with open(self.json_file_path, "w") as f:
            json.dump({"help_embed": self.help_embed}, f, indent=4)

    def update_image_url(self, cog_name, url):
        cog_name = cog_name.lower()
        if cog_name in self.help_embed:
            self.help_embed[cog_name]["thumbnail_url"] = url
            self.save_images()
            return f"Updated {cog_name} thumbnail URL successfully."
        else:
            return f"Cog '{cog_name}' not found."

    def get_image_url(self, cog_name):
        cog_name = cog_name.lower()
        return self.help_embed.get(cog_name, {}).get("thumbnail_url", None)





class Sub_Helper:
    def __init__(self, bot, prefix):
        self.bot = bot
        self.prefix = prefix
        self.help_json_path = "Data/commands/help/sub_helper.json"

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.help_json_path), exist_ok=True)
        if not os.path.exists(self.help_json_path):
            with open(self.help_json_path, "w") as f:
                json.dump({}, f, indent=4)

    def _load_help_json(self):
        self._ensure_file_exists()
        with open(self.help_json_path, "r") as f:
            return json.load(f)

    def _save_help_json(self, data):
        with open(self.help_json_path, "w") as f:
            json.dump(data, f, indent=4)

    def create_command_help_json(self):
        help_data = self._load_help_json()

        for cog in self.bot.cogs.values():
            if isinstance(cog, commands.Cog):
                for cmd in cog.get_commands():
                    if cmd.hidden or cmd.name in help_data:
                        continue  # Skip hidden or already-documented commands

                    help_data[cmd.name] = {
                        "aliases": cmd.aliases,
                        "description": cmd.help or "No description provided.",
                        "example": f"{{}}{cmd.name}",
                        "related_commands": "Provide related commands"
                    }

        self._save_help_json(help_data)

    def get_command_help_string(self, ctx, command_name: str) -> str:
        help_data = self._load_help_json()
        command = self.bot.get_command(command_name)

        if not command:
            return f"Command `{command_name}` not found."

        command_info = help_data.get(command.name, {})
        aliases = command_info.get("aliases", [])
        description = command_info.get("description", "No description provided.")
        example = command_info.get("example", "No example provided.")
        related = command_info.get("related_commands", "No related commands.")

        usage = f"{ctx.prefix}{command.qualified_name} {command.signature.replace('[', '<').replace(']', '>').replace('=None', '')}"

        return f"""```md
{usage}

# Aliases
{', '.join(aliases) if aliases else "No aliases available."}

# Description
{description}

# Example Command(s)
{example.format(*[self.prefix] * example.count('{}')) if '{}' in example else example}

# Related Command(s)
{related.format(*[self.prefix] * related.count('{}')) if '{}' in related else related}

> Remove brackets when typing commands
> <> = required arguments
> [] = optional arguments
```"""
