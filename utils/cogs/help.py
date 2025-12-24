 
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


class HelpMenu(discord.ui.View):
    def __init__(self, bot, select_view, ctx, cog_commands, embed_image_path, embed_color):
        super().__init__(timeout=None)
        self.bot = bot
        self.ctx = ctx

        # Keep only visible commands, including groups
        self.cog_commands = {
            k: [cmd for cmd in v if not cmd.hidden] 
            for k, v in cog_commands.items()
        }
        self.cog_commands = {k: v for k, v in self.cog_commands.items() if v}

        self.page = 0
        self.fields_per_page = 4
        self.select_view = select_view
        self.embed_image_path = embed_image_path
        self.embed_color = embed_color

        # Navigation buttons
        self.prev_button = discord.ui.Button(
            emoji="⬅️", style=discord.ButtonStyle.gray, custom_id=f"prev_{ctx.author.id}"
        )
        self.next_button = discord.ui.Button(
            emoji="➡️", style=discord.ButtonStyle.gray, custom_id=f"next_{ctx.author.id}"
        )
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        if select_view:
            self.add_item(select_view)
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

    async def interaction_check(self, interaction):
        return interaction.user == self.ctx.author

    def build_embed(self):
        embed = discord.Embed(color=self.embed_color)
        embed.set_image(url="attachment://image.png")

        start, end = self.page * self.fields_per_page, (self.page + 1) * self.fields_per_page
        items = list(self.cog_commands.items())[start:end]

        for cog_name, commands_list in items:
            all_cmds = [f"`{cmd.name}`" for cmd in commands_list]
            value = " ".join(all_cmds) if all_cmds else "No commands."
            embed.add_field(name=cog_name.replace("_", " "), value=value, inline=False)

        total_pages = max(1, (len(self.cog_commands) - 1) // self.fields_per_page + 1)
        embed.set_footer(
            text=f"Page {self.page+1}/{total_pages} | Use {self.ctx.prefix}help <command> for details."
        )
        return embed

    async def prev_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        max_page = max(0, (len(self.cog_commands) - 1) // self.fields_per_page)
        if self.page < max_page:
            self.page += 1
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def show_overview(self, interaction: discord.Interaction):
        try:
            img = ImageGenerator(ctx=self.ctx)
            img_path = "data/commands/help/set_image/image.png"
            img.save_image(file_path=img_path)
            file = discord.File(img_path, filename="image.png")
        except Exception as e:
            logger.error(f"Error regenerating overview image: {e}")
            file = None

        self.clear_items()
        if self.select_view:
            self.add_item(self.select_view)
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        embed = self.build_embed()
        if file:
            embed.set_image(url="attachment://image.png")

        await interaction.response.edit_message(embed=embed, attachments=[file] if file else [], view=self)



# ---------------- SELECT HELP ---------------- #

class Select_Help(discord.ui.Select):
    def __init__(self, bot, ctx, help_view=None):
        self.bot, self.ctx, self.help_view = bot, ctx, help_view
        self.primary_color = primary_color()
        self.placeholder_text = "Pick a module to explore commands…"
        self.image_path = "data/images/help_images/cog_image.png"
        self.thumbnail_file = "data/commands/help/thumbnails.json"
        self.module_to_cogs = self.map_modules_to_cogs()

        options = self.build_options() or [
            discord.SelectOption(label="Oops... No module available.", value="none")
        ]
        super().__init__(placeholder=self.placeholder_text, max_values=1, min_values=1, options=options)

    def map_modules_to_cogs(self):
        module_map = {}
        for cog in self.bot.cogs.values():
            if any(not cmd.hidden for cmd in cog.get_commands()):
                mod = inspect.getmodule(cog.__class__).__name__.split('.')[-1]
                module_map.setdefault(mod, []).append(cog)
        return module_map

    def build_options(self):
        opts = []
        for module, cogs in self.module_to_cogs.items():
            cog_name = cogs[0].qualified_name.lower() if cogs else "unknown"
            emoji = Help_Select_Embed_Mapping.emojis.get(cog_name)
            if not emoji:
                continue
            label = module.replace("_", " ").replace(".py", "").title()
            label = f"{label} Commands" if "Help" not in label else label
            opts.append(discord.SelectOption(label=label, value=module, emoji=emoji))
        return opts

    def build_fields_for_module(self, module):
        fields = []
        for cog in self.module_to_cogs.get(module, []):
            visible_cmds = [cmd for cmd in cog.get_commands() if not cmd.hidden]
            if not visible_cmds:
                continue

            commands_str = " ".join(f"`{cmd.name}`" for cmd in visible_cmds)

            inline = len(self.module_to_cogs[module]) == 1
            fields.append((cog.__class__.__name__.replace("_", " "), commands_str, inline))
        return fields

    async def callback(self, interaction: discord.Interaction):
        module = self.values[0]
        if module == "none":
            await interaction.response.send_message("No modules available.", ephemeral=True)
            return

        embed = discord.Embed(description="", color=self.primary_color)
        fields = self.build_fields_for_module(module)
        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value or "No commands.", inline=inline)
        else:
            embed.description = "No visible commands found for this module."

        filename = module.split('.')[0]
        thumbs = Help_Thumbnails(self.thumbnail_file)
        url = thumbs.get_image_url(filename)
        if url:
            embed.set_thumbnail(url=url)

        Options_ImageGenerator(filename).save_image(self.image_path)
        file = (
            discord.File(open(self.image_path, "rb"), filename="cog_image.png")
            if os.path.exists(self.image_path)
            else None
        )
        if file:
            embed.set_image(url="attachment://cog_image.png")

        self.help_view.clear_items()
        overview_btn = discord.ui.Button(label="Overview", style=discord.ButtonStyle.green)

        async def overview_callback(interaction_: discord.Interaction):
            await self.help_view.show_overview(interaction_)

        overview_btn.callback = overview_callback
        self.help_view.add_item(self)
        self.help_view.add_item(overview_btn)
        await interaction.response.edit_message(embed=embed, attachments=[file] if file else [], view=self.help_view)


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




 

# ═══════════════════════════════════════════════════════════════
# COMMAND HELP VIEW - Interactive UI for command details
# ═══════════════════════════════════════════════════════════════

class CommandHelpView(discord.ui.View):
    """Interactive help view with depth navigation for commands/subgroups"""
    
    def __init__(self, bot, ctx, command, command_info: dict, prefix: str, parent_command: str = None):
        super().__init__(timeout=120)
        self.bot = bot
        self.ctx = ctx
        self.command = command
        self.command_info = command_info
        self.prefix = prefix
        self.parent_command = parent_command
        self.primary_color = primary_color()
        
        self._setup_buttons()
    
    def _setup_buttons(self):
        """Setup navigation buttons based on command structure"""
        # Add subcommand dropdown if this is a group command
        if hasattr(self.command, 'commands') and self.command.commands:
            subcommands = [cmd for cmd in self.command.commands if not cmd.hidden]
            if subcommands:
                self.add_item(SubcommandSelect(self.bot, self.ctx, subcommands, self.prefix, self.command.qualified_name))
        
        # Add related commands buttons (max 3)
        related = self.command_info.get("related_commands", "")
        if related and related != "Provide related commands" and related != "No related commands.":
            related_cmds = [cmd.strip().replace(self.prefix, "").replace("{}", "") for cmd in related.split(",")][:3]
            for cmd_name in related_cmds:
                cmd_name = cmd_name.strip()
                if cmd_name and self.bot.get_command(cmd_name):
                    btn = discord.ui.Button(
                        label=cmd_name[:20],
                        style=discord.ButtonStyle.secondary,
                        emoji="🔗",
                        custom_id=f"related_{cmd_name}_{self.ctx.author.id}"
                    )
                    btn.callback = self._make_related_callback(cmd_name)
                    self.add_item(btn)
        
        # Back button if we came from a parent command
        if self.parent_command:
            back_btn = discord.ui.Button(
                label="Back",
                style=discord.ButtonStyle.gray,
                emoji="◀️",
                custom_id=f"back_{self.ctx.author.id}"
            )
            back_btn.callback = self._back_callback
            self.add_item(back_btn)
    
    def _make_related_callback(self, cmd_name: str):
        async def callback(interaction: discord.Interaction):
            if interaction.user != self.ctx.author:
                return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
            
            helper = Sub_Helper(self.bot, self.prefix)
            result = await helper.get_command_help_embed(self.ctx, cmd_name)
            if isinstance(result, tuple):
                embed, view = result
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.edit_message(content=result, embed=None, view=None)
        return callback
    
    async def _back_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        helper = Sub_Helper(self.bot, self.prefix)
        result = await helper.get_command_help_embed(self.ctx, self.parent_command)
        if isinstance(result, tuple):
            embed, view = result
            await interaction.response.edit_message(embed=embed, view=view)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user == self.ctx.author
    
    def build_embed(self) -> discord.Embed:
        """Build a modern, spread-out embed for command help"""
        cmd = self.command
        info = self.command_info
        
        # Get command info
        aliases = info.get("aliases", cmd.aliases if hasattr(cmd, 'aliases') else [])
        description = info.get("description", cmd.help or "No description provided.")
        example = info.get("example", f"{self.prefix}{cmd.qualified_name}")
        result = info.get("result", "")
        
        # Format usage with proper signature
        signature = cmd.signature.replace('[', '<').replace(']', '>').replace('=None', '') if hasattr(cmd, 'signature') else ""
        usage = f"{self.prefix}{cmd.qualified_name} {signature}".strip()
        
        # Build embed with website-inspired styling
        embed = discord.Embed(color=self.primary_color)
        
        # Header section
        embed.set_author(
            name=f"📖 Command: {cmd.qualified_name}",
            icon_url=self.bot.user.display_avatar.url if self.bot.user.avatar else None
        )
        
        # Usage section - prominent display
        embed.add_field(
            name="⌨️ Usage",
            value=f"```\n{usage}\n```",
            inline=False
        )
        
        # Aliases section
        if aliases:
            alias_str = " • ".join([f"`{a}`" for a in aliases])
            embed.add_field(
                name="Aliases",
                value=alias_str,
                inline=True
            )
        
        # Cooldown info if exists
        if hasattr(cmd, '_buckets') and cmd._buckets and cmd._buckets._cooldown:
            cooldown = cmd._buckets._cooldown
            embed.add_field(
                name="Cooldown",
                value=f"⏱️ - {cooldown.rate} use / {int(cooldown.per)}s",
                inline=True
            )
        
        # Description section - full width
        embed.add_field(
            name="Description",
            value=description[:1024],
            inline=False
        )
        
        # Example section
        if example and example != "No example provided.":
            formatted_example = example.format(*[self.prefix] * example.count('{}')) if '{}' in example else example
            embed.add_field(
                name="Example",
                value=f"```\n{formatted_example}\n```",
                inline=False
            )
        
        # Result section
        if result and result != "No result provided.":
            embed.add_field(
                name="Result",
                value=result[:1024],
                inline=False
            )
        
        # Subcommands section if group command
        if hasattr(cmd, 'commands') and cmd.commands:
            subcommands = [c for c in cmd.commands if not c.hidden]
            if subcommands:
                sub_list = " ".join([f"`{c.name}`" for c in subcommands[:15]])
                embed.add_field(
                    name=f"Subcommands ({len(subcommands)})",
                    value=sub_list + ("\n*Use dropdown to explore*" if len(subcommands) > 1 else ""),
                    inline=False
                )
        
        # Footer with helpful info
        embed.set_footer(
            text=f"<> = required • [] = optional • Use {self.prefix}help for all commands",
            icon_url=self.ctx.author.display_avatar.url
        )
        
        return embed


class SubcommandSelect(discord.ui.Select):
    """Dropdown to navigate subcommands"""
    
    def __init__(self, bot, ctx, subcommands, prefix: str, parent_name: str):
        self.bot = bot
        self.ctx = ctx
        self.prefix = prefix
        self.parent_name = parent_name
        
        options = []
        for cmd in subcommands[:25]:  # Discord limit
            desc = (cmd.help or "No description")[:100]
            options.append(discord.SelectOption(
                label=cmd.name,
                description=desc,
                value=cmd.qualified_name,
                emoji="▸"
            ))
        
        super().__init__(
            placeholder="🔍 Explore subcommands...",
            options=options,
            custom_id=f"subcmd_select_{ctx.author.id}"
        )
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        selected_cmd = self.values[0]
        helper = Sub_Helper(self.bot, self.prefix)
        result = await helper.get_command_help_embed(self.ctx, selected_cmd, parent_command=self.parent_name)
        
        if isinstance(result, tuple):
            embed, view = result
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.edit_message(content=result, embed=None, view=None)


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
    
    def _find_command_info(self, help_data: dict, command_name: str) -> dict:
        """Find command info in help data, supporting nested subcommand keys"""
        # Check for direct qualified name match (e.g., "anime search")
        for cog_data in help_data.values():
            if isinstance(cog_data, dict):
                if command_name in cog_data:
                    return cog_data[command_name]
                # Check subcommands key
                for cmd_key, cmd_data in cog_data.items():
                    if isinstance(cmd_data, dict):
                        subcommands = cmd_data.get("subcommands", {})
                        if isinstance(subcommands, dict):
                            # Check if the subcommand name matches
                            sub_name = command_name.split()[-1] if " " in command_name else command_name
                            if sub_name in subcommands:
                                return subcommands[sub_name]
        return {}
    
    async def get_command_help_embed(self, ctx, command_name: str, parent_command: str = None):
        """Get command help as an embed with interactive view"""
        help_data = self._load_help_json()
        command = self.bot.get_command(command_name)
        
        if not command:
            return f"Command `{command_name}` not found."
        
        # Find command info - check multiple locations
        command_info = self._find_command_info(help_data, command.qualified_name)
        if not command_info:
            command_info = self._find_command_info(help_data, command.name)
        if not command_info:
            # Fallback to basic info from command itself
            command_info = {
                "aliases": command.aliases if hasattr(command, 'aliases') else [],
                "description": command.help or "No description provided.",
                "example": f"{self.prefix}{command.qualified_name}",
            }
        
        view = CommandHelpView(self.bot, ctx, command, command_info, self.prefix, parent_command)
        embed = view.build_embed()
        
        return embed, view

    def get_command_help_string(self, ctx, command_name: str) -> str:
        """Legacy method - returns markdown string for backwards compatibility"""
        help_data = self._load_help_json()
        command = self.bot.get_command(command_name)

        if not command:
            return f"Command `{command_name}` not found."

        command_info = self._find_command_info(help_data, command.qualified_name)
        if not command_info:
            command_info = self._find_command_info(help_data, command.name)

        aliases = command_info.get("aliases", [])
        description = command_info.get("description", "No description provided.")
        example = command_info.get("example", "No example provided.")
        related = command_info.get("related_commands", "No related commands.")
        result = command_info.get("result", "No result provided.")

        usage = f"{ctx.prefix}{command.qualified_name} {command.signature.replace('[', '<').replace(']', '>').replace('=None', '')}"

        return f"""```md
{usage}

# Aliases
{', '.join(aliases) if aliases else "No aliases available."}

# Description
{description}

# Example Command(s)
{example.format(*[self.prefix] * example.count('{}')) if '{}' in example else example}

# Result
{result}

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
            
            
            
