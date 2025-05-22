 
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


from data.local.const import *
from imports.discord_imports import *
from imports.log_imports import logger



class Select_Help(discord.ui.Select):
    def __init__(self, bot, ctx):
        self.bot, self.ctx = bot, ctx
        self.primary_color = primary_color()
        self.placeholder_text = "[Select a module]"
        self.image_path = "data/images/help_images/cog_image.png"
        self.thumbnail_file = "data/commands/help/thumbnails.json"
        self.module_to_cogs = self.map_modules_to_cogs()
        options = self.build_options() or [discord.SelectOption(label="No Modules Available", value="none")]
        super().__init__(placeholder=self.placeholder_text, max_values=1, min_values=1, options=options)

    def map_modules_to_cogs(self):
        m = {}
        for cog in self.bot.cogs.values():
            if any(not cmd.hidden for cmd in cog.get_commands()):
                mod = inspect.getmodule(cog.__class__).__name__.split('.')[-1]
                m.setdefault(mod, []).append(cog)
        return m

    def build_options(self):
        opts = []
        for module, cogs in self.module_to_cogs.items():
            cog_name = cogs[0].qualified_name.lower() if cogs else "unknown"
            emoji = Help_Select_Embed_Mapping.emojis.get(cog_name)
            if not emoji:
                for cog in cogs:
                    e = Help_Select_Embed_Mapping.emojis.get(cog.qualified_name.lower())
                    if e:
                        emoji = e
                        break
            opts.append(discord.SelectOption(label=module.replace("_", " ").replace(".py", "").capitalize(), value=module, emoji=emoji))
        return opts

    def build_fields_for_module(self, module):
        return [(c.__class__.__name__, " ".join(f"`{cmd.name}`" for cmd in c.get_commands() if not cmd.hidden))
                for c in self.module_to_cogs.get(module, []) if any(not cmd.hidden for cmd in c.get_commands())]

    async def callback(self, interaction: discord.Interaction):
        try:
            module = self.values[0]
            if module == "none":
                await interaction.response.send_message("No modules available.", ephemeral=True)
                return
            embed = discord.Embed(description="", color=self.primary_color)
            fields = self.build_fields_for_module(module)
            if fields:
                for n, v in fields: embed.add_field(name=n, value=v, inline=True)
            else:
                embed.description = "No visible commands found for this module."
            filename = module.split('.')[0]
            cog = self.module_to_cogs.get(module, [None])[0]
            thumbs = Help_Thumbnails(self.thumbnail_file)
            url = thumbs.get_image_url(filename)
            if url: embed.set_thumbnail(url=url)
            Options_ImageGenerator(filename).save_image(self.image_path)
            file = discord.File(open(self.image_path, "rb"), filename="cog_image.png") if os.path.exists(self.image_path) else None
            if file: embed.set_image(url="attachment://cog_image.png")
            await interaction.response.edit_message(embed=embed, attachments=[file] if file else None)
        except: traceback.print_exc()






class HelpMenu(discord.ui.View):
    def __init__(self, bot, select_view,*, timeout=None):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.primary_color = primary_color()
        cog_commands = {}  
        self.add_item(select_view)
        
