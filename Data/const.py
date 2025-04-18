import asyncio
import requests
import io
import json
import os
import platform
import numpy as np
import re
import traceback
from datetime import datetime, timezone


import aiohttp
from PIL import Image
import psutil
from psutil import *  
import cv2



from Imports.discord_imports import *
from openai import (
    AsyncOpenAI,
) 

class AnyaImages:
    shocked_anya = "https://img-03.stickers.cloud/packs/20d46227-dcb0-4583-8d66-ee78d4743129/webp/a65e28be-a5fd-4654-8e7d-736dbd809df2.webp"
    awake_anya = "https://media.tenor.com/9kLYJilshNMAAAAe/spy-x-family-anya.png"
    question_anya = (
        "https://i.pinimg.com/236x/b7/23/1f/b7231fbf87eee22b6d1f35f83e9a80bd.jpg"
    )
    start_shop_thumbnail = (
        "https://i.pinimg.com/564x/fd/1d/49/fd1d49d255ca18236a27a38b8710681b.jpg"
    )
    start_shop_image = (
        "https://i.pinimg.com/564x/ed/1f/83/ed1f834eb245918964ca5507dbbc59bd.jpg"
    )
    ping_banner_anya = (
        "https://i.pinimg.com/564x/db/98/ff/db98ffc40d53378a9999528b69d66d00.jpg"
    )
    ping_image = (
        "https://i.pinimg.com/564x/25/da/ee/25daee24ea5fb98b5590d542d2879708.jpg"
    )
    sleepy_anya = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcR9y_MT3QHxXZVVzVlA94oFM8uIN0QH1fdw8Q6inySFmQ&s"
    new_mission_anya = (
        "https://i.pinimg.com/236x/b5/90/49/b590497e5e776909274ba40b040bba8c.jpg"
    )
    look_radiant_anya = (
        "https://i.pinimg.com/236x/0b/cf/4b/0bcf4b9002db8cbb5f5d42855b5d460c.jpg"
    )
    ping_thumbnail = (
        "https://i.pinimg.com/236x/5d/d7/d1/5dd7d1d91933d59b8f21732efba70368.jpg"
    )
    help_thumbnail = "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSzvquP9P7dIi5DFyTmtenWQwDyAqOu98l_juVOo6ah5Q_8N5KqT3VAdZ8twJ7L2TexN7k&usqp=CAU"
    help_ai_thumbnail = None  
    help_system_thumbnail = (
        "https://i.pinimg.com/564x/f4/38/ef/f438ef92875df915c8d019780a76a346.jpg"
    )
    help_quest_thumbnail = (
        "https://i.pinimg.com/474x/d9/af/95/d9af956f06d0de95689e2094f753aa2f.jpg"
    )
    help_pokemon_thumbnail = (
        "https://pbs.twimg.com/media/FRaJipkWUAADmt-?format=jpg&name=4096x4096"
    )
    help_anime_thumbnail = "https://anime.astronerdboy.com/wp-content/uploads/2022/06/x03-reading-manga-goofing-off-not-working.jpg"
    help_information_thumbnail = (
        "https://i.pinimg.com/474x/ae/95/91/ae9591cf2700cedc2ca63c2b5eb85990.jpg"
    )
    help_minigame_thumbnail = ("https://comicbook.com/wp-content/uploads/sites/4/2025/02/Spy-x-Family-Damian-Anya.jpeg")
    quest_completed_anya = (
        "https://i.pinimg.com/236x/26/3b/90/263b90473c3651b4fc3d30b462152c0b.jpg"
    )

    agree_to_terms_anya = (
        "https://i.pinimg.com/474x/09/47/bc/0947bc96fe6f6af4a9779d994c0a2df0.jpg"
    )
    
    no_quest_anya = (
        "https://th.bing.com/th/id/OIP.iwQwh6xaDNpS2519HlwV8gHaKg?rs=1&pid=ImgDetMain"
    )
    show_quest_anya = (
        "https://i.pinimg.com/236x/23/2f/62/232f626bc0ec7a845198149fdc38e311.jpg"
    )
    comfirmation_image_url = (
        "https://media.tenor.com/mWAIV_rO9FUAAAAe/happy-anime-girl-happy-anime.png"
    )
    system_image = (
        "https://i.pinimg.com/564x/f4/38/ef/f438ef92875df915c8d019780a76a346.jpg"
    )



