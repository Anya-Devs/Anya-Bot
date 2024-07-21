# Imports
import os
import io
import json
import traceback
from datetime import datetime
from PIL import Image 
from openai import AsyncOpenAI  # Assuming AsyncOpenAI is the correct import from your module
from Imports.discord_imports import *
import platform
import random
import psutil

# Constants
class AnyaImages:
    shocked_anya = "https://img-03.stickers.cloud/packs/20d46227-dcb0-4583-8d66-ee78d4743129/webp/a65e28be-a5fd-4654-8e7d-736dbd809df2.webp"
    awake_anya = 'https://media.tenor.com/9kLYJilshNMAAAAe/spy-x-family-anya.png'
    question_anya = 'https://i.pinimg.com/236x/b7/23/1f/b7231fbf87eee22b6d1f35f83e9a80bd.jpg'
    select_quest = 'https://i.pinimg.com/474x/d9/af/95/d9af956f06d0de95689e2094f753aa2f.jpg' 
    select_ai = None
    start_shop_thumbnail = 'https://i.pinimg.com/564x/fd/1d/49/fd1d49d255ca18236a27a38b8710681b.jpg'
    ping_banner_anya = 'https://i.pinimg.com/564x/db/98/ff/db98ffc40d53378a9999528b69d66d00.jpg'
    ping_image = 'https://i.pinimg.com/564x/25/da/ee/25daee24ea5fb98b5590d542d2879708.jpg'
    sleepy_anya = 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR9y_MT3QHxXZVVzVlA94oFM8uIN0QH1fdw8Q6inySFmQ&s'
    new_mission_anya = 'https://i.pinimg.com/236x/b5/90/49/b590497e5e776909274ba40b040bba8c.jpg'
    look_radiant_anya = 'https://i.pinimg.com/236x/0b/cf/4b/0bcf4b9002db8cbb5f5d42855b5d460c.jpg'
    ping_thumbnail = 'https://i.pinimg.com/236x/5d/d7/d1/5dd7d1d91933d59b8f21732efba70368.jpg'
    help_thumbnail = 'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcQggKtOcHg_2xDGNeqtciU_-7iZ19F3lFbV091fGKq7KtJI5MuOzLBEPg2rQRZ9ru-tDGY&usqp=CAU'
    help_pokemon_thumbnail = 'https://pbs.twimg.com/media/FRaJipkWUAADmt-?format=jpg&name=4096x4096'
    quest_completed_anya = 'https://i.pinimg.com/236x/26/3b/90/263b90473c3651b4fc3d30b462152c0b.jpg'
    agree_to_terms_anya = 'https://i.pinimg.com/474x/09/47/bc/0947bc96fe6f6af4a9779d994c0a2df0.jpg'
    no_quest_anya = 'https://th.bing.com/th/id/OIP.iwQwh6xaDNpS2519HlwV8gHaKg?rs=1&pid=ImgDetMain' # 'https://i.pinimg.com/236x/38/b5/89/38b5893e071f60a9dbcc3074cbf70016.jpg' 
    show_quest_anya = 'https://i.pinimg.com/236x/23/2f/62/232f626bc0ec7a845198149fdc38e311.jpg'
    comfirmation_image_url = 'https://media.tenor.com/mWAIV_rO9FUAAAAe/happy-anime-girl-happy-anime.png'

# Embed Avatar
class EmbedFactory:
    @staticmethod
    async def change_avatar_prompt():
        embed = discord.Embed(
            title="Change Avatar",
            description="Please provide the image attachment or the URL to replace the avatar.\n\n"
                        "Type 'c' to cancel.",
            color=discord.Color.blue()
        )
        return embed

    @staticmethod
    async def successful_avatar_change(emoji_filename):
        embed = discord.Embed(
            title="Avatar Change Successful",
            description=f"The avatar has been successfully changed to `{emoji_filename}`.",
            color=discord.Color.green()
        )
        return embed

    @staticmethod
    async def failed_avatar_change():
        embed = discord.Embed(
            title="Avatar Change Failed",
            description=f"Failed to change the avatar.",
            color=discord.Color.red()
        )
        return embed

class Help_Embed_Mapping:
    embed = {
            "title": "Help Command",
            "description": "Need some help using certain commands?\n\n-# Take a look at the select options and choose the cog you need assistance with.",
            "thumbnail_url": AnyaImages.help_thumbnail,
            "image_url": "https://static1.cbrimages.com/wordpress/wp-content/uploads/2022/11/Spy-x-family-ep-18-Loid-and-Anyas-test-grades.jpg"
    }
    
