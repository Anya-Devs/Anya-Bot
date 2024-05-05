# Import necessary modules
import os
import traceback

import discord
from discord.ext import commands
import aiohttp
from PIL import Image
from io import BytesIO
from Data.const import primary_color, error_custom_embed, Help_Select_Embed_Mapping # Import primary_color function and error_custom_embed from Data.const
from Imports.log_imports import logger  # Import logger from Imports.log_imports




class Select(discord.ui.Select):
    def __init__(self, cog_commands, bot, primary_color):
        options = [
            discord.SelectOption(label=cog_name.replace('_', ' '), value=cog_name, emoji=Help_Select_Embed_Mapping.emojis.get(cog_name.lower()))
            for cog_name in cog_commands.keys()
        ]
        super().__init__(placeholder="Select a Category", max_values=1, min_values=1, options=options)
        self.cog_commands = cog_commands
        self.bot = bot
        self.page = 0  # Track the current page
        self.primary_color = primary_color

    async def callback(self, interaction: discord.Interaction):
        try:
            button: discord.ui.Button = interaction

            cog_name = self.values[0]
            cog_info = self.cog_commands.get(cog_name)
            me = button.guild.get_member(self.bot.user.id)
            color = self.primary_color
            self.cog_embed = discord.Embed(
                title=cog_name.replace('_', ' '),
                description=Help_Select_Embed_Mapping.embeds[cog_name]["description"] or '',
                color=color # Help_Select_Embed_Mapping.embeds[cog_name]["color"] or None
            )
            self.cog_embed.set_thumbnail(url=Help_Select_Embed_Mapping.embeds[cog_name]["thumbnail_url"])
            self.cog_embed.set_image(url=Help_Select_Embed_Mapping.embeds[cog_name]["image_url"])

            cog = self.bot.get_cog(cog_name)
            if cog:
                # Get visible commands in the cog
                cog_commands = [f'`{cmd.name}`' for cmd in cog.get_commands() if not cmd.hidden]
                # If there are visible commands, add a field to the embed
                if cog_commands:
                    cog_commands_str = '\n'.join(cog_commands)
                    self.cog_embed.add_field(
                        name=cog_name.replace('_', ' '),
                        value=f"{cog_commands_str}",
                        inline=False
                    )
                else:
                    logger.info(f"No visible commands found for cog: {cog_name}")
            else:
                logger.info(f"Cog not found: {cog_name}")

            help_menu = HelpMenu(self.bot, self.primary_color)

            await button.response.edit_message(embed=self.cog_embed, view=View_All(self.bot, self.primary_color))
            logger.info("Message edited successfully.")

        except Exception as e:
            traceback_str = traceback.format_exc()
            print(traceback_str)
            logger.debug(f"An error occurred: {traceback_str}")
            pass
        
class HelpMenu(discord.ui.View):
    def __init__(self, bot, primary_color, *, timeout=180):
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
                inline=False
            )
        # Fetch cogs and their subcommands dynamically
        for cog_name, cog_object in self.bot.cogs.items():
            if isinstance(cog_object, commands.Cog):
                subcommands = {cmd.name: cmd.help for cmd in cog_object.get_commands() if not cmd.hidden}
                if subcommands:
                    cog_commands[cog_name] = subcommands
        select_view = Select(cog_commands, self.bot, self.primary_color)
        # Send only the embed without the button
        self.embed = help_embed
        self.add_item(select_view)

class View_All(discord.ui.View):
    def __init__(self, bot, primary_color, *, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.primary_color = primary_color
        cog_commands = {}  # Dictionary to store commands for each cog
        # Create an embed to list non-cog commands with descriptions
        help_embed = discord.Embed(
            title="Commands",
            color=self.primary_color # You can customize the color
        )
        help_embed.set_image(url=self.bot.user.avatar.url)
        # Fetch only non-cog commands
        non_cog_commands = [cmd for cmd in self.bot.commands if not cmd.cog and not cmd.hidden]
        for command in non_cog_commands:
            help_embed.add_field(
                name=f'{command.qualified_name}',
                value=f"> **{command.help}**",
                inline=False
            )
        # Fetch cogs and their subcommands dynamically
        for cog_name, cog_object in self.bot.cogs.items():
            if isinstance(cog_object, commands.Cog):
                subcommands = {cmd.name: cmd.help for cmd in cog_object.get_commands() if not cmd.hidden}
                if subcommands:
                    cog_commands[cog_name] = subcommands
        select_view = Select(cog_commands, self.bot, self.primary_color)
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
                embed.add_field(name=f"{cog_name.replace('_', ' ')}", value=f"{cog_commands_str}", inline=False)
        # embed.set_footer(text="Prefix: ,[command name]")
        embed.set_thumbnail(url=self.bot.user.avatar.url)
        await interaction.response.edit_message(embed=embed, view=HelpMenu(self.bot, self.primary_color))

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
                help_embed.add_field(name=" ", value=f"> **{command.help}**", inline=False)
                help_embed.add_field(name="Usage", value=f"```{usage}```", inline=False)
                await ctx.send(embed=help_embed)
            else:
                await ctx.send("Invalid command name. Please provide a valid command.")
        else:
           try: 
            # Display the general help menu
            help_menu = HelpMenu(self.bot, primary_color_value)
            def get_cog_commands_count(cog):
                return len([cmd for cmd in cog.get_commands() if not cmd.hidden])
            me = ctx.guild.get_member(self.bot.user.id)
            embed = discord.Embed(color=primary_color_value)
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
                    embed.add_field(name=f"{cog_name.replace('_', ' ')}", value=f"{cog_commands_str}", inline=False)
            embed.set_thumbnail(url=self.bot.user.avatar)
            # embed.set_footer(text="Prefix: ,[command name]")
            await ctx.reply(embed=embed, view=help_menu)
            await ctx.defer()
           except Exception as e:
            # If there's an error getting the primary color, display an error message
            logger.error(f"Error sending HelpMenu: {e}")
            await ctx.reply(embed=await error_custom_embed(self.bot, ctx, e, title="HelpMenu"))
            return

def setup(bot):
    bot.add_cog(Help(bot))
