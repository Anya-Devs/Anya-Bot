import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import textwrap
import requests
from io import BytesIO

class TestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def create_discord_message(self, username, message, avatar_url, timestamp="Today at 12:34 PM"):
        try:
            # Download avatar image
            response = requests.get(avatar_url)
            avatar = Image.open(BytesIO(response.content)).resize((40, 40))

            # Define fonts (using default system font)
            font_regular = ImageFont.load_default()
            font_bold = ImageFont.load_default()

            # Create a blank canvas
            canvas_width = 500
            canvas_height = 150  # Initial height, will expand if message is long
            background_color = (54, 57, 63)  # Discord background color
            canvas = Image.new('RGB', (canvas_width, canvas_height), background_color)
            draw = ImageDraw.Draw(canvas)

            # Draw avatar
            canvas.paste(avatar, (10, 10))

            # Draw username and timestamp
            username_color = (255, 255, 255)  # White color for username
            timestamp_color = (114, 118, 125)  # Grey color for timestamp
            draw.text((60, 10), username, font=font_bold, fill=username_color)
            draw.text((60 + draw.textbbox((60, 10), username, font=font_bold)[2] + 10, 10), timestamp, font=font_regular, fill=timestamp_color)

            # Wrap message text
            wrapped_text = textwrap.fill(message, width=60)
            text_start_y = 40
            text_bbox = draw.textbbox((60, text_start_y), wrapped_text, font=font_regular)
            draw.text((60, text_start_y), wrapped_text, font=font_regular, fill=(255, 255, 255))

            # Calculate text height
            text_height = text_bbox[3] - text_bbox[1]

            # Adjust canvas height based on text length
            new_height = text_start_y + text_height + 10
            if new_height > canvas_height:
                new_canvas = Image.new('RGB', (canvas_width, new_height), background_color)
                new_canvas.paste(canvas, (0, 0))
                canvas = new_canvas
                draw = ImageDraw.Draw(canvas)
                draw.text((60, text_start_y), wrapped_text, font=font_regular, fill=(255, 255, 255))

            # Save image
            canvas.save("discord_message.png")
        
        except Exception as e:
            # Handle any exceptions
            print(f"Error creating Discord message image: {e}")

    @commands.command(hidden=True)
    async def test(self, ctx):
        self.create_discord_message(
            username=str(ctx.author),
            message="This is a test message to showcase how a Discord message would look like. It wraps text properly.",
            avatar_url=str(ctx.author.avatar_url),
            timestamp="Today at 12:34 PM"
        )
        await ctx.send(file=discord.File("discord_message.png"))

async def setup(bot):
    await bot.add_cog(TestCog(bot))