class EmbedFactory:
    @staticmethod
    async def change_avatar_prompt():
        embed = discord.Embed(
            title="Change Avatar",
            description="Please provide the image attachment or the URL to replace the avatar.\n\n"
            "Type 'c' to cancel.",
            color=discord.Color.blue(),
        )
        return embed

    @staticmethod
    async def successful_avatar_change(emoji_filename):
        embed = discord.Embed(
            title="Avatar Change Successful",
            description=f"The avatar has been successfully changed to `{emoji_filename}`.",
            color=discord.Color.green(),
        )
        return embed

    @staticmethod
    async def failed_avatar_change():
        embed = discord.Embed(
            title="Avatar Change Failed",
            description=f"Failed to change the avatar.",
            color=discord.Color.red(),
        )
        return embed


class Help_Embed_Mapping:
    embed1 = {
        "title": " ",
        "description": "```Navigate through the selection options.```",
        "thumbnail_url": None,
        "image_url": None,
    }
    embed2 = {
        "title": " ",
        "description": "**Prefix**: `...<cmd.name>` || <@1234247716243112100>\n**Support Server**: [Here](https://discord.gg/qdD4gu4v).",
        "thumbnail_url": AnyaImages.help_thumbnail,
        "image_url": None,
    }


class Help_Select_Embed_Mapping:
    embeds = {
        "system": {
            "title": "System",
            "description": "View the status of the bot, including information about its current performance, system resources usage, and configuration settings.",
            "color": discord.Color.red(),  
            "thumbnail_url": AnyaImages.help_system_thumbnail,
            "image_url": "https://i.pinimg.com/564x/f4/38/ef/f438ef92875df915c8d019780a76a346.jpg",
        },
        "quest": {
            "title": "Quest",
            "description": "Manages quest tracking, balance points, and a shop in a Discord bot. It allows users to view and track quests, configure mission channels, and manage balance.",
            "color": None,  
            "thumbnail_url": AnyaImages.help_quest_thumbnail,
        },
        "ai": {
            "title": "AI",
            "description": "Interact with advanced artificial intelligence functionalities, capable of handling various tasks including natural language processing, image recognition, and more.",
            "color": discord.Color.green(),  
            "thumbnail_url": AnyaImages.help_ai_thumbnail,
        },
        "pokemon": {
            "title": "Pokemon",
            "description": "Uncover and investigate Pokémon by exploring comprehensive details and sharing your insights with others.",
            "color": discord.Color.red(),  
            "thumbnail_url": AnyaImages.help_pokemon_thumbnail,
        },
        "anime": {
            "title": "Anime",
            "description": "Waku waku! Anya offers a taste of anime or weeb content for all who seek it. Get information about your favorite anime or play around and show off some manga.",
            "color": None,
            "thumbnail_url": AnyaImages.help_anime_thumbnail,
        },
        "information": {
            "title": "Information",
            "description": "Gather the status of a member in the Discord server and stay informed to avoid looking silly. Anya can assist you with information such as server links, member details, word definitions, and more.",
            "color": None,
            "thumbnail_url": AnyaImages.help_information_thumbnail,
        },
        "mini_games": {
            "title": "Minigame",
            "description": "Engage in a fun and interactive minigame! Choose the type of minigame you'd like to play and compete for rewards and fun challenges.",
            "color": None,  
            "thumbnail_url": AnyaImages.help_minigame_thumbnail,
        },
        "Cog2": {
            "title": "Title for Cog2",
            "description": "Description for Cog2",
            "color": discord.Color.blue(),  
            "thumbnail_url": "Thumbnail URL for Cog2",
        },
        
    }

    emojis = {
        "system": "<:system:1261208067085959320>",
        "quest": "<:anyasus:1258563706518765669> ",
        "ai": "✨",
        "pokemon": "<:Pokeball:1261208239891156992>",
        "anime": "<:neko_lurk:1320306198075015201>",
        "information": "<:help_info:1268971820988764272>",
        "mini_games": "🎲",  
        
    }
