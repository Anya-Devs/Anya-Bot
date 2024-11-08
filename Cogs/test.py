import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import textwrap
import requests
from io import BytesIO
import os

class DiscordMessageConfig:
    """Configuration for a simulated Discord-style message display."""
    def __init__(
        self,
        username="User",
        message="This is a test message to showcase how a Discord message would look like.",
        avatar_url=None,  # Optional: URL to avatar image
        timestamp="12:34 PM",
        sent=True  # True for sent messages, False for received
    ):
        self.username = username
        self.message = message
        self.avatar_url = avatar_url
        self.timestamp = timestamp
        self.canvas_width = 500
        self.padding = 10
        self.message_padding = 10
        self.background_color = (54, 57, 63)  # Discord dark theme background
        self.text_color = (255, 255, 255)  # White text for messages
        self.timestamp_color = (150, 150, 150)  # Gray for timestamp
        self.username_color = (88, 101, 242)  # Discord username color (light blue)
        self.avatar_size = (40, 40)  # Avatar size
        self.font_path = None  # Path to a TTF font file (optional)
        self.font_size = 16
        self.timestamp_font_size = 12
        self.username_font_size = 14

class DiscordMessageImage:
    """Generates an image resembling a Discord message based on the given configuration."""
    def __init__(self, config: DiscordMessageConfig):
        self.config = config
        self.font = self.load_font(self.config.font_size)
        self.timestamp_font = self.load_font(self.config.timestamp_font_size)
        self.username_font = self.load_font(self.config.username_font_size)

    def load_font(self, size):
        """Loads a TTF font or defaults to PIL's built-in font."""
        if self.config.font_path and os.path.exists(self.config.font_path):
            return ImageFont.truetype(self.config.font_path, size)
        else:
            return ImageFont.load_default()

    def fetch_avatar(self):
        """Fetches and resizes the avatar image from the given URL."""
        if not self.config.avatar_url:
            return None
        try:
            response = requests.get(self.config.avatar_url)
            avatar = Image.open(BytesIO(response.content)).convert("RGBA").resize(self.config.avatar_size)
            # Create a circular mask for the avatar to make it round
            mask = Image.new("L", self.config.avatar_size, 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, self.config.avatar_size[0], self.config.avatar_size[1]), fill=255)
            avatar.putalpha(mask)
            return avatar
        except Exception as e:
            print(f"Error fetching avatar: {e}")
            return None

    def create_image(self):
        """Creates an image that visually represents a Discord-style message."""
        avatar = self.fetch_avatar()
        
        # Create a temporary image to calculate message height
        temp_image = Image.new('RGB', (self.config.canvas_width, 1000), self.config.background_color)
        temp_draw = ImageDraw.Draw(temp_image)
        
        # Calculate wrapped text height
        wrapped_text = textwrap.fill(self.config.message, width=40)
        text_bbox = temp_draw.textbbox((0, 0), wrapped_text, font=self.font)
        text_height = text_bbox[3] - text_bbox[1]
        message_height = text_height + self.config.message_padding * 2
        total_height = max(self.config.avatar_size[1], message_height) + self.config.padding * 2

        # Create the final canvas
        canvas = Image.new('RGB', (self.config.canvas_width, total_height), self.config.background_color)
        draw = ImageDraw.Draw(canvas)

        # Paste avatar if available
        if avatar:
            canvas.paste(avatar, (self.config.padding, self.config.padding), avatar)

        # Draw the username in Discord-style blue and the timestamp to the right
        username_x = self.config.padding + self.config.avatar_size[0] + self.config.padding
        username_y = self.config.padding
        draw.text((username_x, username_y), self.config.username, font=self.username_font, fill=self.config.username_color)

        # Calculate width of username and timestamp for positioning
        username_width = draw.textbbox((0, 0), self.config.username, font=self.username_font)[2]
        timestamp_text = self.config.timestamp
        timestamp_width = draw.textbbox((0, 0), timestamp_text, font=self.timestamp_font)[2]

        # Position the timestamp to the right of the username
        timestamp_x = username_x + username_width + 10  # 10-pixel gap between username and timestamp
        draw.text((timestamp_x, username_y), timestamp_text, font=self.timestamp_font, fill=self.config.timestamp_color)

        # Draw the message text below the username and timestamp
        text_x = username_x
        text_y = username_y + self.config.username_font_size + 5  # Slight gap between username and message
        draw.multiline_text((text_x, text_y), wrapped_text, font=self.font, fill=self.config.text_color)

        return canvas


class MessageImageCog(commands.Cog):
    """Cog to generate and send a Discord-style message image."""
    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def test(self, ctx, *, text: str):
        """Simulates a Discord message by creating and sending an image."""
        # Create a DiscordMessageConfig object with the user's data
        config = DiscordMessageConfig(
            username=str(ctx.author),
            message=f"{text}",
            avatar_url=str(ctx.author.avatar),  # Corrected the access to avatar URL
            timestamp="Today at 12:34 PM"
        )
        
        # Create the Discord message image
        message_image = DiscordMessageImage(config)
        image = message_image.create_image()

        # Save the image as a file
        image.save("Data/test/message/discord_message.png")

        # Send the image file as a response
        await ctx.send(file=discord.File("Data/test/message/discord_message.png"))


# Setup function to add the cog to the bot
def setup(bot):
    bot.add_cog(MessageImageCog(bot))
