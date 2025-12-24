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
                        embed, msg, view = await self.fun_cmd.action_command(ctx, user or ctx.author, txt)
                        await ctx.reply(
                            content=msg if not embed else None,
                            embed=embed,
                            view=view,
                            mention_author=False
                        )
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
                f.seek(0)
                json.dump(data, f, indent=4)
                f.truncate()
        except FileNotFoundError:
            print(f"Missing file: {self._path}")

    def get_commands(self):
        return super().get_commands() + self._dynamic_commands

    @commands.command(name="qna")
    @commands.has_permissions(manage_channels=True)
    async def qna(self, ctx):
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

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        try:
            guild_config = await self.collection.find_one({"guild_id": message.guild.id})
            if not guild_config or message.channel.id != guild_config.get("question_channel"):
                return

            await message.delete()

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

            view = QnAAnswerButton(
                bot=self.bot,
                question_text=message.content,
                asker=message.author,
                answer_channel_id=a_channel.id,
                message_id=None
            )
            sent_msg = await q_channel.send(embed=embed, view=view)
            view.message_id = sent_msg.id

            await self.collection.update_one(
                {"guild_id": message.guild.id},
                {"$push": {"questions": {
                    "message_id": sent_msg.id,
                    "channel_id": q_channel.id,
                    "question": message.content,
                    "asker_id": message.author.id,
                    "answer_message_id": None,
                    "images": []
                }}},
                upsert=True
            )
            print(f"MongoDB updated with new question: {sent_msg.id}")

        except Exception as e:
            print(f"on_message error: {e}")

    # ---------------- Riddle Group Commands ----------------
    @commands.group(name="riddle", invoke_without_command=True)
    async def riddle_group(self, ctx):
        await ctx.send("❌ Invalid subcommand. Use `setup` or `post`.")

    @riddle_group.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def riddle_setup(self, ctx, channel: discord.TextChannel):
        client = AsyncIOMotorClient(self.mongo_url)
        collection = client["Commands"]["riddles"]
        await collection.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"answer_channel_id": channel.id}},
            upsert=True
        )
        await ctx.send(f"✅ Riddle answers will now be collected in {channel.mention}.")

    @riddle_group.command(name="post")
    async def riddle_post(self, ctx):
        """Send an embed with a button to post a riddle via modal"""
        client = AsyncIOMotorClient(self.mongo_url)
        collection = client["Commands"]["riddles"]
        data = await collection.find_one({"guild_id": ctx.guild.id})
        if not data or "answer_channel_id" not in data:
            return await ctx.send("❌ Riddle answers channel not set. Use `riddle setup` first.")

        view = PostRiddleButton(self.bot, ctx.guild.id, self.mongo_url)
        embed = discord.Embed(
            title="🧩 Post a Riddle",
            description="Click the button below to submit a new riddle via modal.",
            color=primary_color()
        )
        await ctx.send(embed=embed, view=view)
        
async def setup(bot):
    await setup_persistent_views_fun(bot)
    await bot.add_cog(Fun(bot))
    