class TutorialMission:
    def __init__(self, bot):
        self.bot = bot
        self.color = (
            primary_color()
        )  
        self.steps = [
            {
                "action": "send",
                "method": "message",
                "content": "Hello {member}",
                "channel": None,
                "times": 1,
                "description": 'Welcome to the tutorial mission! Your first task is to send a message saying "Hello" in the current channel.',
            },
            {
                "action": "send",
                "method": "emoji",
                "content": "👍",
                "channel": None,
                "times": 1,
                "description": 'Your next task is to send an emoji "👍" in the current channel.',
            },
            {
                "action": "send",
                "method": "reaction",
                "content": "😍",
                "channel": None,
                "times": 1,
                "description": 'Finally, react to a message with the emoji "😍" in the current channel.',
            },
        ]
        self.current_step_index = 0  
        self.current_message = None  

    async def check_completion(self, message, user, step, ctx):
        """Check if the user has completed the current tutorial mission step."""
        if step["channel"] == str(message.channel.id):
            if step["method"] == "message":
                
                member_id_pattern = r"<@!?(\d+)>"
                message_content = message.content
                member_ids = re.findall(member_id_pattern, message_content)
                for member_id in member_ids:
                    message_content = message_content.replace(
                        f"<@{member_id}>", f"<@{member_id}>"
                    )  

                quest_content_replaced = step["content"].replace(
                    "{member}", f"<@{member_ids[0]}>" if member_ids else "{member}"
                )  

                if quest_content_replaced in message_content:
                    await self.handle_completion(user, step, ctx)

            elif step["method"] == "emoji":
                
                message_emojis = re.findall(
                    r"<:[\w~]+:(\d+)>", message.content)
                message_emoji_names = [
                    str(discord.utils.get(self.bot.emojis, id=int(emoji_id)))
                    for emoji_id in message_emojis
                ]

                
                unicode_emojis = re.findall(
                    r"[\U0001F600-\U0001F64F]", message.content)

                if (
                    step["content"] in message_emoji_names
                    or step["content"] in unicode_emojis
                ):
                    await self.handle_completion(user, step, ctx)

            elif step["method"] == "reaction":
                
                if str(message.reaction.emoji) == step["content"]:
                    await self.handle_completion(user, step, ctx)

    async def handle_completion(self, user, step, ctx):
        """Handle the completion of a tutorial mission step and provide feedback."""
        feedback_message = (
            f"Congratulations {user.mention}! You have completed: {step['description']}"
        )
        channel = ctx.channel

        
        await channel.send(feedback_message)

        
        if self.current_message:
            try:
                await self.current_message.delete()
            except discord.NotFound:
                

                return
                pass

        
        self.current_step_index += 1

        
        if self.current_step_index < len(self.steps):
            await self.wait_for_user_action(ctx)
        else:
            
            await ctx.send(
                f"Congratulations {user.mention}! You have completed all tutorial steps."
            )

    async def wait_for_user_action(self, ctx):
        """Wait for the user's action to complete the tutorial mission steps."""
        step_index = self.current_step_index
        if step_index >= len(self.steps):
            return

        step = self.steps[step_index]
        embed = discord.Embed(
            title=f"Tutorial Step: {step_index + 1}",
            description=step["description"],
            color=self.color,
        )

        
        if step["method"] == "message":
            embed.add_field(
                name="Instruction",
                value=f"Send a message containing: `{step['content'].replace('{member}', ctx.author.mention)}`",
            )
        elif step["method"] == "emoji":
            embed.add_field(
                name="Instruction", value=f"Send an emoji: `{step['content']}`"
            )
        elif step["method"] == "reaction":
            embed.add_field(
                name="Instruction",
                value=f"React to a message with the emoji: `{step['content']}`",
            )

        
        if self.current_message:
            try:
                await self.current_message.delete()
            except discord.NotFound:
                
                pass
        self.current_message = await ctx.reply(embed=embed)

        
        self.steps[step_index]["channel"] = str(ctx.channel.id)

        def check_message(message):
            return message.author == ctx.author and message.channel == ctx.channel

        def check_reaction(reaction, user):
            return (
                str(reaction.emoji) == step["content"]
                and user == ctx.author
                and reaction.message.channel == ctx.channel
            )

        while True:
            try:
                if step["method"] == "message":
                    
                    user_message = await self.bot.wait_for(
                        "message", timeout=60.0, check=check_message
                    )

                    
                    if user_message.content.lower() == "c":
                        await ctx.send("Tutorial canceled.")
                        if self.current_message:
                            try:
                                await self.current_message.delete()
                            except discord.NotFound:
                                
                                pass
                        return

                    await self.check_completion(user_message, ctx.author, step, ctx)
                    break  

                elif step["method"] == "emoji":
                    
                    user_message = await self.bot.wait_for(
                        "message", timeout=60.0, check=check_message
                    )
                    await self.check_completion(user_message, ctx.author, step, ctx)
                    break  

                elif step["method"] == "reaction":
                    
                    reaction, user = await self.bot.wait_for(
                        "reaction_add", timeout=60.0, check=check_reaction
                    )
                    await self.check_completion(reaction.message, ctx.author, step, ctx)
                    break  

            except asyncio.TimeoutError:
                await ctx.send("Time's up! You didn't complete the task in time.")
                if self.current_message:
                    try:
                        await self.current_message.delete()
                    except discord.NotFound:
                        
                        pass
                return  


