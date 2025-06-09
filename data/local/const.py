import asyncio, io, json, os, platform, re, traceback
from datetime import datetime, timezone

import numpy as np, cv2, psutil
from psutil import *
import requests, aiohttp
from PIL import Image
from imports.discord_imports import *
from openai import AsyncOpenAI
import logging
class AnyaImages:
    @staticmethod
    def load_images():
        with open('data/images/url_map.json', 'r') as file:
            return json.load(file)


images = AnyaImages.load_images()


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
        
        look_radiant_anya = images['look_radiant_anya']
        embed.set_footer(
            text=QUEST_PROMPT_EMBED["footer_text"],
            icon_url=look_radiant_anya,
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
        embed.set_image(url=images['start_shop_image'])
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
    image_url = images['ping_image']
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


def primary_color(image_path="data/images/bot_icon.png"):
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
    bot, ctx, e, title="Custom Error", thumbnail_url=None):
    if thumbnail_url == None:
        thumbnail_url = images['question_anya']

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
        "prefix": "-",
        "token_key": "Test_Token"
    },
    False: { 
        "prefix": ".",
        "token_key": "Token"
    }
}


def timestamp_gen(timestamp: int) -> str:
    dt = datetime.utcfromtimestamp(timestamp).replace(tzinfo=timezone.utc)
    return f'<t:{int(dt.timestamp())}:R>'

class Pokemon:
    
  @staticmethod
  def transform_pokemon_name(n):
        m={"alolan":"-alola","galarian":"-galar","hisui":"-hisui","hisuian":"-hisui","paldean":"-paldea","mega":"-mega"}
        c=re.sub(r'[^a-zA-Z\s\-]','',n).strip()
        if not c: return "",None
        l=c.lower()
        for region,suffix in m.items():
            if region in l:
                parts=c.split()
                if len(parts)>1:
                    base=[x for x in parts if x.lower()!=region]
                    if base: return base[0].lower()+suffix,region
        return c.lower(),None