# Importing necessary modules
import logging
import os
import asyncio
import random
import colorlog
from discord.ext import commands
from Imports.log_imports import logger

# Define a class for the AvatarChanger cog
class AvatarChanger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.countdown = 200  # Initial countdown value in seconds
        self.emojis_folder = 'Data/Emojis'  # Path to the folder containing PNG files
        self.png_files = [f for f in os.listdir(self.emojis_folder) if f.endswith('.png')]
        self.png_weights = [1] * len(self.png_files)  # Equal weights for each PNG file

    # Method to change the bot's avatar
    async def change_avatar(self):
        try:
            if self.png_files:
                random_png = random.choices(self.png_files, weights=self.png_weights)[0]
                with open(os.path.join(self.emojis_folder, random_png), 'rb') as f:
                    avatar_data = f.read()
                await self.bot.user.edit(avatar=avatar_data)
                logger.info(f"Changed avatar to {random_png} - Countdown: {self.countdown} seconds left")
            else:
                logger.info("No PNG files found in the Emojis folder.")
        except Exception as e:
            logger.error(f"An error occurred while changing avatar: {e}")

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

# Setup function to add the AvatarChanger cog to the bot
def setup(bot):
    bot.add_cog(AvatarChanger(bot))
