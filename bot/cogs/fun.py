from utils.cogs.fun import *
from imports.discord_imports import *
from data.local.emojis import *
from typing import Union, Literal
import json, os, random, asyncio
from datetime import datetime, timedelta

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.fun_cmd = Fun_Commands()
        self._dynamic_commands = []
        self._path = 'data/commands/fun/action-response.json'
        self.correct_emojis = {} 
        self._create_actions()
        self.mongo_url = os.getenv("MONGO_URI")
        self.client = AsyncIOMotorClient(self.mongo_url)
        self.db = self.client["Commands"]
        self.collection = self.db["qna"]

    @commands.command(name='8ball')
    async def eight_ball(self, ctx, *, question):
        ans = await self.fun_cmd.eight_ball()
        embed = discord.Embed(
            title="🎱 8Ball",
            description=f"**{question}**\n{blank_emoji} {ans}",
            color=primary_color()
        ).set_footer(
            text=f"Requested by {ctx.author}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else None
        )
        await ctx.reply(embed=embed, mention_author=False)

    def _create_actions(self):
        try:
            with open(self._path, 'r+') as f:
                data = json.load(f)
                actions = list(data.get("phrases", {}).get("self", {}).keys())

                for act in actions:
                    async def cmd(ctx, user: Union[discord.Member, Literal["everyone"]] = None, *, txt=""):
                        embed, msg = await self.fun_cmd.action_command(ctx, user or ctx.author, txt)
                        await (ctx.reply(msg, mention_author=False) if not embed else ctx.send(embed=embed))
                    cmd.__name__ = act
                    command = commands.Command(cmd, name=act)
                    self._dynamic_commands.append(command)
                    self.bot.add_command(command)

                s, o, e = (
                    data.setdefault("phrases", {}).setdefault("self", {}),
                    data["phrases"].setdefault("other", {}),
                    data["phrases"].setdefault("everyone", {})
                )
                for a in actions:
                    s.setdefault(a, f"{a}s themselves")
                    o.setdefault(a, f"{a} {{target}}")
                    e.setdefault(a, f"{a} the whole server")
                f.seek(0); json.dump(data, f, indent=4); f.truncate()
        except FileNotFoundError:
            print(f"Missing file: {self._path}")

    def get_commands(self):
        return super().get_commands() + self._dynamic_commands
    
    
        
    @commands.command(name="memo")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def play_emoji_game(self, ctx):
        emojis = ["😀","😊","😂","😍","😎","😢","😠","😱","😡","😐","🥳","😏","🙃","😇","😅","😜","😌","😋"]
        shuffled = emojis * 2
        random.shuffle(shuffled)
        chosen = random.choice(emojis)
        self.correct_emojis[ctx.channel.id] = chosen

        embed = discord.Embed(
            description=f"Remember this emoji: {chosen}",
            color=primary_color()
        )
        msg = await ctx.reply(embed=embed, mention_author=False)
        await asyncio.sleep(2)

        view = Memo(ctx, shuffled, chosen, msg, bot=self.bot)
        future = int((datetime.utcnow() + timedelta(seconds=13)).timestamp())
        embed = discord.Embed(
            description=f"React with the emoji you remembered.\n`Remaining Time:` {self.timestamp_gen(future)}",
            color=primary_color(),
        )
        try:
            await msg.edit(embed=embed, view=view)
            await asyncio.sleep(10)
        except asyncio.TimeoutError:
            await msg.edit(embed=self.timeout_embed(), view=None)


    @commands.command(name="qna")
    @commands.has_permissions(manage_channels=True)
    async def qna(self, ctx):
        """Interactive Q&A channel setup"""
        current_config = await self.collection.find_one({"guild_id": ctx.guild.id})
        view = QnAConfigView(self.bot, ctx.guild, current_config, self.collection, ctx.author)

        embed = discord.Embed(
            title="📝 Q&A Setup",
            description=(
                "Welcome! Configure your Q&A channels using the dropdowns below.\n\n"
                "**Steps:**\n"
                "1️⃣ Select the Question channel.\n"
                "2️⃣ Select the Answer channel.\n"
                "3️⃣ Click Confirm to save your configuration.\n\n"
                "You can always re-run this command to update channels."
            ),
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )

        view.message = await ctx.reply(embed=embed, view=view, mention_author=False)

    # -----------------------------
    # Listener for questions
    # -----------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
     if message.author.bot or not message.guild:
        return
     try:
        guild_config = await self.collection.find_one({"guild_id": message.guild.id})
        if not guild_config or message.channel.id != guild_config.get("question_channel"):
            return

        await message.delete()  # Remove user's original message

        q_channel = message.guild.get_channel(guild_config["question_channel"])
        a_channel = message.guild.get_channel(guild_config["answer_channel"])
        if not q_channel or not a_channel:
            return

        embed = discord.Embed(
            title="❓ Question",
            description=f"```{message.content}```",
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Asked by {message.author}")

        # Attach the answer button
        view = QnAAnswerButton(
            bot=self.bot,
            question_text=message.content,
            asker=message.author,
            answer_channel_id=a_channel.id,
            message_id=None  # Will be set after sending
        )
        sent_msg = await q_channel.send(embed=embed, view=view)
        view.message_id = sent_msg.id  # persist for button callbacks

        # Store in Mongo
        await self.collection.update_one(
            {"guild_id": message.guild.id},
            {"$push": {"questions": {
                "message_id": sent_msg.id,
                "channel_id": q_channel.id,
                "question": message.content,
                "asker_id": message.author.id,
                "answer_message_id": None,  # placeholder for answer
                "images": []  # placeholder if images are added later
            }}},
            upsert=True
        )
        print(f"MongoDB updated with new question: {sent_msg.id}")

     except Exception as e:
        print(f"on_message error: {e}")

        
async def setup(bot):
    await setup_persistent_views_fun(bot)
    await bot.add_cog(Fun(bot))
    
