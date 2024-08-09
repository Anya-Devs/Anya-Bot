# Import necessary modules
import os
import traceback
import json
import discord
from discord.ext import commands

import aiohttp
from PIL import Image
from io import BytesIO
from Data.const import primary_color, error_custom_embed, Help_Select_Embed_Mapping, Help_Embed_Mapping  # Import primary_color function and error_custom_embed from Data.const
from Imports.log_imports import logger  # Import logger from Imports.log_imports

class Select(discord.ui.Select):
    def __init__(self, cog_commands, bot, primary_color):
        options = [
            discord.SelectOption(label=cog_name.replace('_', ' '), value=cog_name, emoji=Help_Select_Embed_Mapping.emojis.get(cog_name.lower()))
            for cog_name in cog_commands.keys()
        ]
        if not options:
            options = [discord.SelectOption(label="No Categories Available", value="none")]
        super().__init__(placeholder="📚 Select a Category", max_values=1, min_values=1, options=options)
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
                title = f'Category - {emoji} {cog_name.replace("_", " ")}',
                description=f'{Help_Select_Embed_Mapping.embeds[cog_name.lower()]["description"] or ""}',
                color=color
            )
            self.cog_embed2 = discord.Embed(description=f'## {emoji} {cog_name.replace("_", " ")}', color=color)

            
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
                        command_info = f"`...{cmd.name}` - {command_mapping.get(cmd.name, 'No description available')}"
                        
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
                await interaction.response.edit_message(embed=self.cog_embed2 , attachments=[file])
            else:
                await interaction.response.edit_message(embed=self.cog_embed2, attachments=[])

            logger.info("Message edited successfully.")
        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            logger.debug(f"An error occurred: {traceback_str}")
            pass   
        
        
