# Standard Library Imports
import os
import traceback
import json
import io

import cv2
import numpy as np
import aiohttp
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageSequence

from Imports.discord_imports import * 
from Data.const import primary_color, error_custom_embed, Help_Select_Embed_Mapping, Help_Embed_Mapping, banner_url, get_banner_color
from Imports.log_imports import logger


import textwrap


class Select(discord.ui.Select):
    def __init__(self, cog_commands, bot, primary_color):
        options = [
            discord.SelectOption(label=cog_name.replace('_', ' '), value=cog_name, emoji=Help_Select_Embed_Mapping.emojis.get(cog_name.lower()))
            for cog_name in cog_commands.keys()
        ]
        if not options:
            options = [discord.SelectOption(label="No Categories Available", value="none")]
        super().__init__(placeholder="More Details...", max_values=1, min_values=1, options=options)
        self.cog_commands = cog_commands
        self.bot = bot
        self.page = 0  # Track the current page
        self.primary_color = primary_color
        self.command_mapping_file = 'Data/Help/command_map.json'

    def _ensure_file_exists(self):
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.command_mapping_file), exist_ok=True)
        # Ensure the file exists
        if not os.path.exists(self.command_mapping_file):
            with open(self.command_mapping_file, 'w') as f:
                json.dump({}, f, indent=4)

    def _load_command_mapping(self):
        self._ensure_file_exists()
        with open(self.command_mapping_file, 'r') as f:
            return json.load(f)

    def _save_command_mapping(self, mapping):
        with open(self.command_mapping_file, 'w') as f:
            json.dump(mapping, f, indent=4)

    def _update_command_mapping(self):
        mapping = self._load_command_mapping()
        for cog_name in self.cog_commands.keys():
            if cog_name not in mapping:
                mapping[cog_name] = {}
            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cmd in cog_commands:
                    if cmd.name not in mapping[cog_name]:
                        mapping[cog_name][cmd.name] = "Description to fill out"
        self._save_command_mapping(mapping)

   
    async def callback(self, interaction: discord.Interaction):
        try:
            self._update_command_mapping()

            cog_name = self.values[0]
            if cog_name == "none":
                await interaction.response.send_message("No categories available.", ephemeral=True)
                return

            cog_info = self.cog_commands.get(cog_name)
            color = self.primary_color
            emoji = Help_Select_Embed_Mapping.emojis.get(cog_name.lower())

            self.cog_embed1 = discord.Embed(
                title=f'Category - {emoji} {cog_name.replace("_", " ")}',
                description=f'{Help_Select_Embed_Mapping.embeds[cog_name.lower()]["description"] or ""}',
                color=color
            )
            self.cog_embed2 = discord.Embed(title=f'{emoji} {cog_name.replace("_", " ")}', description='', color=color)

            file = None
            if 'ai' in Help_Select_Embed_Mapping.embeds and cog_name.lower() == 'ai':
                file_path = 'Data/Images/Help_Thumbnails/ai.png'
                if os.path.exists(file_path):
                    file = discord.File(file_path, filename='thumbnail.png')
                    self.cog_embed2.set_thumbnail(url='attachment://thumbnail.png')
                else:
                    logger.error(f"Thumbnail file '{file_path}' not found.")
            else:
                self.cog_embed2.set_thumbnail(url=Help_Select_Embed_Mapping.embeds[cog_name.lower()]["thumbnail_url"])

            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                if cog_commands:
                    command_mapping = self._load_command_mapping().get(cog_name, {})
                    for cmd in cog_commands:
                        cmd_args = [
                            f"[{param.name}]" if param.default is not param.empty else f"<{param.name}>"
                            for param in cmd.clean_params.values()
                        ]
                        args_str = " ".join(cmd_args)
                        command_info = f"`...{cmd.name}`  {command_mapping.get(cmd.name, 'No description available')}"
                        
                        self.cog_embed2.add_field(
                            name='',
                            value=command_info,
                            inline=False
                        )
                else:
                    logger.info(f"No visible commands found for cog: {cog_name}")
            else:
                logger.info(f"Cog not found: {cog_name}")

            if file:
                await interaction.response.edit_message(embed=self.cog_embed2, attachments=[file])
            else:
                await interaction.response.edit_message(embed=self.cog_embed2, attachments=[])


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
        
        cog_commands = {}  # Dictionary to store commands for each cog
        self.add_item(select_view)
        # Send only the embed without the button


