"""                   commands                   """

import os, random, asyncio, logging, aiohttp, aiofiles
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from imports.discord_imports import *
from imports.log_imports import *
from data.local.const import *
from bot.utils.cogs.quest import *
  
class Fun_Commands:
    def __init__(self):
        self._8ball_file = "data/commands/fun/8ball-responses.txt"
        action_file = "data/commands/fun/action-response.json"
        self.action_api = "https://api.otakugifs.xyz/gif?reaction={}"
        self.fallback_api = "https://api.waifu.pics/sfw/{}"
        self.nekos_api = "https://nekos.best/api/v2/{}"
        self.mongo = AsyncIOMotorClient(os.getenv("MONGO_URI")).Commands.fun
        with open(action_file) as f:
            data = json.load(f)
            self.emotes = data["emotes"]
            self.phrases = data["phrases"]
        
        # Map actions to API endpoints
        self.api_mapping = {
            "waifu.pics": ["hug", "kiss", "slap", "pat", "cuddle", "poke", "tickle", "bite", "bonk", "kick", "blush", "wave", "smile", "dance", "cry", "wink"],
            "nekos.best": ["hug", "kiss", "slap", "pat", "cuddle", "poke", "tickle", "bite", "kick", "blush", "wave", "smile", "dance", "cry", "wink", "punch", "feed", "laugh", "stare", "pout", "nod", "yawn"]
        }

    async def eight_ball(self):
        async with aiofiles.open(self._8ball_file, "r") as f:
            responses = await f.readlines()
        return random.choice([r.strip() for r in responses if r.strip()])

    async def action_command(self, ctx, user: Union[discord.Member, Literal["everyone"], None] = None, extra=""):
        if user is None:
            user = ctx.author
        action = ctx.command.name
        
        # Try to get GIF from multiple APIs with fallback
        gif = None
        async with aiohttp.ClientSession() as s:
            # Try primary API (otakugifs)
            try:
                resp = await s.get(self.action_api.format(action))
                if resp.status == 200:
                    data = await resp.json()
                    gif = data.get("url")
            except:
                pass
            
            # Try nekos.best API if primary failed
            if not gif and action in self.api_mapping.get("nekos.best", []):
                try:
                    resp = await s.get(self.nekos_api.format(action))
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results", [])
                        if results:
                            gif = results[0].get("url")
                except:
                    pass
            
            # Try waifu.pics API if still no GIF
            if not gif and action in self.api_mapping.get("waifu.pics", []):
                try:
                    resp = await s.get(self.fallback_api.format(action))
                    if resp.status == 200:
                        data = await resp.json()
                        gif = data.get("url")
                except:
                    pass
            
            # Fallback to a default GIF if all APIs fail
            if not gif:
                gif = "https://media.tenor.com/images/d8c9e1b1e5c5e5e5e5e5e5e5e5e5e5e5/tenor.gif"
        
        emote = next((e for e, acts in self.emotes.items() if action in acts), "")

        if isinstance(user, str) and user.lower() == "everyone":
            target, phrase = "the whole server", self.phrases["everyone"].get(action, f"{action}s")
        elif isinstance(user, discord.Member) and user == ctx.author:
            target, phrase = "themselves", self.phrases["self"].get(action, f"{action}s")
        else:
            target, phrase = user.display_name, self.phrases["other"].get(action, f"{action}s")

        plain = "[no_embed]" in phrase
        phrase = phrase.replace("[no_embed]", "").strip()
        msg = f"{phrase.format(user=ctx.author.display_name,target=target)} {extra}".strip() # {emote}

        sid, aid = str(ctx.guild.id), str(ctx.author.id)

        if isinstance(user, discord.Member) and not user.bot and user != ctx.author:
            await self.mongo.update_one(
                {"server_id": sid},
                {"$inc": {f"members.{action}.intake.{user.id}": 1}},
                upsert=True
            )
        if (isinstance(user, discord.Member) and not user.bot and user != ctx.author) or (isinstance(user, str) and user.lower() == "everyone"):
            await self.mongo.update_one(
                {"server_id": sid},
                {"$inc": {f"members.{action}.outtake.{aid}": 1}},
                upsert=True
            )

        doc = await self.mongo.find_one({"server_id": sid}) or {}
        sent = doc.get("members", {}).get(action, {}).get("outtake", {}).get(aid, 0)
        received = doc.get("members", {}).get(action, {}).get("intake", {}).get(aid, 0)

        embed = None if plain else discord.Embed(title=msg, color=primary_color()).set_image(url=gif).set_footer(text=f"Sent: {sent} | Received: {received}")

        view = None
        if isinstance(user, discord.Member) and user != ctx.author and not user.bot:
            view = ActionBackView(self, ctx, action, user, extra)

        return embed, msg, view