QUEST_PROMPT_EMBED = {
    "title": None,
    "color": discord.Color.yellow(),  
    "footer_text": "Quest Terms Agreement",
}


class Quest_Prompt:
    @staticmethod
    async def get_embed(bot):
        
        fair_emoji = discord.utils.get(bot.emojis, id=1244196046565802015)
        tracking_emoji = discord.utils.get(bot.emojis, id=1244195699331960863)
        respect_emoji = discord.utils.get(bot.emojis, id=1244196427828301825)

        print("getting embed")
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
            timestamp=datetime.now(),
        )
        
        embed.set_footer(
            text=QUEST_PROMPT_EMBED["footer_text"],
            icon_url=AnyaImages.look_radiant_anya,
        )
        return embed


class Quest_Progress:
    
    Progress_Bar_MAPPING = {
        "front_empty": 1237456749674364969,
        "front_full": 1237456617776218205,
        "mid_empty": 1237456613527523328,
        "mid_full": 1237456614697730139,
        "back_empty": 1237456616119599164,
        "back_full": 1237456619143696395,
    }

    
    @staticmethod
    async def generate_progress_bar(progress, bot):
        bar = ""
        for i in range(6):
            front_emoji = (
                discord.utils.get(
                    bot.emojis,
                    id=Quest_Progress.Progress_Bar_MAPPING[
                        "front_full" if progress >= (
                            i + 1) * 0.1 else "front_empty"
                    ],
                )
                or ":_:"
            )
            mid_emoji = (
                discord.utils.get(
                    bot.emojis,
                    id=Quest_Progress.Progress_Bar_MAPPING[
                        "mid_full" if progress >= (
                            i + 1) * 0.1 else "mid_empty"
                    ],
                )
                or ":_:"
            )
            bar += f"{front_emoji}{mid_emoji}" if i == 0 else f"{mid_emoji}"
        back_emoji = (
            discord.utils.get(
                bot.emojis,
                id=Quest_Progress.Progress_Bar_MAPPING[
                    "back_full" if progress == 1 else "back_empty"
                ],
            )
            or ":_:"
        )
        bar += f"{back_emoji}"  
        return bar


class QuestEmbed:
    @staticmethod
    async def create_quest_embed(
        bot: discord.Client,  
        quest: str,
        quest_id: int,
        action: str,
        method: str,
        channel: discord.TextChannel,
        times: int,
        content: str,
        user: discord.User,
    ) -> discord.Embed:
        
        description = (
            f"**Quest ID:** `{quest_id}`\n"
            f"**Action:** `{action.title()}`\n"
            f"**Method:** `{method}`\n"
            f"**Channel:** {channel.mention}\n"
            f"**Times:** `{times}`\n"
            f"**Content:** `{content}`"
        )

        
        added_emoji = discord.utils.get(bot.emojis, id=1244440519514521600)

        
        embed = discord.Embed(
            
            description=description,
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )

        
        embed.set_author(name=user.name, icon_url=user.avatar)

        
        embed.set_footer(text="Quest Created")
        embed.set_thumbnail(url=AnyaImages.new_mission_anya)

        return embed

    @staticmethod
    async def get_agree_confirmation_embed(bot, user):
        check_emoji_id = 1243403342722371645
        check_emoji = discord.utils.get(bot.emojis, id=check_emoji_id)

        confirmation_embed = discord.Embed(
            title=f"{check_emoji} Confirmation Complete",
            description=f"Do `...quest` to check server quest.",
            color=discord.Color.pink(),
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
            ),
        )
        return embed

    @staticmethod
    async def show_quest(bot, ctx):
        help_emoji = discord.utils.get(bot.emojis, id=1245611790176616510)

        embed = discord.Embed(
            
            timestamp=datetime.now()
        )
        embed.set_footer(text="Server Quest\n",
                         icon_url=AnyaImages.show_quest_anya)
        embed.set_author(
            name=f"{ctx.author.display_name} quests", icon_url=ctx.author.avatar
        )
        
        return embed


