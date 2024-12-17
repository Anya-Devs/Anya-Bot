import os
import random
import asyncio
import discord
import requests
from PIL import Image
from io import BytesIO
from discord.ext import commands


from Data import const
from Imports.log_imports import logger

class Changer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.countdown = 900  # Initial countdown value in seconds
        self.emojis_folder = 'Data/Emojis'  # Path to the folder containing image files
        self.image_files = [f for f in os.listdir(self.emojis_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
        self.png_weights = [1] * len(self.image_files)  # Equal weights for each image file

    # Method to change the bot's avatar
    async def change_avatar(self, emoji_filename=None, image_data=None):
        try:
            if emoji_filename is not None and image_data is not None:
                # Save the new image
                with open(os.path.join(self.emojis_folder, emoji_filename), 'wb') as f:
                    f.write(image_data)
                # Update the list of image files
                self.image_files = [f for f in os.listdir(self.emojis_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))]
            elif self.image_files:
                # Choose a random image file
                random_image = random.choices(self.image_files, weights=self.png_weights)[0]
                with open(os.path.join(self.emojis_folder, random_image), 'rb') as f:
                    avatar_data = f.read()
                # Change the bot's avatar
                await self.bot.user.edit(avatar=avatar_data)
                logger.info(f"Changed avatar to {random_image} - Countdown: {self.countdown} seconds left")
                return True
            else:
                logger.info("No image files found in the Emojis folder.")
                return False
        except Exception as e:
            logger.error(f"An error occurred while changing avatar: {e}")
            return False

    # Listener for when the bot is ready
    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("AvatarChanger cog is ready. This cog periodically changes the bot's avatar.")
        await self.change_avatar_countdown()  # Start the countdown loop when bot is ready

    # Method to start the countdown loop
    async def change_avatar_countdown(self):
        while True:
            await self.change_avatar()
            await asyncio.sleep(self.countdown)  # Wait for {self.countdown} seconds between avatar changes

    @commands.command(name='avatar',hidden=True)
    @commands.is_owner()
    async def change_avatar_command(self, ctx, emoji_filename=None):
        embed = await const.EmbedFactory.change_avatar_prompt()
        await ctx.send(embed=embed)

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            user_response = await self.bot.wait_for('message', timeout=120, check=check)

            if user_response.content.lower() == 'c':
                await ctx.send("Operation cancelled.")
                return

            if user_response.attachments:
                attachment = user_response.attachments[0]
                image_data = await attachment.read()
                emoji_filename = attachment.filename

                if os.path.exists(os.path.join(self.emojis_folder, emoji_filename)):
                    await ctx.send(f"The file '{emoji_filename}' already exists. Do you want to override it? (yes/no)")
                    response = await self.bot.wait_for('message', timeout=120, check=check)

                    if response.content.lower() == 'no':
                        const.logger.info(f"User chose not to override the file '{emoji_filename}'.")
                        await ctx.send("Operation cancelled.")
                        return
                    else:
                        const.logger.info(f"User chose to override the file '{emoji_filename}'.")
                        pass

                if await self.change_avatar(emoji_filename, image_data):
                    embed = await const.EmbedFactory.failed_avatar_change()
                else:
                    embed = await const.EmbedFactory.successful_avatar_change(emoji_filename)
                
                await ctx.send(embed=embed)

            elif user_response.content.startswith("http"):
                image_url = user_response.content

                # Ask for the filename for the new image
                embed = discord.Embed(
                    title="Change Avatar",
                    description="Please provide a filename for the new image.\n\nType `c` to cancel.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)

                try:
                    user_response = await self.bot.wait_for('message', timeout=120, check=check)

                    if user_response.content.lower() == 'c':
                        await ctx.send("Operation cancelled.")
                        return

                    emoji_filename = user_response.content

                    # Download the image from the URL using Pillow
                    response = requests.get(image_url)
                    if response.status_code == 200:
                        with Image.open(BytesIO(response.content)) as img:
                            img.save(os.path.join(self.emojis_folder, emoji_filename))
                        await const.AvatarEmbeds.avatar_change_successful(ctx, emoji_filename)
                    else:
                        await ctx.send("Failed to download the image from the provided URL.")
                        const.logger.error(f"Failed to download the image from {image_url}")

                except asyncio.TimeoutError:
                    await ctx.send("Time's up. Operation cancelled.")
                    const.logger.info("Timeout occurred. Operation cancelled.")

        except asyncio.TimeoutError:
            await ctx.send("Time's up. Operation cancelled.")
            const.logger.info("Timeout occurred. Operation cancelled.")


def setup(bot):
    bot.add_cog(AvatarChanger(bot))