class ActionBackView(discord.ui.View):
    def __init__(self, fun, ctx, action, target, extra):
        super().__init__(timeout=None)
        self.fun = fun
        self.ctx = ctx
        self.action = action
        self.target = target
        self.extra = extra

    @discord.ui.button(label="Do it back", style=discord.ButtonStyle.primary)
    async def do_it_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user != self.target:
                await interaction.response.send_message("Only the recipient can do this back!", ephemeral=True)
                return

            async with aiohttp.ClientSession() as s:
                gif = (await (await s.get(self.fun.action_api.format(self.action))).json())["url"]
            emote = next((e for e, acts in self.fun.emotes.items() if self.action in acts), "")

            target_name = self.ctx.author.display_name
            phrase = self.fun.phrases["other"].get(self.action, f"{self.action}s")
            plain = "[no_embed]" in phrase
            phrase = phrase.replace("[no_embed]", "").strip()
            
            # Get natural-sounding do_it_back phrases from JSON
            do_it_back_phrases = self.fun.phrases.get("do_it_back", {}).get(self.action, [
                f"{interaction.user.display_name} responds back",
                f"{interaction.user.display_name} returns the {self.action}",
                f"{interaction.user.display_name} {self.action}s back"
            ])
            
            # Reference the initial message content
            original_msg = self.ctx.message.content if hasattr(self.ctx, 'message') else ""
            msg_back = f"{random.choice(do_it_back_phrases).format(user=interaction.user.display_name, target=self.ctx.author.display_name)} {self.extra}".strip()

            sid = str(interaction.guild.id)
            aid = str(interaction.user.id)

            await self.fun.mongo.update_one(
                {"server_id": sid},
                {"$inc": {f"members.{self.action}.intake.{self.ctx.author.id}": 1}},
                upsert=True
            )

            await self.fun.mongo.update_one(
                {"server_id": sid},
                {"$inc": {f"members.{self.action}.outtake.{aid}": 1}},
                upsert=True
            )

            doc = await self.fun.mongo.find_one({"server_id": sid}) or {}
            sent = doc.get("members", {}).get(self.action, {}).get("outtake", {}).get(aid, 0)
            received = doc.get("members", {}).get(self.action, {}).get("intake", {}).get(aid, 0)

            embed_back = None if plain else discord.Embed(
                title=msg_back, 
            ).set_image(url=gif).set_footer(
                text=f"Sent: {sent} | Received: {received} | Responding to {self.ctx.author.display_name}'s {self.action}"
            )

            await interaction.message.reply(content=msg_back if plain else None, embed=embed_back)

            button.disabled = True
            await interaction.response.edit_message(view=self)
            self.stop()
            
        except Exception as e:
            print(f"❌ ERROR in ActionBackView.do_it_back: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            
            # Try to respond to the user about the error
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ An error occurred while processing your action back.", ephemeral=True)
                else:
                    await interaction.followup.send("❌ An error occurred while processing your action back.", ephemeral=True)
            except:
                pass  # If we can't even send an error message, just give up
        


# ---------------- Mini Games ---------------- #
class Mini_Games:
    def __init__(self):
        self.correct_emojis = {}

    @staticmethod
    def timeout_embed():
        return discord.Embed(
            title="⏰ Time's Up...",
            description="||```You didn't click the emoji in time.```||",
            color=discord.Color.red()
        )

    @staticmethod
    def timestamp_gen(ts: int) -> str:
        return f"<t:{int(datetime.utcfromtimestamp(ts).replace(tzinfo=timezone.utc).timestamp())}:R>"


# ---------------- Reaction Game (renamed from Memo) ---------------- #
class Reaction(discord.ui.View):
    """Reaction game view with save streak and continue playing features"""
    def __init__(self, ctx, emojis, chosen_emoji, message, bot=None):
        super().__init__(timeout=None)  # No timeout - handled by command
        self.ctx = ctx
        self.emojis = list(emojis)
        self.chosen_emoji = chosen_emoji
        self.message = message
        self.bot = bot
        self.quest_data = Quest_Data(bot) if bot else Quest_Data(ctx.bot)
        self.reaction_data = Reaction_Data()
        self.user_points = {}
        self.streak_increment = 1
        self.base_points = 5
        self.points_multiplier = 2
        self.answered = False

        # Shuffle and create emoji buttons
        options = random.sample(list(set(self.emojis) - {chosen_emoji}), min(4, len(set(self.emojis))-1))
        all_options = options + [chosen_emoji]
        random.shuffle(all_options)
        
        for idx, emoji in enumerate(all_options):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                custom_id="correct_emoji" if emoji == chosen_emoji else f"emoji_{idx}",
                emoji=emoji,
                row=0
            )
            btn.callback = self.on_button_click
            self.add_item(btn)

    async def on_button_click(self, inter: discord.Interaction):
        if inter.user != self.ctx.author:
            return await inter.response.send_message("This isn't your game!", ephemeral=True)
        
        self.answered = True
        cid = inter.data["custom_id"]
        
        if cid == "correct_emoji":
            # Correct answer - increment streak
            current_streak = await self.reaction_data.get_streak(inter.guild.id, inter.user.id)
            new_streak = current_streak + self.streak_increment
            await self.reaction_data.set_streak(inter.guild.id, inter.user.id, new_streak)
            
            # Update best streak if needed
            best_streak = await self.reaction_data.get_best_streak(inter.guild.id, inter.user.id)
            if new_streak > best_streak:
                await self.reaction_data.set_best_streak(inter.guild.id, inter.user.id, new_streak)
            
            # Calculate points
            pts = self.base_points if new_streak <= 1 else int(new_streak * self.points_multiplier)
            await self.quest_data.add_balance(str(inter.user.id), str(inter.guild.id), pts)
            bal = await self.quest_data.get_balance(str(inter.user.id), str(inter.guild.id))
            
            # Show success with save/continue options
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"You earned **+{pts}** pts!\n\n"
                           f"🔥 **Streak:** {new_streak}\n"
                           f"💰 **Balance:** {bal:,} pts",
                color=discord.Color.green()
            )
            
            # Create new view with Save and Continue buttons
            continue_view = ReactionContinueView(self.ctx, self.emojis, self.message, self.bot, new_streak)
            
            self.clear_items()
            await inter.response.edit_message(embed=embed, view=continue_view)
        else:
            # Wrong answer - reset streak
            old_streak = await self.reaction_data.get_streak(inter.guild.id, inter.user.id)
            await self.reaction_data.set_streak(inter.guild.id, inter.user.id, 0)
            
            embed = discord.Embed(
                title="❌ Wrong!",
                description=f"The correct emoji was {self.chosen_emoji}\n\n"
                           f"💔 **Streak Lost:** {old_streak} → 0",
                color=discord.Color.red()
            )
            
            self.clear_items()
            await inter.response.edit_message(embed=embed, view=None)
        
        self.stop()