class Help_Select_Embed_Mapping:
    embeds = {
       
        "system": {
            "title": "System",
            "description": "View the status of the bot, including information about its current performance, system resources usage, and configuration settings.",
            "color": discord.Color.red(),  # Customize color as needed
            "thumbnail_url": "https://i.pinimg.com/564x/f4/38/ef/f438ef92875df915c8d019780a76a346.jpg",
            "image_url": "https://i.pinimg.com/564x/f4/38/ef/f438ef92875df915c8d019780a76a346.jpg"
        },
        "quest": {
            "title": "Quest",
            "description": 'Participate in activities within your server, staying active with simple quests.',
            "color": None,  # Customize color as needed
            "thumbnail_url": AnyaImages.select_quest
        },
        "ai": {
            "title": "AI",
            "description": "Interact with advanced artificial intelligence functionalities, capable of handling various tasks including natural language processing, image recognition, and more.",
            "color": discord.Color.green(),  # Customize color as needed
            "thumbnail_url": AnyaImages.select_ai
        },
        
        "pokemon": {
            "title": "Pokemon",
            "description": "Learn the fandom of pokemon and explore the information related to pokemon and its fandom.\n-# Long live Pokemon Fandom",
            "color": discord.Color.red(),  # Customize color as needed
            "thumbnail_url": AnyaImages.help_pokemon_thumbnail
        },
        
        "Cog2": {
            "title": "Title for Cog2",
            "description": "Description for Cog2",
            "color": discord.Color.blue(),  # Customize color as needed
            "thumbnail_url": "Thumbnail URL for Cog2"
        },
        # Add more embed mappings for other cogs as needed
    }

    emojis = {
        "system": "<:system:1261208067085959320>", # "<:system_icon:1238536111266201610>",
        "quest": "<:anyasus:1258563706518765669> ",
        "ai": '<:ai:1258206841737973842> ',
        'pokemon': '<:Pokeball:1261208239891156992>',
        # Add more emoji mappings for other cogs as needed
    }

    
    
class TutorialMission:
    def __init__(self):
        self.steps = [
            {
                'action': 'send',
                'method': 'message',
                'content': 'Hello',
                'description': 'Welcome to the tutorial mission! Your first task is to say "Hello" in the server chat.',
                'times': 1
            },
            {
                'action': 'react',
                'method': 'reaction',
                'content': '👍',
                'description': 'React to this message with a thumbs up emoji.',
                'times': 1
            },
            {
                'description': 'Welcome them and tell them they have a new quest.'
            }
        ]    
    
QUEST_PROMPT_EMBED = {
    "title": None,
    "color": discord.Color.yellow(), # You can specify a color in hex format if needed
    "footer_text": "Quest Terms Agreement"
}

class Quest_Prompt:
    @staticmethod
    async def get_embed(bot):
        # terms_emoji = discord.utils.get(bot.emojis, id=1244193792400031835)
        fair_emoji = discord.utils.get(bot.emojis, id=1244196046565802015)
        tracking_emoji = discord.utils.get(bot.emojis, id=1244195699331960863)
        respect_emoji = discord.utils.get(bot.emojis, id=1244196427828301825)
                          
        print('getting embed')
        embed = discord.Embed(
            description=(
        f"**By accepting server quests, you agree to the following terms and conditions:**\n\n"
        f"- **{fair_emoji} Play fair:**\n"
        "> ```Do not use self-bots or any form of automation.```\n"
        f"- **{tracking_emoji} Voluntary tracking:**\n"
        "> ```Your messages may be tracked for quest purposes.```\n"
        f"- **{respect_emoji} Respect server admin:**\n"
        "> ```You may receive quests from the server admin.```\n"
    ),
            color=QUEST_PROMPT_EMBED["color"],
            timestamp = datetime.now()
        )
        # embed.set_thumbnail(url=AnyaImages.look_radiant_anya)
        embed.set_footer(text=QUEST_PROMPT_EMBED["footer_text"],icon_url=AnyaImages.look_radiant_anya)
        return embed
    