class Quest_Completed_Embed:
    @staticmethod
    async def create_embed(
        bot,
        quest_content,
        channel_mention,
        times,
        user,
        quest_id,
        method=None,
        reward="N/A",
        balance=None,
    ):
        
        check_emoji_id = 1243403342722371645
        reward_emoji_id = 1247800150479339581

        
        check_emoji = discord.utils.get(bot.emojis, id=check_emoji_id)
        reward_emoji = discord.utils.get(bot.emojis, id=reward_emoji_id)
        
        amount = "times" if times > 1 else "time"

        quest_completed = f'-# {check_emoji} {user.mention} : {method.title()} "{quest_content.replace("`", "")}", {times} {amount}'

        reward_text = f"`{reward} stp`"

        
        embed = discord.Embed(
            timestamp=datetime.now(), description=quest_completed, color=primary_color()
        )

        

        embed.add_field(
            name=f"Reward ", value=f"{reward_emoji} {reward_text}", inline=True
        )
        embed.add_field(name=f"Stella Points:",
                        value=f"{balance:,}", inline=True)

        
        embed.set_thumbnail(url=user.avatar)
        embed.set_footer(text=f"Congrats, you've completed quest {quest_id}!")
        return embed


class ShopEmbed:
    @staticmethod
    async def start_shop_embed(bot, ctx, balance):
        embed = discord.Embed(
            title="<:shop:1272249831120965753>    Spy Shop", color=primary_color()
        )
        
        embed.description = f"```py\nStella Points: {balance}```"
        embed.set_footer(
            text=f"Use the {bot.user.name}'s option menu to acquire your spy tool."
        )
        embed.set_thumbnail(url=ctx.author.avatar)
        embed.set_image(url=AnyaImages.start_shop_image)
        return embed


class LogConstants:
    start_log_thumbnail = "https://example.com/start_log_thumbnail.png"
    footer_text = "Please commit your changes to the repository."
    footer_icon = "https://example.com/footer_icon.png"
    author_name = "Your Bot Name"
    author_icon = "https://example.com/author_icon.png"
    embed_color = None