class Options_ImageGenerator:
    def __init__(self, cog_name, image_width=800, image_height=800):
        config_path = "data/commands/help/option_image.json"
        with open(config_path, "r") as f:
            config = json.load(f)

        self.font_path_header = config["font_path_header"]
        self.font_path_base = config["font_path_base"]
        self.character_path = config["character_path"]
        self.background_path = config["background_path"]
        self.character_scale = config["character_scale"]
        self.header_font_color = config["header_font_color"]
        self.base_font_color = config["base_font_color"]
        self.base_font_size = config["base_font_size"]
        self.min_font_size = config["min_font_size"]
        self.character_pos = tuple(config["character_pos"])
        self.text_x_offset = config["text_x_offset"]
        self.text_y_offset = config["text_y_offset"]
        self.text_spacing = config["text_spacing"]
        self.color_replacements_map = config["color_replacements_map"]

        self.image_width = image_width
        self.image_height = image_height
        self.header_font_size = int(image_width * 0.04)

        self.cog_name = cog_name
        self.header_text = f"{cog_name.replace('_', ' ').title()}"
        self.text_wrap_max = image_width * 0.63
        self.description_text = self._wrap_text(
            f"{Help_Select_Embed_Mapping.embeds[cog_name.lower()]['description'] or '...'}",
            max_width=self.text_wrap_max,
        )

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
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        font = ImageFont.truetype(self.font_path_base, self.base_font_size)
        for word in words:
            current_line.append(word)
            line_width = draw.textbbox((0, 0), " ".join(current_line), font=font)[2]
            if line_width > max_width:
                current_line.pop()
                lines.append(" ".join(current_line))
                current_line = [word]
        if current_line:
            lines.append(" ".join(current_line))
        return "\n".join(lines)

    def adjust_font_size_for_text(self, text, max_width):
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        font_size = self.base_font_size
        font = ImageFont.truetype(self.font_path_base, font_size)
        while True:
            wrapped_text = self._wrap_text(text, max_width)
            lines = wrapped_text.split("\n")
            longest_line = max(lines, key=lambda line: draw.textbbox((0, 0), line, font=font)[2])
            if draw.textbbox((0, 0), longest_line, font=font)[2] <= max_width or font_size <= self.min_font_size:
                break
            font_size -= 1
            font = ImageFont.truetype(self.font_path_base, font_size)
        return font_size

    def _draw_text(self, draw, text_x, text_y):
        dynamic_font_size = self.adjust_font_size_for_text(self.description_text, self.text_wrap_max)
        dynamic_font = ImageFont.truetype(self.font_path_base, dynamic_font_size)
        draw.text((text_x, text_y), self.header_text, font=self.header_font, fill=self.header_font_color)
        text_y += self.header_font.size + self.text_spacing
        draw.text((text_x, text_y), self.description_text, font=dynamic_font, fill=self.base_font_color)

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

        
        self.font_path_header = "data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        self.font_path_base = "data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        
        
        self.character_path = "data/commands/help/menu/initial/style/assets/character.png"
        self.background_path = "data/commands/help/menu/initial/style/assets/background.png"

        
        self.scale_factor = 1.5  

        
        self.header_font_size = int(35 * self.scale_factor)
        self.base_font_size = int(22 * self.scale_factor)
        self.command_font_size = int(13 * self.scale_factor)

        
        self.header_font_color = "white"
        self.base_font_color = "black"
        self.command_font_color = "white"

        
        self.character_scale = 0.6  

        
        self.text1 = self._truncate_text(f"{ctx.me.display_name} Help", 350 * self.scale_factor)
        self.text2_options = [
            "how can I help you today?",
            "need help with something?",
            "what can I do for you?",
            "how may I assist you?",
        ]
        self.text2 = f"Hello {self.user_name}, {random.choice(self.text2_options)}"
        self.text3 = "Command: [option]?"

        
        self.character_pos = (int(5 * self.scale_factor), int(5 * self.scale_factor))
        self.text_x_offset = int(10 * self.scale_factor)
        self.text_y_offset = int(25 * self.scale_factor)
        self.text_spacing = int(20 * self.scale_factor)
        self.command_text_margin = int(40 * self.scale_factor)
        self.command_text_bottom_margin = int(30 * self.scale_factor)

        self._load_resources()

    def _truncate_text(self, text, max_width):
        """Truncate text to fit within the specified width."""
        draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))  
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

        
        new_bg_size = (int(self.background.width * self.scale_factor), int(self.background.height * self.scale_factor))
        self.background = self.background.resize(new_bg_size, Image.LANCZOS)

        
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
        self.help_json_path = "data/commands/help/commands.json"

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
                cog_name = cog.__class__.__name__
                if cog_name not in help_data:
                    help_data[cog_name] = {}
                for cmd in cog.get_commands():
                    if cmd.hidden or cmd.name in help_data[cog_name]:
                        continue
                    help_data[cog_name][cmd.name] = {
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

        command_info = {}
        for cog_data in help_data.values():
            if command.name in cog_data:
                command_info = cog_data[command.name]
                break

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

    def check_and_fix_misplaced_commands(self):
        help_data = self._load_help_json()
        updated = False

        command_to_cog = {}
        for cog_name, cog in self.bot.cogs.items():
            for cmd in cog.get_commands():
                command_to_cog[cmd.name] = cog_name

        correct_structure = {cog_name: help_data.get(cog_name, {}) for cog_name in self.bot.cogs}

        for key in list(help_data.keys()):
            if key in self.bot.cogs:
                continue
            cmd_name = key
            cmd_data = help_data[key]
            if not isinstance(cmd_data, dict) or "description" not in cmd_data:
                continue
            correct_cog = command_to_cog.get(cmd_name)
            if correct_cog:
                if cmd_name not in correct_structure[correct_cog] or (
                    cmd_data.get("description", "").lower() != "no description provided."
                ):
                    correct_structure[correct_cog][cmd_name] = {
                        **correct_structure[correct_cog].get(cmd_name, {}),
                        **cmd_data
                    }
                    updated = True
                del help_data[key]

        for cog_name, commands in help_data.items():
            if cog_name not in self.bot.cogs:
                continue
            for cmd_name in list(commands.keys()):
                actual_cog = command_to_cog.get(cmd_name)
                if actual_cog and actual_cog != cog_name:
                    cmd_data = commands.pop(cmd_name)
                    correct_structure[actual_cog][cmd_name] = {
                        **correct_structure[actual_cog].get(cmd_name, {}),
                        **cmd_data
                    }
                    updated = True

        if updated:
            self._save_help_json(correct_structure)
            





class Help_Select_Embed_Mapping:
    images = AnyaImages.load_images()
    embed_data_path = "data/commands/help/embed-options.json"
    with open(embed_data_path, 'r', encoding='utf-8') as file:
        embed_options = json.load(file)

    embeds = {}
    emojis = {}

    for key, data in embed_options.items():
        embeds[key] = {
            "title": data["title"],
            "description": data["description"],
            "color": getattr(
                discord.Color,
                "red" if key in {"system", "pokemon"} else
                "green" if key == "ai" else
                "magenta" if key == "fun" else
                "blue" if key == "Cog2" else
                "default"
            )(),
            "thumbnail_url": images.get(f"help_{key}_thumbnail", ""),
            "image_url": images.get(f"help_{key}_thumbnail", "") if key == "system" else None
        }
        emoji = data.get("emoji")
        if emoji:
            emojis[key] = emoji  

    @classmethod
    def get_emoji(cls, cog_name: str):
        return cls.emojis.get(cog_name.lower())         
            