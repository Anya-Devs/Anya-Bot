import os
import random
import asyncio
import logging
from datetime import datetime, timezone, timedelta

# Third-Party Library Imports
import json
import numpy as np
import motor.motor_asyncio
from pymongo.errors import PyMongoError

from Imports.discord_imports import *
from Cogs.quest import Quest_Data, primary_color
from Data.const import error_custom_embed

# Configure the logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)


class Memo_Game(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.correct_emojis = {}  # Define correct_emojis as a dictionary

    @commands.command(name="memo")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def play_emoji_game(self, ctx):
        emojis = [
            "😀",
            "😊",
            "😂",
            "😍",
            "😎",
            "😢",
            "😠",
            "😱",
            "😡",
            "😐",
            "🥳",
            "😏",
            "🙃",
            "😇",
            "😅",
            "😜",
            "😌",
            "😋",
        ]
        shuffled_emojis = emojis * 2
        random.shuffle(shuffled_emojis)

        chosen_emoji = random.choice(emojis)

        # Store the correct emoji for this channel
        self.correct_emojis[ctx.channel.id] = chosen_emoji

        # Create an embed with the chosen emoji
        embed = discord.Embed(
            description=f"Remember this emoji: {chosen_emoji}", color=primary_color()
        )

        # Display the embed for a short duration before updating content
        message = await ctx.reply(embed=embed, mention_author=False)
        await asyncio.sleep(2)

        # Create an instance of Memo
        memo_view = Memo(ctx, shuffled_emojis, chosen_emoji, message, bot=self.bot)

        # Generate the timestamp for 10 seconds from now
        future_timestamp = int((datetime.utcnow() + timedelta(seconds=13)).timestamp())
        formatted_time = self.timestamp_gen(future_timestamp)
        embed = discord.Embed(
            description=f"React with the emoji you remembered.\n`Remaining Time:` {formatted_time}",
            color=primary_color(),
        )
        try:
            await message.edit(embed=embed, view=memo_view)
            await asyncio.sleep(10)  # Wait for 10 seconds
        except asyncio.TimeoutError:
            await message.edit(embed=self.timeout_embed(), view=None)

    def timeout_embed(self):
        return discord.Embed(
            title="Time's Up...",
            description="||```You didn't click the emoji in time.```||",
        )

    def timestamp_gen(self, timestamp: int) -> str:
        dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
        formatted_timestamp = f"<t:{int(dt.timestamp())}:R>"
        return formatted_timestamp


class Memo(discord.ui.View):
    def __init__(self, ctx, emojis, chosen_emoji, message, bot):
        self.timeout_duration = 10  # Timeout in seconds
        self.streak_increment = 1  # Streak increment for correct answers
        self.base_points = 5  # Base points for the first streak
        self.points_multiplier = 2  # Multiplier for points based on streak
        self.max_streak = (
            3  # Max streak allowed (this is different from emojis to remember)
        )
        self.max_emojis_to_remember = 3  # Default max emojis to remember (up to 3)
        self.user_points = {}

        # Now initialize the parent class
        super().__init__(timeout=self.timeout_duration)

        # Context and game setup
        self.ctx = ctx
        self.emojis = emojis
        self.chosen_emoji = chosen_emoji
        self.message = message
        self.bot = bot

        self.quest_data = Quest_Data(bot)
        self.memo_data = Memo_Data(bot)

        # Ensure emojis are a list
        if not isinstance(self.emojis, list):
            self.emojis = list(self.emojis)

        # Prepare random emojis for reactions
        reactions = random.sample(
            list(set(self.emojis) - {chosen_emoji}),
            min(len(set(self.emojis) - {chosen_emoji}), 4),
        )
        reactions.append(chosen_emoji)
        random.shuffle(reactions)

        # Add emoji buttons
        self.buttons = []
        for index, emoji in enumerate(reactions):
            custom_id = "correct_emoji" if emoji == chosen_emoji else f"emoji_{index}"
            button = discord.ui.Button(
                style=discord.ButtonStyle.gray, custom_id=custom_id, emoji=emoji
            )
            button.callback = self.on_button_click
            self.add_item(button)
            self.buttons.append(button)

        # Stop and Continue buttons
        self.stop_button = discord.ui.Button(
            style=discord.ButtonStyle.red, label="Stop", custom_id="stop_button"
        )
        self.stop_button.callback = self.on_stop_click

        self.continue_button = discord.ui.Button(
            style=discord.ButtonStyle.green,
            label="Continue",
            custom_id="continue_button",
        )
        self.continue_button.callback = self.on_continue_click

        # Setup the game asynchronously
        self.setup_task = asyncio.create_task(self.setup())

    async def setup(self):
        """Asynchronous setup for the Memo game."""
        self.max_emojis_to_remember = await self.calculate_emojis_to_remember()

    async def calculate_emojis_to_remember(self):
        """Calculate the number of emojis to remember based on the streak."""
        current_streak = await self.memo_data.get_streak(
            self.ctx.guild.id, self.ctx.author.id
        )
        if current_streak >= 20:
            return 3
        elif current_streak >= 10:
            return 2
        return 1

    async def on_button_click(self, interaction: discord.Interaction):
        super().__init__(timeout=None)
        user = interaction.user
        selected_button_id = interaction.data["custom_id"]

        if selected_button_id == "correct_emoji":
            # Correct emoji selected: update streak and points
            current_streak = await self.memo_data.get_streak(user.guild.id, user.id)
            new_streak = current_streak + self.streak_increment
            await self.memo_data.set_streak(user.guild.id, user.id, new_streak)

            # Calculate points
            points = (
                int(new_streak * self.points_multiplier)
                if new_streak > 1
                else self.base_points
            )
            self.user_points[user.id] = self.user_points.get(user.id, 0) + points
            await self.quest_data.add_balance(
                str(user.id), str(interaction.guild.id), points
            )

            # Update the embed and display correct answer using continue_game_embed
            balance = await self.quest_data.get_balance(
                str(user.id), str(interaction.guild.id)
            )  # Get the updated balance
            embed_correct = await MemoEmbeds.continue_game_embed(
                points, new_streak, balance, user, self.bot
            )

            # Update view
            self.clear_items()
            self.add_item(self.stop_button)
            self.add_item(self.continue_button)
            await interaction.response.edit_message(embed=embed_correct, view=self)

            # Mark button as green (indicating it was clicked)
            for button in self.buttons:
                if button.custom_id == selected_button_id:
                    button.style = discord.ButtonStyle.green  # Mark the button green
                    break
            await interaction.message.edit(view=self)

        else:
            # Incorrect answer: reset streak and points
            current_streak = await self.memo_data.get_streak(user.guild.id, user.id)
            await self.memo_data.set_streak(user.guild.id, user.id, 0)
            embed_incorrect = MemoEmbeds.incorrect_embed(current_streak)
            await interaction.response.edit_message(embed=embed_incorrect, view=None)

    async def on_stop_click(self, interaction: discord.Interaction):
        user = interaction.user

        # Only the author of the game can stop the game
        if user != self.ctx.author:
            await interaction.response.send_message(
                "Only the author of the game can stop the game!", ephemeral=True
            )
            return

        streak = await self.memo_data.get_streak(user.guild.id, user.id)
        highscore = await self.memo_data.get_user_highscore(
            user.guild.id, user.id
        )  # Fetch highscore
        avatar = str(user.avatar)

        embed_stop = await MemoEmbeds.stop_game_embed(streak, highscore, avatar)
        await interaction.response.edit_message(embed=embed_stop, view=None)

    async def on_continue_click(self, interaction: discord.Interaction):
        # Only the author of the game can continue the game
        user = interaction.user
        if user != self.ctx.author:
            await interaction.response.send_message(
                "Only the author of the game can continue the game!", ephemeral=True
            )
            return

        await interaction.response.defer()
        current_streak = await self.memo_data.get_streak(user.guild.id, user.id)

        # Handle points based on streak
        points = (
            int(current_streak * self.points_multiplier)
            if current_streak > 0
            else self.base_points
        )
        self.user_points[user.id] = self.user_points.get(user.id, 0) + points

        # Get balance asynchronously
        balance = await self.quest_data.get_balance(
            str(user.id), str(user.guild.id)
        )  # Get balance from quest_data

        # Randomly select a new emoji to remember
        new_chosen_emoji = random.choice(self.emojis)

        # Update the description with the new chosen emoji
        embed = await MemoEmbeds.blank_embed()
        embed.description = f"Remember this emoji: {new_chosen_emoji}"  # Set the description as requested

        formatted_time = self.ctx.cog.timestamp_gen(
            int(
                (
                    datetime.utcnow() + timedelta(seconds=self.timeout_duration)
                ).timestamp()
            )
        )
        embed.add_field(
            name="",
            value=f"React with the emoji you remembered {formatted_time}",
            inline=False,
        )

        # Create a new Memo view for the updated game state with the new emoji
        memo_view = Memo(
            self.ctx, self.emojis, new_chosen_emoji, self.message, self.ctx.bot
        )

        # Update the embed and view
        await self.message.edit(embed=embed, view=memo_view)

        # Clear the description after 1 second
        await asyncio.sleep(1)
        embed.description = " "
        await self.message.edit(embed=embed, view=memo_view)

    async def stop_game(self):
        """Stops the game and sends final results."""
        user = self.ctx.author
        streak = await self.memo_data.get_user_highscore(user.guild.id, user.id)

        # Ensure `stop_game_embed` is awaited and returns the embed
        embed_stop = await MemoEmbeds.stop_game_embed(streak, streak, user.avatar)

        # Add missing field if needed (like `formatted_time`)
        await self.message.edit(embed=embed_stop, view=None)

    # Timeout handler is automatically handled by discord.ui.View
    async def on_timeout(self):
        """Handle timeout logic: reset streak and points if no reaction."""
        current_streak = await self.memo_data.get_streak(
            self.ctx.guild.id, self.ctx.author.id
        )
        await self.memo_data.set_streak(
            self.ctx.guild.id, self.ctx.author.id, 0
        )  # Reset streak
        self.user_points[self.ctx.author.id] = 0  # Reset points
        embed_timeout = await MemoEmbeds.timeout_embed()
        await self.message.edit(embed=embed_timeout, view=None)


class Memo_Data(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.DB_NAME = "Memo"

        # Initialize MongoDB connection
        mongo_url = os.getenv("MONGO_URI")

        if not mongo_url:
            raise ValueError("No MONGO_URI found in environment variables")
        self.mongoConnect = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)

    async def get_user_highscore(self, guild_id, user_id):
        """Get the highscore for a user in a specific guild."""
        collection = self.mongoConnect[self.DB_NAME]["highscores"]
        try:
            user_data = await collection.find_one(
                {"guild_id": guild_id, "user_id": user_id}
            )
            return user_data["highscore"] if user_data else 0
        except PyMongoError as e:
            logger.error(
                f"Error retrieving highscore for user {user_id} in guild {guild_id}: {e}"
            )
            return 0

    async def set_user_highscore(self, guild_id, user_id, highscore):
        """Set the highscore for a user in a specific guild."""
        collection = self.mongoConnect[self.DB_NAME]["highscores"]
        try:
            await collection.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {"highscore": highscore}},
                upsert=True,
            )
        except PyMongoError as e:
            logger.error(
                f"Error setting highscore for user {user_id} in guild {guild_id}: {e}"
            )

    async def get_streak(self, guild_id, user_id):
        """Get the streak for a user in a specific guild."""
        collection = self.mongoConnect[self.DB_NAME]["streaks"]
        try:
            user_data = await collection.find_one(
                {"guild_id": guild_id, "user_id": user_id}
            )
            return user_data["streak"] if user_data else 0
        except PyMongoError as e:
            logger.error(
                f"Error retrieving streak for user {user_id} in guild {guild_id}: {e}"
            )
            return 0

    async def set_streak(self, guild_id, user_id, streak):
        """Set the streak for a user in a specific guild."""
        collection = self.mongoConnect[self.DB_NAME]["streaks"]
        try:
            await collection.update_one(
                {"guild_id": guild_id, "user_id": user_id},
                {"$set": {"streak": streak}},
                upsert=True,
            )
        except PyMongoError as e:
            logger.error(
                f"Error setting streak for user {user_id} in guild {guild_id}: {e}"
            )

    async def handle_error(self, interaction, error, title):
        """Handles errors and sends a custom embed."""
        await error_custom_embed(self.bot, interaction, str(error), title=title)

    async def validate_input(self, **kwargs):
        """Validates input values to ensure they are not None or empty."""
        for key, value in kwargs.items():
            if value is None or value == "":
                raise ValueError(f"{key} cannot be None or empty")

    async def update_user_data(self, user_id, points, set_time):
        # Update the user's data with the new points and set time
        user_data = await self.get_user_data(user_id)
        if user_data:
            user_data["points"] += points  # Add the points to the user's current total
            user_data["set_time"] = set_time  # Update the set time for the user
            await self.save_user_data(user_data)  # Save the updated data
        else:
            # If user data doesn't exist, create it
            user_data = {"points": points, "set_time": set_time}
            await self.save_user_data(user_data)