class Quest_Progress:
    # Dictionary to store progress bar mappings
    Progress_Bar_MAPPING = {
        "front_empty": 1237456749674364969,
        "front_full": 1237456617776218205,
        "mid_empty": 1237456613527523328,
        "mid_full": 1237456614697730139,
        "back_empty": 1237456616119599164,
        "back_full": 1237456619143696395
    }

    # Function to generate progress bar emojis
    @staticmethod
    async def generate_progress_bar(progress, bot):
        bar = ""
        for i in range(10):
            front_emoji = discord.utils.get(bot.emojis, id=Quest_Progress.Progress_Bar_MAPPING["front_full" if progress >= (i + 1) * 0.1 else "front_empty"]) or ":_:"
            mid_emoji = discord.utils.get(bot.emojis, id=Quest_Progress.Progress_Bar_MAPPING["mid_full" if progress >= (i + 1) * 0.1 else "mid_empty"]) or ":_:"
            bar += f"{front_emoji}{mid_emoji}" if i == 0 else f"{mid_emoji}"
        back_emoji = discord.utils.get(bot.emojis, id=Quest_Progress.Progress_Bar_MAPPING["back_full" if progress == 1 else "back_empty"]) or ":_:"
        bar += f"{back_emoji}"  # Back part emoji
        return bar

    