class ImageGenerator:
    def __init__(self, ctx, bot_avatar_url=None):
        """Initialize the ImageGenerator with user-specific data and load resources."""
        self.user_name = ctx.author.me.display_name
        self.bot_avatar_url = bot_avatar_url
        
        # Configurable values
        self.font_path_header = "Data/commands/help/menu/initial/style/assets/font/valentine.ttf"
        self.font_path_base = "Data/commands/help/menu/initial/style/assets/font/dizhitl-italic.ttf"
        self.character_path = "Data/commands/help/menu/initial/style/assets/character.png"
        self.background_path = "Data/commands/help/menu/initial/style/assets/background.png"

        # Color replacements
        self.color_replacements = {
            'f9fbfa': 'https://preview.redd.it/tips-on-generating-pink-anime-aesthetic-environments-v0-iw2qlnedfa7c1.jpg?width=624&format=pjpg&auto=webp&s=0549deb99f066ecade9d21b80179f6b0af1056ac', 
            # 'f8a9a2': 'https://preview.redd.it/tips-on-generating-pink-anime-aesthetic-environments-v0-9i88qpedfa7c1.jpg?width=622&format=pjpg&auto=webp&s=e74ac4a77c02d57d12abda856be2991a46123885',  # Replace this color
        }
        
        self.color_replacements = self.color_replacements or {}
        
        # Font sizes
        self.header_font_size = 45
        self.base_font_size = 18
        self.command_font_size = 15

        # Font colors
        self.header_font_color = "white"
        self.base_font_color = "black"
        self.command_font_color = "white"

        # Character image scale
        self.character_scale = 0.4

        # Text content
        self.text1 = self._truncate_text(f"Hey {self.user_name}", 350)  # Truncate user_name if needed
        # List of possible texts for self.text2
        self.text2_options = [
            "What would you like assistance with?",
            "How can I help you today?",
            "Need help with something?",
            "What can I do for you?",
            "How may I assist you?"
        ]
        
        # Randomly select a text for self.text2
        self.text2 = random.choice(self.text2_options)
 
        self.text3 = "Command: [option]?"

        # Layout positions
        self.character_pos = (5, 5)
        self.text_x_offset = 20
        self.text_y_offset = 22
        self.text_spacing = 20

        self.command_text_margin = 40
        self.command_text_bottom_margin = 30

        # Bot avatar settings
        self.avatar_size = (100, 100)
        self.avatar_pos = (550,10)
        
        # Load fonts and images
        self._load_resources()

    def _truncate_text(self, text, max_width):
        """Truncate text to fit within the specified width."""
        draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))  # Dummy image to get draw object
        font = ImageFont.truetype(self.font_path_header, self.header_font_size)  # Use header font size

        # Check if text fits within the specified width
        while draw.textbbox((0, 0), text, font=font)[2] > max_width:
            text = text[:-1]  # Remove the last character
            if len(text) == 0:  # Ensure there's some text
                break
        return text

    def _load_resources(self):
        """Load the fonts and images required for generating the help menu image."""
        self.font = ImageFont.truetype(self.font_path_header, self.header_font_size)
        self.base_font = ImageFont.truetype(self.font_path_base, self.base_font_size)
        self.command_font = ImageFont.truetype(self.font_path_base, self.command_font_size)
        self.character = Image.open(self.character_path).convert("RGBA")
        self.background = Image.open(self.background_path).convert("RGBA")

        # Load and process bot avatar if URL is provided
        if self.bot_avatar_url:
            self.bot_avatar = self._download_and_process_avatar(self.bot_avatar_url)
        else:
            self.bot_avatar = None

        # Process color replacements
        if self.color_replacements:
            self._apply_color_replacements()

        self._resize_character()

    def _download_image(self, url):
        """Download an image from a URL and return it as a PIL Image."""
        response = requests.get(url)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))

    def _download_and_process_avatar(self, url):
        """Download, crop, and resize the bot avatar image."""
        avatar = self._download_image(url)
        avatar = avatar.resize((self.avatar_size[0] * 2, self.avatar_size[1] * 2))

        # Create a mask for the circular crop
        mask = Image.new('L', avatar.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, avatar.size[0], avatar.size[1]), fill=255)
        
        avatar.putalpha(mask)
        avatar = avatar.crop((0, 0, self.avatar_size[0] * 2, self.avatar_size[1] * 2))
        avatar = avatar.resize(self.avatar_size, Image.ANTIALIAS)
        
        return avatar

    def _apply_color_replacements(self):
        """Replace specific colors in the background image with colors from replacement images."""
        bg_array = np.array(self.background)

        for old_hex, replacement_url in self.color_replacements.items():
            replacement_img = self._download_image(replacement_url)
            replacement_img = replacement_img.resize((self.background.width, self.background.height))
            replacement_array = np.array(replacement_img)[:, :, :3]

            old_color = tuple(int(old_hex[i:i+2], 16) for i in (0, 2, 4))
            mask = cv2.inRange(bg_array[:, :, :3], np.array(old_color) - 10, np.array(old_color) + 10)
            bg_array[mask > 0, :3] = replacement_array[mask > 0]

        self.background = Image.fromarray(bg_array, 'RGBA')

    def _resize_character(self):
        """Resize the character image to a percentage of its original size."""
        new_width = round(self.character.width * self.character_scale)
        new_height = round(self.character.height * self.character_scale)
        self.character = self.character.resize((new_width, new_height))

    def _draw_text(self, draw, text_x, text_y):
        """Draw all text on the image."""
        draw.text((text_x, text_y), self.text1, font=self.font, fill=self.header_font_color)
        text_y += self.font.size + self.text_spacing
        draw.text((text_x, text_y), self.text2, font=self.base_font, fill=self.base_font_color)
        text_y += self.base_font.size + self.text_spacing

        textbbox = draw.textbbox((0, 0), self.text3, font=self.command_font)
        w, h = textbbox[2] - textbbox[0], textbbox[3] - textbbox[1]
        draw.text((self.background.width - w - self.command_text_margin, self.background.height - h - self.command_text_bottom_margin),
                  self.text3, font=self.command_font, fill=self.command_font_color)

    def create_image(self):
        """Generate the complete image with the background, character, and text."""
        bg = self.background.copy()
        draw = ImageDraw.Draw(bg)

        # Paste the character image onto the background
        character_x, character_y = self.character_pos
        bg.paste(self.character, (character_x, character_y), self.character)

        # Paste the bot avatar if available
        if self.bot_avatar:
            avatar_x, avatar_y = self.avatar_pos
            bg.paste(self.bot_avatar, (avatar_x, avatar_y), self.bot_avatar)

        # Draw all text onto the image
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
        img.save(img_bytes, format='PNG')
        display(IPImage(img_bytes.getvalue()))
        
        
        
        
        
        
        


  


    
    
    
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cog_commands = {}
        self.command_mapping_file = 'Data/Help/command_map.json'

    def _ensure_file_exists(self):
        os.makedirs(os.path.dirname(self.command_mapping_file), exist_ok=True)
        if not os.path.exists(self.command_mapping_file):
            with open(self.command_mapping_file, 'w') as f:
                json.dump({}, f, indent=4)

    def _load_command_mapping(self):
        self._ensure_file_exists()
        with open(self.command_mapping_file, 'r') as f:
            return json.load(f)

    def _save_command_mapping(self, mapping):
        with open(self.command_mapping_file, 'w') as f:
            json.dump(mapping, f, indent=4)

    def _update_command_mapping(self):
        mapping = self._load_command_mapping()
        for cog_name in self.cog_commands.keys():
            if cog_name not in mapping:
                mapping[cog_name] = {}
            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cmd in cog_commands:
                    if cmd.name not in mapping[cog_name]:
                        mapping[cog_name][cmd.name] = "Description to fill out"
        self._save_command_mapping(mapping)

    def format_cog_commands(self, cog_name, cog_commands, command_mapping):
        embed = discord.Embed(title=f"Commands for {cog_name}", color=primary_color_value)
        embed.description = ' '  # Add a placeholder description to ensure it's not empty

        for cmd_name in cog_commands:
            cmd = command_mapping.get(cmd_name)
            if cmd is None:
                continue  # Skip if command not found

            if not hasattr(cmd, 'clean_params'):
                continue  # Skip if cmd does not have clean_params

            cmd_args = [
                f"[{param.name}]" if param.default is not param.empty else f"<{param.name}>"
                for param in cmd.clean_params.values()
            ]
            args_str = " ".join(cmd_args)
            command_info = f"...{cmd.name} {args_str}"

            embed.add_field(name=cmd_name, value=f'```{command_info}```', inline=False)

        return embed

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        try:
            cog_commands = {}
            command_mapping = self._load_command_mapping()

            # Get the bot's avatar and primary color
            bot_avatar_url = str(self.bot.user.avatar.with_size(128))
            async with aiohttp.ClientSession() as session:
                async with session.get(bot_avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.reply('Failed to get bot avatar.')
                    data = await resp.read()
            avatar_image = Image.open(BytesIO(data))
            temp_image_dir = 'Data/Images'
            temp_image_path = os.path.join(temp_image_dir, 'bot_icon.png')
            os.makedirs(temp_image_dir, exist_ok=True)
            avatar_image.save(temp_image_path)
            primary_color_value = primary_color(temp_image_path)
        except Exception as e:
            logger.error(f"Error getting primary color: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Primary Color"))
            return

        if command_name:
            command = self.bot.get_command(command_name)
            if command:
                command_string = f"{command.qualified_name} {command.signature.replace('[', '<').replace(']', '>').replace('=None', '')}"
                usage = f"{ctx.prefix}{command_string}"
                help_embed = discord.Embed(
                    title=command.qualified_name,
                    color=primary_color_value,
                    description=f"> **{command.help}**"
                )
                help_embed.add_field(name="Usage", value=f"```{usage}```", inline=True)
                await ctx.send(embed=help_embed)
            else:
                await ctx.send("Invalid command name. Please provide a valid command.")
        else:
            try:
                for cog_name, cog_object in self.bot.cogs.items():
                    if isinstance(cog_object, commands.Cog):
                        commands_in_cog = [cmd for cmd in cog_object.get_commands() if not cmd.hidden]
                        if commands_in_cog:
                            cog_commands[cog_name] = commands_in_cog

                self.cog_commands = cog_commands
                self._update_command_mapping()

                # Create the image slideshow
                image_generator = ImageGenerator(
                    ctx=ctx,
                    user_name=ctx.author.display_name
                )
                image_file_path = 'Data/Help/image.png'
                image_generator.save_image(file_path=image_file_path)

                # Upload the image file to Discord
                with open(image_file_path, 'rb') as file:
                    help_embed = discord.Embed(
                        title=f"{ctx.me.display_name} Help",
                        color=primary_color_value,
                        description=(
                            f"Use `{ctx.prefix}help <command>` to get more information about a specific command.\n\n"
                            f"- For more help, visit the [support server](https://discord.gg/9QTMkjsteF)."
                        )
                    )
                    
                    select_view = Select(self.cog_commands, self.bot, primary_color_value)
                    options = HelpMenu(self.bot, primary_color_value, select_view)

                    help_embed.set_image(url='attachment://image.png')
                    await ctx.send(embed=help_embed, file=discord.File(file, 'image.png'), view=options, reference=ctx.message, allowed_mentions=discord.AllowedMentions.none())

                # Ensure file cleanup if necessary
                if os.path.exists(image_file_path):
                    os.remove(image_file_path)

            except Exception as e:
                logger.error(f"Error sending HelpMenu: {e}")
                await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Help"))
                return
            
            
            
            
def setup(bot):
    bot.add_cog(Help(bot))