class ReactionContinueView(discord.ui.View):
    """View with Save Streak and Continue Playing buttons"""
    def __init__(self, ctx, emojis, message, bot, current_streak):
        super().__init__(timeout=30)
        self.ctx = ctx
        self.emojis = emojis
        self.message = message
        self.bot = bot
        self.current_streak = current_streak
        self.reaction_data = Reaction_Data()
        self.quest_data = Quest_Data(bot) if bot else Quest_Data(ctx.bot)

    @discord.ui.button(label="🛑 Save Streak", style=discord.ButtonStyle.red, row=0)
    async def save_streak(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user != self.ctx.author:
            return await inter.response.send_message("This isn't your game!", ephemeral=True)
        
        best_streak = await self.reaction_data.get_best_streak(inter.guild.id, inter.user.id)
        
        embed = discord.Embed(
            title="🏆 Streak Saved!",
            description=f"You saved your streak of **{self.current_streak}**!\n\n"
                       f"🏅 **Best Streak:** {max(best_streak, self.current_streak)}",
            color=discord.Color.gold()
        )
        
        self.clear_items()
        await inter.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="▶️ Continue Playing", style=discord.ButtonStyle.green, row=0)
    async def continue_playing(self, inter: discord.Interaction, button: discord.ui.Button):
        if inter.user != self.ctx.author:
            return await inter.response.send_message("This isn't your game!", ephemeral=True)
        
        await inter.response.defer()
        
        # Calculate difficulty based on streak
        base_time = 10
        param = self.current_streak * 0.5
        play_time = max(2.5, base_time - param)
        
        # Pick new emoji
        chosen = random.choice(self.emojis)
        
        # Show the emoji to remember
        embed = discord.Embed(
            title=f"🧠 Level {self.current_streak + 1}",
            description=f"Remember this emoji: {chosen}\n\n"
                       f"🔥 **Streak:** {self.current_streak}\n"
                       f"⏱️ **Time:** {play_time:.1f}s",
            color=discord.Color.blue()
        )
        
        self.clear_items()
        await self.message.edit(embed=embed, view=None)
        
        await asyncio.sleep(2)
        
        # Create new game view
        new_view = Reaction(self.ctx, self.emojis, chosen, self.message, self.bot)
        future = int((datetime.now(timezone.utc) + timedelta(seconds=play_time)).timestamp())
        
        embed = discord.Embed(
            description=f"Click the emoji you remembered!\n`Remaining Time:` <t:{future}:R>",
            color=discord.Color.blue()
        )
        
        await self.message.edit(embed=embed, view=new_view)
        
        # Wait for answer or timeout
        try:
            await asyncio.wait_for(new_view.wait(), timeout=play_time)
        except asyncio.TimeoutError:
            if not new_view.answered:
                # Time's up - reset streak
                await self.reaction_data.set_streak(inter.guild.id, inter.user.id, 0)
                
                timeout_embed = discord.Embed(
                    title="⏰ Time's Up!",
                    description=f"You didn't click {chosen} in time!\n\n"
                               f"💔 **Streak Lost:** {self.current_streak} → 0",
                    color=discord.Color.red()
                )
                
                for child in new_view.children:
                    child.disabled = True
                await self.message.edit(embed=timeout_embed, view=None)
        
        self.stop()

    async def on_timeout(self):
        # If they don't choose, save their streak
        embed = discord.Embed(
            title="⏰ Time to decide expired",
            description=f"Your streak of **{self.current_streak}** has been saved!",
            color=discord.Color.orange()
        )
        try:
            await self.message.edit(embed=embed, view=None)
        except:
            pass