class QuestEmbed:
    @staticmethod
    async def create_quest_embed(
        bot: discord.Client,  # Add bot parameter
        quest: str,
        quest_id: int, 
        action: str, 
        method: str, 
        channel: discord.TextChannel, 
        times: int, 
        content: str,
        user: discord.User
    ) -> discord.Embed:
        # Construct a more readable description
        description = (
            f"**Quest ID:** `{quest_id}`\n"
            f"**Action:** `{action.title()}`\n"
            f"**Method:** `{method}`\n"
            f"**Channel:** {channel.mention}\n"
            f"**Times:** `{times}`\n"
            f"**Content:** `{content}`"
        )
        
        # Retrieve the emoji
        added_emoji = discord.utils.get(bot.emojis, id=1244440519514521600)
        
        # Create the embed
        embed = discord.Embed(
            # title=f"{added_emoji}  New Quest",
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        # Set the author using the user parameter
        embed.set_author(name=user.name, icon_url=user.avatar)
        
        # Set the footer and thumbnail
        embed.set_footer(text='Quest Created')
        embed.set_thumbnail(url=AnyaImages.new_mission_anya)
        
        return embed
    
    @staticmethod
    async def get_agree_confirmation_embed(bot,user):
        check_emoji_id = 1243403342722371645
        check_emoji = discord.utils.get(bot.emojis, id=check_emoji_id)

        confirmation_embed = discord.Embed(
            title=f"{check_emoji} Confirmation Complete",
            description=f"Do `...quest` to check server quest.",
            color=discord.Color.pink()
        )
        
        return confirmation_embed
    
    @staticmethod
    async def get_no_quest_embed():
        no_quest_embed = discord.Embed(
            title="No Quest Available",
            description="There are no quests available for you at the moment.",
        )
        no_quest_embed.set_thumbnail(url=AnyaImages.no_quest_anya)
        return no_quest_embed
   
    @staticmethod
    async def send_content_request(method):
        embed = discord.Embed(
            title=f"Content Request for {method.name}",
            description=(
                "Please provide the content for the quest. You can use the following variables in your content:\n\n"
                "**{new_member}**: Checks if the member joined within the last 7 days.\n"
                "**{old_member}**: Checks if the member joined more than 30 days ago.\n"
                "**{role <role_name>}**: Checks if the member has the specified role.\n"
                "**{unique_member}**: Ensures the member is unique for this quest."
            )
        )
        return embed
    
    @staticmethod
    async def show_quest(bot,ctx):
        help_emoji = discord.utils.get(bot.emojis, id=1245611790176616510)

        
        embed = discord.Embed(
            # description='{member}: Mention someone in your server (excluding bots and yourself)',
            timestamp=datetime.now())
        embed.set_footer(text='Server Quest\n',icon_url=AnyaImages.show_quest_anya)
        embed.set_author(name=f"{ctx.author.display_name} quests",icon_url=ctx.author.avatar)
        # embed.set_thumbnail(url=AnyaImages.show_quest_anya)
        return embed
            
class Quest_Completed_Embed:
    @staticmethod
    async def create_embed(bot, quest_content, channel_mention, times, user, quest_id, method=None, reward='N/A', balance=None):
        # Define emoji ids
        check_emoji_id = 1243403342722371645
        reward_emoji_id = 1247800150479339581

        # Get emojis
        check_emoji = discord.utils.get(bot.emojis, id=check_emoji_id)
        reward_emoji = discord.utils.get(bot.emojis, id=reward_emoji_id)
        # Text art
        amount = 'times' if times > 1 else 'time'

        quest_completed = f'-# {check_emoji} {user.mention} : {method.title()} "{quest_content.replace("`", "")}", {times} {amount}'

        reward_text = f'`{reward} stp`'
        
        # Create embed
        embed = discord.Embed(
            timestamp=datetime.now(),
            description = quest_completed,
            color=discord.Color.random()
        )

        
       

        # embed.add_field(name=f'{check_emoji} Completed', value=f'**You {quest_completed}!**', inline=True)
        
        embed.add_field(name=f'Reward ', value=f'{reward_emoji} {reward_text}', inline=True)
        embed.add_field(name=f'Balance', value=balance, inline=True)

        
        # Set thumbnail image
        embed.set_thumbnail(url=user.avatar)
        return embed
    
    
class ShopEmbed:
    @staticmethod
    async def start_shop_embed(bot, ctx, balance):
        embed = discord.Embed(title='Spy Shop')
        embed.description = f'```py\nBalance: {balance}```'  # f"*Remember these tools might make or break relshinships, so please be careful.*"
        embed.set_footer(text=f"Use the {bot.user.name}'s option menu to acquire your spy tool.")
        embed.set_thumbnail(url=AnyaImages.start_shop_thumbnail)
        return embed
    
class LogConstants:
    start_log_thumbnail = "https://example.com/start_log_thumbnail.png"
    footer_text = "Please commit your changes to the repository."
    footer_icon = "https://example.com/footer_icon.png"
    author_name = "Your Bot Name"
    author_icon = "https://example.com/author_icon.png"
    embed_color = None

class PingConstants:
    thumbnail_url = None # AnyaImages.ping_thumbnail
    image_url =  AnyaImages.ping_image
    footer_icon = None
    embed_color = None

    current_time = datetime.now().strftime("%I:%M:%S %p")
    system_info = {
        "Operating System": f"{platform.system()} {platform.release()}\n└── {platform.version()} ",
        "System Time": current_time,
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
        "System Version": current_time
    }
    language_info = {
        "Language": "Python",
        "Discord Library": f"+ {discord.__version__}\n└── discord.py"
    }
    @staticmethod
    def format_diff(value):
        cpu_threshold = 80
        python_version_threshold = "3.10.13"
        if isinstance(value, str) and value < python_version_threshold:
            return f"- {value}\n"
        elif isinstance(value, (int, float)) and value > cpu_threshold:
            return f"- {value}\n"
        else:
            return f"+ {value}\n"

# Classes
class Emojis:
    emoji_paths = {
        "cpu_emoji": "Emojis/cpu.png",
        "memory_emoji": "Emojis/memory.png",
        "python_emoji": "Emojis/python.png"
    }

    @staticmethod
    async def load(bot, ctx):
        print('Loading emojis from local files')
        emojis = {}
        for emoji_name, file_path in Emojis.emoji_paths.items():
            emoji = await Emojis.create_emoji(ctx, file_path, emoji_name)
            emoji_id = emoji.split(":")[-1][:-1]
            emoji_format = f"<:_:{emoji_id}>"
            emojis[emoji_id] = emoji_format  # Store emoji format with emoji ID as key
            print(emoji_format)

        formatted_results = ""
        for emoji_id in emojis.keys():
            formatted_results += f"<:_:{emoji_id}>"

        return formatted_results

    @staticmethod
    async def create_emoji(ctx, file_path, emoji_name):
        # Check if emoji.json file exists, create if not
        if not os.path.exists("Data"):
            os.makedirs("Data")
        if not os.path.exists("Data/emoji.json"):
            with open("Data/emoji.json", "w") as f:
                json.dump({}, f)  # Empty json file

        # Load emoji data from emoji.json
        with open("Data/emoji.json", "r") as f:
            emoji_data = json.load(f)

        # Check if emoji exists in the json
        if emoji_name in emoji_data and "emoji_id" in emoji_data[emoji_name]:
            # Emoji ID exists in json, return the emoji format
            emoji_id = emoji_data[emoji_name]["emoji_id"]
            return f"<:_:{emoji_id}>"

        # Check if emoji exists in the guild
        existing_emoji = discord.utils.get(ctx.guild.emojis, name=emoji_name)
        if existing_emoji:
            # Delete existing emoji from the guild
            await existing_emoji.delete()
            print(f"Deleted existing emoji: {existing_emoji.name}")

        # Create new emoji
        with open(file_path, "rb") as f:
            image = Image.open(f)
            img_byte_array = io.BytesIO()
            image.save(img_byte_array, format=image.format)
            img_byte_array.seek(0)
            print(f"Creating emoji from file: {file_path}")
            new_emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=img_byte_array.read())
            print(f"Emoji created successfully: {new_emoji.name}")

            # Update emoji data
            emoji_data[emoji_name] = {"emoji_id": new_emoji.id, "emoji_name": "_"}
            with open("Data/emoji.json", "w") as f:
                json.dump(emoji_data, f, indent=4)  # Save updated json with indentation

        # Return the emoji format
        return f"<:_:{new_emoji.id}>"
    

