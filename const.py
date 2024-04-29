import platform
from datetime import datetime
import io
import traceback

import discord
from PIL import Image

class AnyaImages:
    shocked_anya = "https://img-03.stickers.cloud/packs/20d46227-dcb0-4583-8d66-ee78d4743129/webp/a65e28be-a5fd-4654-8e7d-736dbd809df2.webp"
    awake_anya = 'https://media.tenor.com/9kLYJilshNMAAAAe/spy-x-family-anya.png'
    question_anya= 'https://i.pinimg.com/236x/b7/23/1f/b7231fbf87eee22b6d1f35f83e9a80bd.jpg'

async def error_custom_embed(bot, ctx, e, title="Custom Error", thumbnail_url=AnyaImages.question_anya):
    # Create an error embed after catching the exception
    error_embed = discord.Embed(
        description=f'```bash\n{e}```',
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    error_embed.set_author(name=f'{bot.user.display_name.title()} - {title}', icon_url=bot.user.avatar)
    # Get the last traceback frame from the exception
    line_number = traceback.extract_tb(e.__traceback__)[-1].lineno
    tb_frame = traceback.extract_tb(e.__traceback__)[-1]
    file_location = tb_frame.filename  # File location

    print("Error found in line", line_number)
    error_embed.add_field(
        name=" ",
        value=f":warning: **Potential issue found:**\n- **File:** `{file_location}`\n- **Line:** `{line_number}`",
        inline=False
    )
    error_embed.set_footer(text='Error Found')
    error_embed.set_thumbnail(url=thumbnail_url)

    # Inform the user about the error
    await ctx.reply(embed=error_embed)

class Emojis:
    @staticmethod
    async def load(bot):
        print('Loading emojis from local files')
        cpu_emoji = await Emojis.create_emoji(bot, "Emojis/cpu.jpg")
        memory_emoji = await Emojis.create_emoji(bot, "Emojis/memory.png")
        python_emoji = await Emojis.create_emoji(bot, "Emojis/python.jpg")
        return cpu_emoji, memory_emoji, python_emoji

    @staticmethod
    async def create_emoji(bot, file_path):
            with open(file_path, "rb") as f:
                image = Image.open(f)
                img_byte_array = io.BytesIO()
                image.save(img_byte_array, format=image.format)
                img_byte_array.seek(0)
                print(f"Creating emoji from file: {file_path}")
                emoji = await bot.guild.create_custom_emoji(name=file_path.split("/")[-1].split(".")[0], image=img_byte_array.read())
                print(f"Emoji created successfully: {emoji.name}")
                return emoji
    

class LogConstants:
    """
    Constants related to logging.
    """
    # URL of the thumbnail image for the start log embed
    start_log_thumbnail = "https://example.com/start_log_thumbnail.png"
    
    # Footer details
    footer_text = "Please commit your changes to the repository."
    footer_icon = "https://example.com/footer_icon.png"
    
    # Author details
    author_name = "Your Bot Name"
    author_icon = "https://example.com/author_icon.png"

class PingConstants:
    """
    Constants related to the ping command.
    """
    # Thumbnail URL for the ping command
    thumbnail_url = 'https://example.com'

    # Image URL for the ping command
    image_url =  AnyaImages.awake_anya
    
    # Embed color
    embed_color = None
    
    # System information
    current_time = datetime.now().strftime("%I:%M:%S %p")  # Get current time
    system_info = {
        "Operating System": f"{platform.system()} {platform.release()}\n└── {platform.version()} ",
        "System Time": current_time,  # Format time as "I M P"
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
        "System Version": datetime.now().strftime("%I:%M:%S %p")  # Format system version as "I M P"
    }
    
    # Language information
    language_info = {
        "Language": "Python",
        "Discord Library": f"\ndiscord.py\n└── {discord.__version__}"
    }
    # Format i
    def format_diff(value):
        # Define thresholds for "bad" or "outdated" values
        cpu_threshold = 80  # CPU usage percentage threshold
        python_version_threshold = "3.7"  # Minimum required Python version

        # Check if value is bad or outdated and format accordingly
        if isinstance(value, str) and value < python_version_threshold:
            return f"- {value}\n"
        elif isinstance(value, (int, float)) and value > cpu_threshold:
            return f"- {value}\n"
        else:
            return f"+ {value}\n"
