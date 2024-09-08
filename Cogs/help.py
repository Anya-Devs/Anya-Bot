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
    def __init__(self, bot, ctx, avatar_url, background_url, check_gif, font_path='Data/bubbles.ttf'):
        self.bot = bot
        self.avatar_url = avatar_url
        self.background_url = background_url
        self.check_gif = check_gif
        self.font_path = font_path
        self.avatar = self.load_image_from_url(self.avatar_url)
        self.background = self._load_background()
        self.avatar_size = (100, 100)  # Adjust as needed
        self.command_mapping_file = 'Data/Help/command_map.json'
        self.ctx = ctx

    def load_image_from_url(self, url):
        """Load an image from a URL."""
        response = requests.get(url)
        img = Image.open(BytesIO(response.content))
        return img

    def _load_background(self):
        """Load background image or create a solid color background."""
        if self.check_gif:
            # If check_gif is True, background_url is an image URL
            return self.load_image_from_url(self.background_url)
        else:
            # If check_gif is False, background_url is a color
            color = self.background_url  # Assuming it's a hex color code like '#FFFFFF'
            return Image.new('RGBA', (800, 600), color)  # Adjust size as needed

    def get_max_font_size(self, text, max_width, min_size=10, max_size=100):
        """Determine the maximum font size that fits the text within the specified width."""
        for size in range(max_size, min_size - 1, -1):
            font = ImageFont.truetype(self.font_path, size)
            text_bbox = ImageDraw.Draw(Image.new('RGBA', (1, 1))).textbbox((0, 0), text, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            if text_width <= max_width:
                return size
        return min_size

    def _ensure_file_exists(self):
        """Ensure the command mapping file exists."""
        os.makedirs(os.path.dirname(self.command_mapping_file), exist_ok=True)
        if not os.path.exists(self.command_mapping_file):
            with open(self.command_mapping_file, 'w') as f:
                json.dump({}, f, indent=4)

    def _load_command_mapping(self):
        """Load the command mappings from a JSON file."""
        self._ensure_file_exists()
        with open(self.command_mapping_file, 'r') as f:
            return json.load(f)

    def _save_command_mapping(self, mapping):
        """Save the command mappings to a JSON file."""
        with open(self.command_mapping_file, 'w') as f:
            json.dump(mapping, f, indent=4)

    def _update_command_mapping(self):
        """Update the command mappings with any new commands from the bot."""
        mapping = self._load_command_mapping()
        for cog_name in self.bot.cogs.keys():
            if cog_name not in mapping:
                mapping[cog_name] = {}
            cog = self.bot.get_cog(cog_name)
            if cog:
                cog_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                for cmd in cog_commands:
                    if cmd.name not in mapping[cog_name]:
                        mapping[cog_name][cmd.name] = "Description to fill out"
        self._save_command_mapping(mapping)

    def create_slideshow(self, output_path='slideshow.gif'):
        """Create a slideshow GIF with command details on individual frames."""
        frames = []
        command_mapping = self._load_command_mapping()

        # Get status text with user and command
        status_text = f"{self.ctx.author}, what would you like assistance with?"
        prefix_text = "prefix: ...<command>"

        # Loop through each cog and its commands
        for cog_name, commands in command_mapping.items():
            for cmd_name, cmd_desc in commands.items():
                # Prepare a new frame for each command
                frame = self.background.copy()
                if frame.mode != 'RGBA':
                    frame = frame.convert('RGBA')

                # Create a translucent black shader layer
                shader_layer = Image.new('RGBA', frame.size, (0, 0, 0, 0))
                shader_draw = ImageDraw.Draw(shader_layer)
                shader_color = (0, 0, 0, 100)  # Translucent black
                shader_draw.rectangle([(0, 0), (frame.width, frame.height)], fill=shader_color)
                frame = Image.alpha_composite(frame, shader_layer)

                # Position of the avatar (left of the text)
                avatar_position = (50, (frame.height - self.avatar_size[1]) // 2)

                # Text area width and position (beside the avatar)
                text_area_width = frame.width - self.avatar_size[0] - 100
                text = f"{self.ctx.author}, what would you like assistance with?\nCommand: ...{cmd_name}"
                font_size = self.get_max_font_size(text, text_area_width) 
                font = ImageFont.truetype(self.font_path, font_size)

                # Create a shader behind the text
                draw = ImageDraw.Draw(frame)
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_width = text_bbox[2] - text_bbox[0]
                text_height = text_bbox[3] - text_bbox[1]
                text_shader_width = text_width + 40  # Extra padding for visibility
                text_shader_height = text_height + 20
                text_shader_position = (avatar_position[0] + self.avatar_size[0] + 10 - 20, (frame.height - text_shader_height) // 2 - 10)  # Adjust for padding

                # Create shader layer for text background
                text_shader = Image.new('RGBA', (text_shader_width, text_shader_height), (0, 0, 0, 150))  # Black with semi-transparency
                frame.paste(text_shader, text_shader_position, text_shader)

                # Calculate text size and position
                text_position = (avatar_position[0] + self.avatar_size[0] + 30, (frame.height - text_height) // 2)  # 30 pixels padding between avatar and text

                # Paste the avatar onto the background with shader
                mask = self.avatar.split()[3]  # Ensuring the alpha mask is used
                frame.paste(self.avatar, avatar_position, mask)

                # Add styled text on top of the shader
                draw.text(text_position, text, font=font, fill=(255, 255, 255))  # White color for text

                # Append the frame to the slideshow
                frames.append(frame.copy())

        # Save the animated GIF
        frames[0].save(output_path, save_all=True, append_images=frames[1:], loop=0, duration=1000)  # 1000ms per frame

        return output_path
    
    
    
    
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
            user_avatar_url = str(ctx.author.avatar.with_size(128))
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
                
                approved_banner_gif = await banner_url(self.bot, ctx.author)
                
                if get_banner_gif:
                  background_url =  approved_banner_gif
                  check_gif = True
                else: 
                   
                   background_url = await get_banner_color(self.bot, ctx.author)
                   check_gif = False



                # Create the image slideshow
                image_generator = ImageGenerator(
                    bot=self.bot,
                    ctx=ctx,
                    avatar_url=user_avatar_url,
                    background_url=background_url
                    check_gif=check_gif
                )
                image_file_path = 'Data/Help/slideshow.gif'
                image_generator.create_slideshow(output_path=image_file_path)

                # Upload the GIF file to Discord
                with open(image_file_path, 'rb') as file:
                    help_embed = discord.Embed(
                        title=f"{ctx.me.display_name} Help",
                        color=primary_color_value,
                        description=(
                            f"Use `{ctx.prefix}help <command>` to get more information about a specific command.\n\n"
                            f"-# For more help, visit the [support server](https://discord.gg/9QTMkjsteF)."
                        )
                    )
                    
                    select_view = Select(self.cog_commands, self.bot, primary_color_value)
                    options = HelpMenu(self.bot, primary_color_value, select_view)
                    
                    
 

                    help_embed.set_image(url='attachment://help_slideshow.gif')
                    await ctx.send(embed=help_embed, file=discord.File(file, 'help_slideshow.gif'), view=options, reference=ctx.message, allowed_mentions=discord.AllowedMentions.none())

                # Ensure file cleanup if necessary
                if os.path.exists(image_file_path):
                    os.remove(image_file_path)

            except Exception as e:
                logger.error(f"Error sending HelpMenu: {e}")
                await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Help"))
                return

            
            
            
            
            
def setup(bot):
    bot.add_cog(Help(bot))