class Information_Embed:
    @staticmethod
    async def get_embed(bot_user: discord.User, bot):
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            ram_percent = psutil.virtual_memory().percent
            cpu_cores = psutil.cpu_count(logical=True)
            cpu_text = f"{cpu_percent:.0f}% of {cpu_cores} cores"
            total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)  # Convert to GB
            ram_text = f"{ram_percent:.0f}% of {total_ram_gb:.0f}GB ({total_ram_gb * ram_percent / 100:.0f}GB)"
            owner = bot.get_user(1030285330739363880)
            about = discord.Embed(
                title="Bot Information",
                description=(
                    f"Assigns member's quests to encourage server activity.\n\n"
                    f" Owner: {owner.mention}\n"
                    f"- Created: {bot_user.created_at.strftime('%B %d, %Y')}\n\n"
                    f"Internal:\n"
                    f"- **CPU**: {cpu_text}\n- **RAM**: {ram_text}\n\n"
                    "-# [Support server](https://discord.gg/5p5b7A7WRH)\n"
                    "-# [Invite bot](https://discord.com/oauth2/authorize?client_id=1234247716243112100&permissions=27482422508608&scope=bot)"

                ),
                timestamp=datetime.now()
            )
            about.set_thumbnail(url=bot.user.avatar)
            about.set_footer(text='About Myself')
            return about
        except Exception as e:
            print(e)
    
# Functions
async def sdxl(prompt):
    openai_client = AsyncOpenAI(
        api_key='ng-YgkaT8abn2sWaqZRUmVPzs07BdtrE',  # API key remains the same as provided
        base_url="https://api.naga.ac/v1"
    )

    response = await openai_client.images.generate(
        model="playground-v2.5",  # Using a valid model for image generation
        prompt=prompt,
        n=1,  # images count
        size="1024x1024"  # Standard size for image generation
    )
    return response.data[0].url


def primary_color(image_path='Data/Images/bot_icon.png'):
    image = Image.open(image_path)
    # Resize the image to 1x1 pixel to get the dominant color
    resized_image = image.resize((1, 1))
    dominant_color = resized_image.getpixel((0, 0))
    return discord.Color.from_rgb(dominant_color[0], dominant_color[1], dominant_color[2])

# Async Functions
def generate_invite_link(bot, missing_perms):
  permissions = discord.Permissions()
  text_permissions = [
    'send_messages', 'send_tts_messages', 'embed_links', 'attach_files', 
    'read_message_history', 'mention_everyone', 'use_external_emojis', 
    'add_reactions', 'manage_messages'
  ]
   
  for perm in text_permissions:
    setattr(permissions, perm, True)
   
  # return discord.utils.oauth_url(bot.user.id, permissions=permissions)
  return 'https://discord.com/oauth2/authorize?client_id=1234247716243112100&permissions=1689934340028480&integration_type=0&scope=bot'



async def error_custom_embed(bot, ctx, e, title="Custom Error", thumbnail_url=AnyaImages.question_anya):
    error_embed = discord.Embed(
        description=f'```bash\n{e}```',
        color=discord.Color.red(),
        timestamp=datetime.now()
    )
    error_embed.set_author(name=f'{bot.user.display_name.title()} - {title}', icon_url=bot.user.avatar)
    line_number = traceback.extract_tb(e.__traceback__)[-1].lineno
    tb_frame = traceback.extract_tb(e.__traceback__)[-1]
    file_location = tb_frame.filename
    error_embed.add_field(
        name=" ",
        value=f"**Potential issue found:**\n- **File:** `{file_location}`\n- **Line:** `{line_number}`",
        inline=False
    )
    error_embed.set_footer(text='Error Found')
    error_embed.set_thumbnail(url=thumbnail_url)
    
    try:
        # Check if messageable is a Context (ctx) object or Interaction object and send message accordingly
        if isinstance(ctx, commands.Context):
            await ctx.reply(embed=error_embed)
        elif isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=error_embed)
    except discord.errors.Forbidden:
        missing_perms = ['embed_links']  # Add any other permissions the bot might be missing
        invite_link = generate_invite_link(bot, ctx, missing_perms)
        error_message = f"I don't have the necessary permissions to send an embed.[Fix Permission]({invite_link})."
        
        if isinstance(ctx, commands.Context):
            await ctx.reply(error_message)
        elif isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(error_message)

    
 