# ---------------- Memo Game (Legacy) ---------------- #
class Memo(discord.ui.View):
    def __init__(self, ctx, emojis, chosen_emoji, message, bot=None):
        super().__init__(timeout=10)
        self.ctx, self.emojis, self.chosen_emoji, self.message = ctx, list(emojis), chosen_emoji, message
        self.bot = bot
        self.quest_data = Quest_Data(bot) if bot else Quest_Data(ctx.bot)
        self.memo_data = Memo_Data()
        self.user_points, self.streak_increment, self.base_points, self.points_multiplier = {}, 1, 5, 2

        # Buttons
        options = random.sample(set(self.emojis) - {chosen_emoji}, min(4, len(self.emojis)-1))
        for idx, emoji in enumerate(options+[chosen_emoji]):
            btn = discord.ui.Button(
                style=discord.ButtonStyle.gray,
                custom_id="correct_emoji" if emoji == chosen_emoji else f"emoji_{idx}",
                emoji=emoji
            )
            btn.callback = self.on_button_click
            self.add_item(btn)

        for b in [("Stop", discord.ButtonStyle.red, self.on_stop_click),
                  ("Continue", discord.ButtonStyle.green, self.on_continue_click)]:
            btn = discord.ui.Button(label=b[0], style=b[1])
            btn.callback = b[2]
            setattr(self, f"{b[0].lower()}_button", btn)

    # ---------- Game Logic ---------- #
    async def on_button_click(self, inter: discord.Interaction):
        u, cid = inter.user, inter.data["custom_id"]
        if cid == "correct_emoji":
            streak = await self.memo_data.get_streak(u.guild.id,u.id)+self.streak_increment
            await self.memo_data.set_streak(u.guild.id,u.id,streak)
            pts = self.base_points if streak<=1 else int(streak*self.points_multiplier)
            self.user_points[u.id]=self.user_points.get(u.id,0)+pts
            await self.quest_data.add_balance(str(u.id),str(inter.guild.id),pts)
            bal = await self.quest_data.get_balance(str(u.id),str(inter.guild.id))
            emb = await MemoEmbeds.continue_game_embed(pts,streak,bal,u)
            self.clear_items()
            [self.add_item(x) for x in (self.stop_button,self.continue_button)]
            await inter.response.edit_message(embed=emb, view=self)
        else:
            streak=await self.memo_data.get_streak(u.guild.id,u.id)
            await self.memo_data.set_streak(u.guild.id,u.id,0)
            await inter.response.edit_message(embed=MemoEmbeds.incorrect_embed(streak), view=None)

    async def on_stop_click(self, inter: discord.Interaction):
        if inter.user!=self.ctx.author:
            return await inter.response.send_message("Only author can stop!",ephemeral=True)
        streak=await self.memo_data.get_streak(inter.guild.id,inter.user.id)
        high=await self.memo_data.get_user_highscore(inter.guild.id,inter.user.id)
        emb=await MemoEmbeds.stop_game_embed(streak,high,str(inter.user.avatar))
        await inter.response.edit_message(embed=emb,view=None)

    async def on_continue_click(self, inter: discord.Interaction):
        if inter.user!=self.ctx.author:
            return await inter.response.send_message("Only author can continue!",ephemeral=True)
        await inter.response.defer()
        streak=await self.memo_data.get_streak(inter.guild.id,inter.user.id)
        pts=self.base_points if streak<=0 else int(streak*self.points_multiplier)
        self.user_points[inter.user.id]=self.user_points.get(inter.user.id,0)+pts
        new=random.choice(self.emojis)
        ts=self.ctx.cog.timestamp_gen(int((datetime.utcnow()+timedelta(seconds=self.timeout)).timestamp()))
        emb=await MemoEmbeds.blank_embed()
        emb.description=f"Remember this emoji: {new}"
        emb.add_field(name="",value=f"React with the emoji you remembered {ts}",inline=False)
        newv=Memo(self.ctx,self.emojis,new,self.message)
        await self.message.edit(embed=emb,view=newv)
        await asyncio.sleep(1)
        emb.description=" "
        await self.message.edit(embed=emb,view=newv)

    async def on_timeout(self):
        await self.memo_data.set_streak(self.ctx.guild.id,self.ctx.author.id,0)
        self.user_points[self.ctx.author.id]=0
        await self.message.edit(embed=await MemoEmbeds.timeout_embed(),view=None)