class MemoEmbeds:
    @staticmethod
    def correct_embed(points, streak):
        """Returns the embed for correct answers."""
        embed = discord.Embed(
            title="Correct!",
            description=f"You earned {points} points.",
            color=primary_color(),
        )
        embed.set_footer(text=f"Current Streak: {streak}")
        return embed

    @staticmethod
    def incorrect_embed(streak):
        """Returns the embed for incorrect answers."""
        embed = discord.Embed(
            title="Incorrect",
            description=f"Your streak has ended.\n```End Streak: {streak}```",
        )
        return embed

    @staticmethod
    async def stop_game_embed(streak, highscore, avatar):
        """Returns the embed when the game is stopped."""
        embed = discord.Embed(
            title="Game Stopped",
            description=(
                f"```Current Highscore: {streak}```"
                if streak > highscore
                else f"```New Highscore: {streak}```"
            ),
            color=primary_color(),
        )
        embed.set_thumbnail(url=avatar)
        return embed

    @staticmethod
    async def blank_embed():
        embed = discord.Embed(color=primary_color())
        return embed

    @staticmethod
    async def continue_game_embed(points, streak, balance, user, bot):
        """Returns the embed when the user chooses to continue."""
        embed = discord.Embed(color=primary_color())
        # Define emoji ids
        check_emoji_id = 1243403342722371645
        reward_emoji_id = 1247800150479339581

        reward_text = f"`{points} stp`"

        # Get emojis
        check_emoji = discord.utils.get(bot.emojis, id=check_emoji_id)
        reward_emoji = discord.utils.get(bot.emojis, id=reward_emoji_id)
        embed.add_field(
            name=f"Reward ", value=f"{reward_emoji} {reward_text}", inline=True
        )
        embed.add_field(name=f"Stella Points:", value=f"{balance:,}", inline=True)
        embed.set_footer(text=f"Current Streak: {streak}\tHighscore: Working on it...")
        embed.set_author(icon_url=user.avatar, name=f"{user.name}'s progess")
        return embed

    @staticmethod
    def new_round_embed(chosen_emoji):
        """Returns the embed for a new round."""
        embed = discord.Embed(
            description=f"Remember this emoji: {chosen_emoji}",
            color=primary_color(),  # Assuming you have this function defined
        )
        return embed

    @staticmethod
    async def timeout_embed():
        """Returns the embed for a timeout scenario."""
        embed = discord.Embed(
            title="Time's Up!",
            description="You took too long to respond. Your streak has been reset to `0`.",
        )
        embed.set_footer(text="Try again in the next round!")
        return embed


def setup(bot):
    bot.add_cog(Memo_Game(bot))