class PingConstants:
    thumbnail_url = None  
    image_url = AnyaImages.ping_image
    footer_icon = None
    embed_color = None

    current_time = datetime.now().strftime("%I:%M:%S %p")
    system_info = {
        "Operating System": f"{platform.system()} {platform.release()}\n└── {platform.version()} ",
        "System Time": current_time,
        "Processor": platform.processor(),
        "Python Version": platform.python_version(),
        "System Version": current_time,
    }
    language_info = {
        "Language": "Python",
        "Discord Library": f"+ {discord.__version__}\n└── discord.py",
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



class Emojis:
    emoji_paths = {
        "cpu_emoji": "Emojis/cpu.png",
        "memory_emoji": "Emojis/memory.png",
        "python_emoji": "Emojis/python.png",
    }

    @staticmethod
    async def load(bot, ctx):
        print("Loading emojis from local files")
        emojis = {}
        for emoji_name, file_path in Emojis.emoji_paths.items():
            emoji = await Emojis.create_emoji(ctx, file_path, emoji_name)
            emoji_id = emoji.split(":")[-1][:-1]
            emoji_format = f"<:_:{emoji_id}>"
            
            emojis[emoji_id] = emoji_format
            print(emoji_format)

        formatted_results = ""
        for emoji_id in emojis.keys():
            formatted_results += f"<:_:{emoji_id}>"

        return formatted_results

    @staticmethod
    async def create_emoji(ctx, file_path, emoji_name):
        
        if not os.path.exists("Data"):
            os.makedirs("Data")
        if not os.path.exists("Data/emoji.json"):
            with open("Data/emoji.json", "w") as f:
                json.dump({}, f)  

        
        with open("Data/emoji.json", "r") as f:
            emoji_data = json.load(f)

        
        if emoji_name in emoji_data and "emoji_id" in emoji_data[emoji_name]:
            
            emoji_id = emoji_data[emoji_name]["emoji_id"]
            return f"<:_:{emoji_id}>"

        
        existing_emoji = discord.utils.get(ctx.guild.emojis, name=emoji_name)
        if existing_emoji:
            
            await existing_emoji.delete()
            print(f"Deleted existing emoji: {existing_emoji.name}")

        
        with open(file_path, "rb") as f:
            image = Image.open(f)
            img_byte_array = io.BytesIO()
            image.save(img_byte_array, format=image.format)
            img_byte_array.seek(0)
            print(f"Creating emoji from file: {file_path}")
            new_emoji = await ctx.guild.create_custom_emoji(
                name=emoji_name, image=img_byte_array.read()
            )
            print(f"Emoji created successfully: {new_emoji.name}")

            
            emoji_data[emoji_name] = {
                "emoji_id": new_emoji.id, "emoji_name": "_"}
            with open("Data/emoji.json", "w") as f:
                
                json.dump(emoji_data, f, indent=4)

        
        return f"<:_:{new_emoji.id}>"


class Information_Embed:
    @staticmethod
    async def get_bot_embed(bot_user: discord.User, bot):
        def timestamp_gen(timestamp: int) -> str:
            dt = datetime.utcfromtimestamp(
                timestamp).replace(tzinfo=timezone.utc)
            return f"<t:{int(dt.timestamp())}:R>"

        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            ram_percent = psutil.virtual_memory().percent
            cpu_cores = psutil.cpu_count(logical=True)
            cpu_text = f"{cpu_percent:.0f}% of {cpu_cores} cores"
            total_ram_gb = psutil.virtual_memory().total / (1024**3)  
            ram_text = f"{ram_percent:.0f}% of {total_ram_gb:.0f}GB ({total_ram_gb * ram_percent / 100:.0f}GB)"
            total_guilds = len(bot.guilds)
            total_users = sum(guild.member_count for guild in bot.guilds)
            created_timestamp = int(bot_user.created_at.timestamp())
            created_relative = timestamp_gen(created_timestamp)

            owner_1 = bot.get_user(1124389055598170182)
            about = discord.Embed(
                title="Bot Information",
                description=(
                    f"Assigns member's quests to encourage server activity. Has other commands for those who don't wanna do server quest, Anya has alittle in store for everyone.\n\n"
                    f"🌐 Global:\n"
                    f"- Servers: {total_guilds}\n- Members: {total_users}\n\n"
                    f"❤️ Internal:\n"
                    f"- **CPU**: {cpu_text}\n- **RAM**: {ram_text}\n\n"
                    f":clock: Creation:\n"
                    f"- **Developer**: {owner_1}\n- **When?**: {created_relative}\n\n"
                    "-# [Support server](https://discord.gg/5p5b7A7WRH)\n"
                    "-# [Invite bot](https://discord.com/oauth2/authorize?client_id=1234247716243112100&permissions=27482422508608&scope=bot)\n\n"
                ),
                timestamp=datetime.now(),
                color=primary_color(),
            )
            about.set_thumbnail(url=owner_1.avatar)
            banner_url = await Information_Embed.get_user_banner_url(bot, bot.user)
            about.set_image(url=banner_url)

            about.set_footer(text="About Myself")
            return about
        except Exception as e:
            print(e)

    @staticmethod
    async def get_member_embed(bot, member):
        def timestamp_gen(timestamp: int) -> str:
            dt = datetime.utcfromtimestamp(
                timestamp).replace(tzinfo=timezone.utc)
            return f"<t:{int(dt.timestamp())}:R>"

        created_at_utc = member.created_at.replace(tzinfo=timezone.utc)
        joined_at_utc = member.joined_at.replace(tzinfo=timezone.utc)

        formatted_created_timestamp = timestamp_gen(created_at_utc.timestamp())
        formatted_joined_timestamp = timestamp_gen(joined_at_utc.timestamp())

        perms_categories = {
            "Admin": [
                "administrator",
                "manage_guild",
                "manage_channels",
                "kick_members",
                "ban_members",
            ],
            "Moderator": ["kick_members", "ban_members", "manage_messages"],
            "Member": ["send_messages", "read_messages"],
        }

        category = None
        for perm, value in member.guild_permissions:
            if category is not None:
                break
            if value:
                for role_category, perms in perms_categories.items():
                    if perm in perms:
                        category = role_category
                        break

        type_is = "🤖" if member.bot else "👤"
        category_text = category if category else "Member"

        
        bot_owner_mention = ""
        if member.bot:
            owner_id = await Information_Embed.get_bot_owner_id(bot, member.id)
            if owner_id:
                bot_owner_mention = f"\n-# **Bot Owner**: <@{bot.owner_id}>"

        description = "-# **User**: {}\n-# **Nick**: {}\n\n-# **Status**: {}\n-# **Created**: {}\n-# **Joined**: {}\n\n-# **Roles**: \n{}".format(
            member,
            member.nick or "No nickname",
            member.status,
            formatted_created_timestamp,
            formatted_joined_timestamp,
            "".join(
                [
                    (
                        f"- {role.mention} (admin)\n"
                        if role.permissions.administrator
                        else (
                            f"- {role.mention} (moderator)\n"
                            if role.permissions.kick_members
                            or role.permissions.ban_members
                            else (
                                f"- {role.mention} (baby moderator)\n"
                                if role.permissions.manage_messages
                                else f"- {role.mention}\n"
                            )
                        )
                    )
                    for role in sorted(
                        member.roles,
                        key=lambda r: (
                            r.permissions.administrator,
                            r.permissions.kick_members or r.permissions.ban_members,
                            r.permissions.manage_messages,
                        ),
                        reverse=True,
                    )
                    if role.name != "@everyone"
                ]
            )
            or "No roles",
        )

        footer = f"ID: {member.id}\nAcknowledge: {type_is} {category_text}"

        embed = discord.Embed(
            title=f"{member.display_name}",
            description=description,
            color=member.color,
            timestamp=datetime.now(),
        )

        banner_url = await Information_Embed.get_user_banner_url(bot, member)
        if banner_url:
            embed.set_image(url=banner_url)

        embed.set_thumbnail(url=member.avatar.url)

        embed.set_footer(text=footer)

        return embed

    @staticmethod
    async def get_bot_owner_id(bot, bot_id):
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://discord.com/api/v10/users/{bot_id}",
                headers={"Authorization": f"Bot {os.getenv('TOKEN')}"},
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    print(data)
                    
                    return data.get("id")
                else:
                    print(
                        f"Failed to fetch bot owner. Status code: {response.status}")
                    return None

    @staticmethod
    async def get_guild_embed(guild):
        embed = discord.Embed(
            title=f"Information for {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(),
        )

        embed.add_field(name="ID", value=f"{guild.id}", inline=False)
        embed.add_field(name="Owner", value=f"{guild.owner}", inline=False)
        embed.add_field(
            name="Member Count", value=f"{guild.member_count}", inline=False
        )
        embed.add_field(
            name="Created ",
            value=f"{guild.created_at.strftime('%b %d, %Y')}",
            inline=False,
        )

        embed.set_thumbnail(
            url=guild.icon.url if guild.icon else discord.Embed.Empty)

        return embed

    @staticmethod
    async def get_invite_embed(invite):
        embed = discord.Embed(
            title=f"Invite Information",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )

        embed.add_field(name="Invite Code",
                        value=f"{invite.code}", inline=False)
        embed.add_field(
            name="Guild", value=f"{invite.guild.name}", inline=False)
        embed.add_field(
            name="Channel", value=f"{invite.channel.name}", inline=False)
        embed.add_field(
            name="Inviter", value=f"{invite.inviter}", inline=False)
        embed.add_field(name="Uses", value=f"{invite.uses}", inline=False)
        embed.add_field(
            name="Max Uses",
            value=f"{invite.max_uses}" if invite.max_uses else "Unlimited",
            inline=False,
        )
        embed.add_field(
            name="Expires At",
            value=(
                f"{invite.expires_at.strftime('%b %d, %Y %H:%M:%S')}"
                if invite.expires_at
                else "Never"
            ),
            inline=False,
        )

        embed.set_thumbnail(
            url=invite.guild.icon.url if invite.guild.icon else discord.Embed.Empty
        )

        return embed

    @staticmethod
    async def get_user_banner_url(bot, user):
        req = await bot.http.request(
            discord.http.Route("GET", "/users/{uid}", uid=user.id)
        )
        banner_id = req.get("banner")
        if banner_id:
            image_size = "?size=1024"
            animated = banner_id.startswith("a_")
            file_extension = "gif" if animated else "png"
            image_base_url = "https://cdn.discordapp.com/"
            banners_endpoint = f"banners/{user.id}/{banner_id}.{file_extension}"
            return f"{image_base_url}{banners_endpoint}{image_size}"
        return None



async def sdxl(prompt):
    openai_client = AsyncOpenAI(
        
        api_key="ng-YgkaT8abn2sWaqZRUmVPzs07BdtrE",
        base_url="https://api.naga.ac/v1",
    )

    response = await openai_client.images.generate(
        model="playground-v2.5",  
        prompt=prompt,
        n=1,  
        size="1024x1024",  
    )
    return response.data[0].url


def primary_color(image_path="Data/images/bot_icon.png"):
    image = Image.open(image_path)
    image = image.convert("RGB")
    resized_image = image.resize((1, 1))
    dominant_color = resized_image.getpixel((0, 0))
    return discord.Color.from_rgb(
        dominant_color[0], dominant_color[1], dominant_color[2]
    )



def generate_invite_link(bot, missing_perms):
    permissions = discord.Permissions()
    text_permissions = [
        "send_messages",
        "send_tts_messages",
        "embed_links",
        "attach_files",
        "read_message_history",
        "mention_everyone",
        "use_external_emojis",
        "add_reactions",
        "manage_messages",
    ]

    for perm in text_permissions:
        setattr(permissions, perm, True)

    
    return "https://discord.com/oauth2/authorize?client_id=1234247716243112100&permissions=1689934340028480&integration_type=0&scope=bot"



async def banner_url(bot, user):
    req = await bot.http.request(discord.http.Route("GET", "/users/{uid}", uid=user.id))
    banner_id = req.get("banner")
    if banner_id:
        image_size = "?size=1024"
        animated = banner_id.startswith("a_")
        file_extension = "gif" if animated else "png"
        image_base_url = "https://cdn.discordapp.com/"
        banners_endpoint = f"banners/{user.id}/{banner_id}.{file_extension}"
        return f"{image_base_url}{banners_endpoint}{image_size}"
    return None



async def get_banner_color(bot, user: discord.User):
    try:
        req = await bot.http.request(
            discord.http.Route("GET", "/users/{uid}", uid=user.id)
        )
        banner_color = req.get("banner_color")

        if banner_color:
            return banner_color
        else:
            return None
    except Exception as e:
        print(f"An error occurred while fetching banner color: {e}")
        return None


async def error_custom_embed(
    bot, ctx, e, title="Custom Error", thumbnail_url=AnyaImages.question_anya
):
    error_embed = discord.Embed(
        description=f"```bash\n{e}```",
        color=discord.Color.red(),
        timestamp=datetime.now(),
    )
    error_embed.set_author(
        name=f"{bot.user.display_name.title()} - {title}", icon_url=bot.user.avatar
    )
    line_number = traceback.extract_tb(e.__traceback__)[-1].lineno
    tb_frame = traceback.extract_tb(e.__traceback__)[-1]
    file_location = tb_frame.filename
    error_embed.add_field(
        name=" ",
        value=f"**Potential issue found:**\n- **File:** `{file_location}`\n- **Line:** `{line_number}`",
        inline=False,
    )
    error_embed.set_footer(text="Error Found")
    error_embed.set_thumbnail(url=thumbnail_url)

    try:
        
        if isinstance(ctx, commands.Context):
            await ctx.reply(embed=error_embed)
        elif isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(embed=error_embed)
    except discord.errors.Forbidden:
        missing_perms = [
            "embed_links"
        ]  
        invite_link = generate_invite_link(bot, ctx, missing_perms)
        error_message = f"I don't have the necessary permissions to send an embed.[Fix Permission]({invite_link})."

        if isinstance(ctx, commands.Context):
            await ctx.reply(error_message)
        elif isinstance(ctx, discord.Interaction):
            await ctx.response.send_message(error_message)


def timestamp_gen(timestamp: int) -> str:
    dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    return f"<t:{int(dt.timestamp())}:R>"




class AvatarToTextArt:
    def __init__(s, url, w=80, h=40):
        s.u = url
        s.w = w
        s.h = h
        s.i = s.g = s.r = s.a = s.ca = None
        s.c = '@%#*+=-:. '

    def f(s):
        s.i = np.array(Image.open(io.BytesIO(requests.get(s.u).content)).convert('RGB'))

    def g_(s):
        if s.i is not None: s.g = cv2.cvtColor(s.i, cv2.COLOR_RGB2GRAY)

    def r_(s):
        if s.g is not None:
            s.g = cv2.resize(s.g, (s.w, s.h))
            s.r = cv2.resize(s.i, (s.w, s.h))

    def m(s):
        if s.g is not None:
            n = len(s.c)
            s.a = ''.join([s.c[(n - 1) - (min(int(p), 255) * (n - 1) // 255)] for p in s.g.flatten()])

    def ansi(s, r, g, b):
        return f'\033[38;2;{r};{g};{b}m'

    def c_(s):
        if s.r is not None and s.a is not None:
            t = ""
            try: tw = os.get_terminal_size().columns
            except: tw = 120
            pad = " " * ((tw - s.w) // 2)
            for i, ch in enumerate(s.a):
                y, x = divmod(i, s.w)
                if x == 0 and i > 0: t += "\n" + pad
                elif i == 0: t += pad
                r, g, b = np.clip(s.r[y, x], 0, 255).astype(int)
                t += f"{s.ansi(r, g, b)}{ch}\033[0m"
            s.ca = t + "\n"

    def create_art(s):
        s.f()
        s.g_()
        s.r_()
        s.m()
        s.c_()

    def get_colored_ascii_art(s):
        return s.ca

    def p(s):
        print(s.ca if s.ca else "Run run() first.") 
    
bot_config = {
    True: { 
        "prefix": ".",
        "token_key": "Test_Token"
    },
    False: { 
        "prefix": "...",
        "token_key": "Token"
    }
}