# ---------------- Database Layer ---------------- #
class Memo_Data:
    def __init__(self):
        uri=os.getenv("MONGO_URI")
        if not uri:
            raise ValueError("Missing MONGO_URI env var")
        self.mongo=motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.DB_NAME="Memo"

    async def _fetch(self,c,q,f):
        try:
            d=await self.mongo[self.DB_NAME][c].find_one(q) or {}
            return d.get(f,0)
        except PyMongoError:
            return 0

    async def _update(self,c,q,d):
        try:
            await self.mongo[self.DB_NAME][c].update_one(q,{"$set":d},upsert=True)
        except PyMongoError:
            pass

    async def get_user_highscore(self,g,u):
        return await self._fetch("highscores",{"guild_id":g,"user_id":u},"highscore")
    async def get_streak(self,g,u):
        return await self._fetch("streaks",{"guild_id":g,"user_id":u},"streak")
    async def set_user_highscore(self,g,u,s):
        await self._update("highscores",{"guild_id":g,"user_id":u},{"highscore":s})
    async def set_streak(self,g,u,s):
        await self._update("streaks",{"guild_id":g,"user_id":u},{"streak":s})


class Reaction_Data:
    """Database layer for Reaction game (renamed from Memo)"""
    def __init__(self):
        uri=os.getenv("MONGO_URI")
        if not uri:
            raise ValueError("Missing MONGO_URI env var")
        self.mongo=motor.motor_asyncio.AsyncIOMotorClient(uri)["Reaction"]

    async def _fetch(self,c,q,f):
        try:
            d=await self.mongo[c].find_one(q) or {}
            return d.get(f,0)
        except PyMongoError:
            return 0

    async def _update(self,c,q,d):
        try:
            await self.mongo[c].update_one(q,{"$set":d},upsert=True)
        except PyMongoError:
            pass

    async def get_user_highscore(self,g,u):
        return await self._fetch("highscores",{"guild_id":g,"user_id":u},"highscore")
    async def get_streak(self,g,u):
        return await self._fetch("streaks",{"guild_id":g,"user_id":u},"streak")
    async def set_user_highscore(self,g,u,s):
        await self._update("highscores",{"guild_id":g,"user_id":u},{"highscore":s})
    async def set_streak(self,g,u,s):
        await self._update("streaks",{"guild_id":g,"user_id":u},{"streak":s})
    async def get_best_streak(self,g,u):
        return await self._fetch("highscores",{"guild_id":g,"user_id":u},"best_streak")
    async def set_best_streak(self,g,u,s):
        await self._update("highscores",{"guild_id":g,"user_id":u},{"best_streak":s})


# ---------------- Embeds ---------------- #
class MemoEmbeds:
    @staticmethod
    def incorrect_embed(streak):
        return discord.Embed(
            title="❌ Incorrect",description=f"Your streak ended.\n```End Streak: {streak}```",color=discord.Color.red()
        )

    @staticmethod
    async def stop_game_embed(streak,high,av):
        desc=f"```New Highscore: {streak}```" if streak>high else f"```Current Highscore: {streak}```"
        return discord.Embed(title="🛑 Game Stopped",description=desc,color=primary_color()).set_thumbnail(url=av)

    @staticmethod
    async def blank_embed():
        return discord.Embed(color=primary_color())

    @staticmethod
    async def continue_game_embed(pts,streak,bal,u):
        emb=discord.Embed(color=primary_color())
        emb.add_field(name="Reward",value=f"⭐ `{pts} stp`",inline=True)
        emb.add_field(name="Stella Points",value=f"{bal:,}",inline=True)
        emb.set_footer(text=f"Current Streak: {streak}")
        emb.set_author(icon_url=u.avatar,name=f"{u.name}'s Progress")
        return emb

    @staticmethod
    async def timeout_embed():
        return discord.Embed(
            title="⏳ Time's Up!",description="You took too long. Streak reset to `0`.",color=discord.Color.red()
        ).set_footer(text="Try again next round!")