class HelpMenu(discord.ui.View):
    def __init__(self, bot, primary_color, select_view, *, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.primary_color = primary_color
        cog_commands = {}  # Dictionary to store commands for each cog
        # Create an embed to list non-cog commands with descriptions
        help_embed = discord.Embed(
            title="Commands",
            color=self.primary_color  # You can customize the color
        )
        help_embed.set_image(url=self.bot.user.avatar.url)
        # Fetch only non-cog commands
        non_cog_commands = [cmd for cmd in self.bot.commands if not cmd.cog and not cmd.hidden]
        for command in non_cog_commands:
            help_embed.add_field(
                name=f'{command.qualified_name}',
                value=f"> **{command.help}**",
                inline=True
            )
        # Fetch cogs and their subcommands dynamically
        for cog_name, cog_object in self.bot.cogs.items():
            if isinstance(cog_object, commands.Cog):
                subcommands = {cmd.name: cmd.help for cmd in cog_object.get_commands() if not cmd.hidden}
                if subcommands:
                    cog_commands[cog_name] = subcommands
        self.add_item(select_view)
        # Send only the embed without the button
        self.embed = help_embed


class View_All(discord.ui.View):
    def __init__(self, bot, primary_color, select_view, *, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.primary_color = primary_color
        cog_commands = {}  # Dictionary to store commands for each cog
        # Create an embed to list non-cog commands with descriptions
        help_embed = discord.Embed(
            title="Commands",
            color=self.primary_color  # You can customize the color
        )
        help_embed.set_image(url=self.bot.user.avatar.url)
        # Fetch only non-cog commands
        non_cog_commands = [cmd for cmd in self.bot.commands if not cmd.cog and not cmd.hidden]
        for command in non_cog_commands:
            help_embed.add_field(
                name=f'{command.qualified_name}',
                value=f"> **{command.help}**",
                inline=True
            )
        # Fetch cogs and their subcommands dynamically
        for cog_name, cog_object in self.bot.cogs.items():
            if isinstance(cog_object, commands.Cog):
                subcommands = {cmd.name: cmd.help for cmd in cog_object.get_commands() if not cmd.hidden}
                if subcommands:
                    cog_commands[cog_name] = subcommands
        self.add_item(select_view)

    @discord.ui.button(label="View All", style=discord.ButtonStyle.primary)
    async def sort_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        def get_cog_commands_count(cog):
            return len([cmd for cmd in cog.get_commands() if not cmd.hidden])
        me = button.guild.get_member(self.bot.user.id)
        embed = discord.Embed(color=self.primary_color)
        # Get all cogs
        cogs = [cog for cog in self.bot.cogs]
        # Sort cogs based on the number of commands
        sorted_cogs = sorted(cogs, key=lambda cog: get_cog_commands_count(self.bot.get_cog(cog)))
        # Iterate through sorted cogs and their commands
        for cog_name in sorted_cogs:
            cog = self.bot.get_cog(cog_name)
            cog_commands = [f"`{cmd.name}`" for cmd in cog.get_commands() if not cmd.hidden]
            if cog_commands:
                cog_commands_str = ' '.join(cog_commands)
                embed.add_field(name=f"{cog_name.replace('_', ' ')}", value=f"{cog_commands_str}", inline=True)
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await interaction.response.edit_message(embed=embed, view=HelpMenu(self.bot, self.primary_color, select_view=self))


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def help(self, ctx, command_name: str = None):
        try:
            cog_commands = {}  # Dictionary to store commands for each cog
            # Get the bot's icon
            bot_avatar_url = str(self.bot.user.avatar.with_size(128))
            async with aiohttp.ClientSession() as session:
                async with session.get(bot_avatar_url) as resp:
                    if resp.status != 200:
                        return await ctx.reply('Failed to get bot avatar.')
                    data = await resp.read()
            avatar_image = Image.open(BytesIO(data))
            # Save the bot's icon as a temporary image file
            temp_image_dir = 'Data/Images'
            temp_image_path = os.path.join(temp_image_dir, 'bot_icon.png')
            # Check if the directory exists, if not, create it
            if not os.path.exists(temp_image_dir):
                os.makedirs(temp_image_dir)
            avatar_image.save(temp_image_path)
            # Get the primary color of the bot's icon
            primary_color_value = primary_color(temp_image_path)
        except Exception as e:
            # If there's an error getting the primary color, display an error message
            logger.error(f"Error getting primary color: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="Primary Color"))
            return

        if command_name is not None:
            # Display help for a specific command
            command = self.bot.get_command(command_name)
            if command is not None:
                command_string = f"{command.qualified_name}  {command.signature.replace('[', '<').replace(']', '>').replace('=None', '')}"
                usage = f"{ctx.prefix}{command_string}"
                help_embed = discord.Embed(
                    title=command.qualified_name,
                    color=primary_color_value
                )
                help_embed.add_field(name=" ", value=f"> **{command.help}**", inline=True)
                help_embed.add_field(name="Usage", value=f"```{usage}```", inline=True)
                await ctx.send(embed=help_embed)
            else:
                await ctx.send("Invalid command name. Please provide a valid command.")
        else:
            try:
                # Display the general help menu
                for cog_name, cog_object in self.bot.cogs.items():
                    if isinstance(cog_object, commands.Cog):
                        subcommands = {cmd.name: cmd.help for cmd in cog_object.get_commands() if not cmd.hidden}
                        if subcommands:
                            cog_commands[cog_name] = subcommands
                
                # Create the first embed
                embed1 = discord.Embed(
                    title=Help_Embed_Mapping.embed1["title"] or '',
                    description=Help_Embed_Mapping.embed1["description"],
                    color=primary_color_value
                )
                embed1.set_thumbnail(url=Help_Embed_Mapping.embed1["thumbnail_url"])
                if Help_Embed_Mapping.embed1["image_url"]:
                    embed1.set_image(url=Help_Embed_Mapping.embed1["image_url"])
                
                # Create the second embed
                embed2 = discord.Embed(
                    title=Help_Embed_Mapping.embed2["title"] or '',
                    description=Help_Embed_Mapping.embed2["description"],
                    color=primary_color_value
                )
                # embed2.set_thumbnail(url=Help_Embed_Mapping.embed2["thumbnail_url"])
                if Help_Embed_Mapping.embed2["image_url"]:
                    embed2.set_image(url=Help_Embed_Mapping.embed2["image_url"])
                
                # Set up the help menu
                select_view = Select(cog_commands, self.bot, primary_color_value)
                help_menu = HelpMenu(self.bot, primary_color_value, select_view)
                
                await ctx.send(embed=embed1, view=help_menu)
                await ctx.defer()
            except Exception as e:
                # If there's an error sending the help menu, display an error message
                logger.error(f"Error sending HelpMenu: {e}")
                await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="HelpMenu"))
                return

def setup(bot):
    bot.add_cog(Help(bot))