class QnAAnswerButton(ui.View):
    def __init__(self, bot, question_text, asker, answer_channel_id, message_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.question_text = question_text[:2000]
        self.asker = asker
        self.answer_channel_id = answer_channel_id
        self.message_id = message_id

    @ui.button(label="Answer", style=discord.ButtonStyle.primary, custom_id="qna_answer_btn")
    async def answer(self, interaction: discord.Interaction, button: ui.Button):
        if not self.asker:
            await interaction.response.send_message(
                "❌ Original asker could not be found.", ephemeral=True
            )
            return

        answer_channel = interaction.guild.get_channel(self.answer_channel_id)
        if not answer_channel:
            await interaction.response.send_message(
                "❌ Answer channel not found.", ephemeral=True
            )
            return

        modal = QnAModal(
            bot=self.bot,
            question_text=self.question_text,
            asker=self.asker,
            answer_channel_id=self.answer_channel_id,
            responder=interaction.user,
            guild_id=interaction.guild.id,  # <-- pass guild ID here
            question_message_id=self.message_id
        )
        await interaction.response.send_modal(modal)



class QnAModal(ui.Modal, title="Answer Question"):
    def __init__(self, bot, question_text, asker, answer_channel_id, responder, guild_id, question_message_id):
        super().__init__()
        self.bot = bot
        self.question_text = question_text
        self.asker = asker
        self.answer_channel_id = answer_channel_id
        self.responder = responder
        self.guild_id = guild_id
        self.question_message_id = question_message_id 

        # Answer input
        self.answer_input = ui.TextInput(
            label=self.question_text,
            style=discord.TextStyle.paragraph,
            placeholder=f"Answer the question:\n{self.question_text}",
            required=True
        )
        self.add_item(self.answer_input)

        # Optional images input
        self.images_input = ui.TextInput(
            label="Image Links (optional)",
            style=discord.TextStyle.short,
            placeholder="Enter up to 4 links (separated by space or comma)",
            required=False,
            max_length=1000
        )
        self.add_item(self.images_input)

    async def on_submit(self, interaction: discord.Interaction):
        channel = interaction.guild.get_channel(self.answer_channel_id)
        if not channel:
            await interaction.response.send_message("⚠️ Answer channel not found.", ephemeral=True)
            return

        embed = discord.Embed(
            description=(
                f"❓ **{self.asker.mention} Question:**\n```{self.question_text}```\n\n"
                f"💬 **{self.responder.mention} Answer:**\n```{self.answer_input.value}```"
            ),
            color=primary_color(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=self.responder.display_avatar.url)
        embed.set_footer(text=f"Question by {self.asker.display_name} | Answered by {self.responder.display_name}")

        # Parse image links
        image_links = []
        if self.images_input.value:
            raw = self.images_input.value.replace(",", " ").split()
            image_links = [link.strip() for link in raw if link.startswith("http")]
            image_links = image_links[:4]

        msg = await channel.send(embed=embed)
        if image_links:
            view = QnAImageButton(bot=self.bot, images=image_links, message_id=msg.id)
            await msg.edit(view=view)

        # Insert into MongoDB
        mongo_url = os.getenv("MONGO_URI")
        client = AsyncIOMotorClient(mongo_url)
        collection = client["Commands"]["qna"]
        await collection.update_one(
            {"guild_id": self.guild_id, "questions.message_id": self.question_message_id},
            {"$set": {
                "questions.$.answer_message_id": msg.id,
                "questions.$.images": image_links
            }},
            upsert=True
        )

        await interaction.response.send_message("✅ Your answer has been submitted!", ephemeral=True)


        
class QnAImageButton(ui.View):
    def __init__(self, bot, images: list[str] | None, message_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.images = images or []
        self.message_id = message_id

        button = ui.Button(
            label="📷 View Images",
            style=discord.ButtonStyle.secondary,
            custom_id=f"images_{message_id}"
        )
        button.callback = self.view_images
        self.add_item(button)

    async def view_images(self, interaction: discord.Interaction):
        if not self.images:
            await interaction.response.send_message("⚠️ No images available.", ephemeral=True)
            return

        embeds = [discord.Embed(color=discord.Color.blurple()).set_image(url=link)
                  for link in self.images[:4]]

        await interaction.response.send_message(embeds=embeds, ephemeral=True)


# ----------------------------
# Q & A Config
# ----------------------------
class QnAConfigView(ui.View):
    def __init__(self, bot, guild, current_config, collection, author):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.collection = collection
        self.selected_question = None
        self.selected_answer = None
        self.current_config = current_config
        self.message = None
        self.author = author

        # Dropdowns
        self.add_item(TextChannelSelect("Select Question Channel", self.set_question_channel, self.author))
        self.add_item(TextChannelSelect("Select Answer Channel", self.set_answer_channel, self.author))

        # Confirm button
        self.confirm_btn = ui.Button(label="Confirm Setup", style=discord.ButtonStyle.success, disabled=True)
        self.confirm_btn.callback = self.confirm_setup
        self.add_item(self.confirm_btn)

    async def set_question_channel(self, channel):
        self.selected_question = channel
        await self.update_confirm_state()

    async def set_answer_channel(self, channel):
        self.selected_answer = channel
        await self.update_confirm_state()

    async def update_confirm_state(self):
        self.confirm_btn.disabled = not (self.selected_question and self.selected_answer)
        await self.refresh_embed()

    async def refresh_embed(self):
        if not self.message:
            return
        embed = discord.Embed(
            title="Q&A Configuration",
            description="Use the dropdowns to select channels and press Confirm when ready.",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        if self.selected_question:
            embed.add_field(name="Selected Question Channel", value=self.selected_question.mention, inline=True)
        if self.selected_answer:
            embed.add_field(name="Selected Answer Channel", value=self.selected_answer.mention, inline=True)
        if self.current_config:
            q = self.guild.get_channel(self.current_config.get("question_channel"))
            a = self.guild.get_channel(self.current_config.get("answer_channel"))
            embed.set_footer(text=f"Current config: Q: {q.name if q else 'None'} | A: {a.name if a else 'None'}")
        else:
            embed.set_footer(text="No current Q&A configuration")
        await self.message.edit(embed=embed, view=self)

    async def confirm_setup(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ You cannot interact with this setup.", ephemeral=True)
            return

        await self.collection.update_one(
            {"guild_id": self.guild.id},
            {"$set": {"question_channel": self.selected_question.id, "answer_channel": self.selected_answer.id}},
            upsert=True
        )
        self.current_config = {"question_channel": self.selected_question.id, "answer_channel": self.selected_answer.id}
        await self.refresh_embed()
        await interaction.response.send_message("✅ Q&A channels saved!", ephemeral=True)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)


class TextChannelSelect(ui.ChannelSelect):
    def __init__(self, placeholder_text, callback_fn, author):
        super().__init__(
            placeholder=placeholder_text,
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )
        self.callback_fn = callback_fn
        self.author = author

    async def callback(self, interaction: discord.Interaction):
        try:
            if interaction.user != self.author:
                await interaction.response.send_message(
                    "❌ You cannot interact with this.", ephemeral=True
                )
                return

            # ChannelSelect already returns a channel object
            selected_channel = self.values[0]

            await self.callback_fn(selected_channel)
            await interaction.response.defer()
        except Exception as e:
            print(f"Error in TextChannelSelect callback: {e}")


   














# -----------------------------
# Restore persistent views
# -----------------------------
async def setup_persistent_views_fun(bot):
    mongo_url = os.getenv("MONGO_URI")
    client = AsyncIOMotorClient(mongo_url)
    collection = client["Commands"]["qna"]
    guilds_cursor = collection.find({})

    async for guild_data in guilds_cursor:
        guild_id = guild_data.get("guild_id")
        guild = bot.get_guild(guild_id)
        if not guild:
            print(f"⚠️ Guild {guild_id} not found. Skipping...")
            continue

        question_channel_id = guild_data.get("question_channel")
        answer_channel_id = guild_data.get("answer_channel")
        question_channel = guild.get_channel(question_channel_id)
        answer_channel = guild.get_channel(answer_channel_id)

        questions = guild_data.get("questions", [])
        for q in questions:
            answer_message_id = q.get("answer_message_id")
            if not answer_channel or not answer_message_id:
                continue

            try:
                answer_msg = await answer_channel.fetch_message(answer_message_id)
                asker = guild.get_member(q.get("asker_id"))

                # --- Restore Answer Button ---
                if asker:
                    answer_view = QnAAnswerButton(
                        bot=bot,
                        question_text=q.get("question", "No question text")[:2000],
                        asker=asker,
                        answer_channel_id=answer_channel.id,
                        message_id=answer_msg.id
                    )
                    bot.add_view(answer_view, message_id=answer_msg.id)

                # --- Restore Image Button(s) ---
                if q.get("images"):
                    image_view = QnAImageButton(
                        bot=bot,
                        images=q.get("images", []),
                        message_id=answer_msg.id
                    )
                    bot.add_view(image_view, message_id=answer_msg.id)

            except discord.NotFound:
                print(f"🗑️ Removing stale QnA entry: {answer_message_id}")
                await collection.update_one(
                    {"guild_id": guild.id},
                    {"$pull": {"questions": {"answer_message_id": answer_message_id}}}
                )
            except Exception as e:
                print(f"❌ Could not restore QnA answer/image buttons: {e}")  
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                
                


class RiddleAnswerModal(ui.Modal, title="Answer the Riddle"):
    def __init__(self, bot, riddle_text, answer_channel_id, responder, guild_id, message_id, mongo_url):
        super().__init__()
        self.bot = bot
        self.riddle_text = riddle_text
        self.answer_channel_id = answer_channel_id
        self.responder = responder
        self.guild_id = guild_id
        self.message_id = message_id
        self.mongo_url = mongo_url

        # Riddle field (read-only, for long riddles)
        self.riddle_display = ui.TextInput(
            label="Riddle",
            style=TextStyle.paragraph,
            default=riddle_text,  # full text
            required=False,
            max_length=2000  # Discord's modal limit
        )
        self.riddle_display.disabled = True
        self.add_item(self.riddle_display)

        # Answer field
        self.answer_input = ui.TextInput(
            label="Your Answer",
            style=TextStyle.paragraph,
            placeholder="Type your answer here...",
            required=True
        )
        self.add_item(self.answer_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            channel = interaction.guild.get_channel(self.answer_channel_id)
            if not channel:
                return await interaction.response.send_message(
                    "⚠️ Riddle answers channel not found.", ephemeral=True
                )

            embed = Embed(
                description=f"🧩 **{self.responder.mention} answered:**\n```{self.answer_input.value}```",
                color=primary_color(),
                timestamp=datetime.now()
            )
            embed.set_footer(text=f"Submitted by {self.responder.display_name}")

            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(f"Error sending embed: {e}")

            try:
                client = AsyncIOMotorClient(self.mongo_url)
                collection = client["Commands"]["riddles"]
                await collection.update_one(
                    {"guild_id": self.guild_id, "riddles.message_id": self.message_id},
                    {"$push": {"riddles.$.answers": {"user_id": self.responder.id, "answer": self.answer_input.value}}},
                    upsert=True
                )
            except Exception as e:
                print(f"Error updating MongoDB: {e}")

            await interaction.response.send_message("✅ Your answer has been submitted!", ephemeral=True)
        except Exception as e:
            print(f"RiddleAnswerModal on_submit error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Something went wrong.", ephemeral=True)
class RiddleAnswerButton(ui.View):
    def __init__(self, bot, riddle_text, answer_channel_id, message_id, mongo_url):
        super().__init__(timeout=None)
        self.bot = bot
        self.riddle_text = riddle_text
        self.answer_channel_id = answer_channel_id
        self.message_id = message_id
        self.mongo_url = mongo_url

    def copy(self):
        """Create a fresh view so button works again."""
        return RiddleAnswerButton(
            self.bot, self.riddle_text, self.answer_channel_id, self.message_id, self.mongo_url
        )

    @ui.button(label="Answer Riddle", style=ButtonStyle.primary)
    async def answer(self, interaction: discord.Interaction, button: ui.Button):
        try:
            modal = RiddleAnswerModal(
                bot=self.bot,
                riddle_text=self.riddle_text,
                answer_channel_id=self.answer_channel_id,
                responder=interaction.user,
                guild_id=interaction.guild.id,
                message_id=self.message_id,
                mongo_url=self.mongo_url
            )
            await interaction.response.send_modal(modal)
            # Re-attach fresh copy so the button can be used again
            await interaction.message.edit(view=self.copy())
        except Exception as e:
            print(f"RiddleAnswerButton error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Could not open the riddle modal.", ephemeral=True)


class RiddlePostModal(ui.Modal, title="Post a Riddle"):
    def __init__(self, bot, guild_id, mongo_url):
        super().__init__()
        self.bot = bot
        self.guild_id = guild_id
        self.mongo_url = mongo_url

        self.riddle_input = ui.TextInput(
            label="Your Riddle",
            style=TextStyle.paragraph,
            placeholder="Type the riddle here...",
            required=True
        )
        self.add_item(self.riddle_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            client = AsyncIOMotorClient(self.mongo_url)
            collection = client["Commands"]["riddles"]
            data = await collection.find_one({"guild_id": self.guild_id})
            if not data or "answer_channel_id" not in data:
                await interaction.response.send_message(
                    "❌ Riddle answers channel not set. Use `riddle setup` first.",
                    ephemeral=True
                )
                return

            answer_channel_id = data["answer_channel_id"]
            riddle_text = self.riddle_input.value

            channel = interaction.channel
            embed = Embed(
                title="🧩 New Riddle!",
                description=f"{riddle_text}\n\nAll answers will be posted in <#{answer_channel_id}>.",
                color=primary_color(),
                timestamp=datetime.now()
            )

            try:
                msg = await channel.send(
                    embed=embed,
                    view=RiddleAnswerButton(
                        self.bot, riddle_text, answer_channel_id, interaction.id, self.mongo_url
                    )
                )
            except Exception as e:
                print(f"Error sending riddle embed: {e}")

            try:
                await collection.update_one(
                    {"guild_id": self.guild_id},
                    {"$push": {"riddles": {"message_id": interaction.id, "riddle_text": riddle_text, "answers": []}}},
                    upsert=True
                )
            except Exception as e:
                print(f"Error saving riddle to MongoDB: {e}")

            await interaction.response.send_message("✅ Riddle posted!", ephemeral=True)

            try:
                await interaction.message.delete()
            except Exception as e:
                print(f"Error deleting modal message: {e}")

        except Exception as e:
            print(f"RiddlePostModal on_submit error: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Something went wrong.", ephemeral=True)


class PostRiddleButton(ui.View):
    def __init__(self, bot, guild_id, mongo_url):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id
        self.mongo_url = mongo_url

    @ui.button(label="Post a Riddle", style=discord.ButtonStyle.primary)
    async def post_riddle(self, interaction: discord.Interaction, button: ui.Button):
        try:
            modal = RiddlePostModal(self.bot, self.guild_id, self.mongo_url)
            await interaction.response.send_modal(modal)
        except Exception as e:
            print(f"PostRiddleButton error: {e}")
            await interaction.response.send_message("❌ Could not open the riddle posting modal.", ephemeral=True)
