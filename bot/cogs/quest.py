import datetime, typing, traceback, json
from io import BytesIO


from data.local.const import *
from imports.discord_imports import *
from imports.log_imports import *
from utils.cogs.quest import *
from utils.cogs.leaderboard_image import LeaderboardImageGenerator
from utils.character_utils import format_character_name
from utils.cogs.quest import _safe_select_emoji
from utils.character_utils import get_character_def
from utils.character_utils import build_character_embed_with_files



import discord
from discord.ext import commands
import json
import logging
from io import BytesIO
from datetime import datetime
import os
import time
logger = logging.getLogger(__name__)


def _today_key_utc() -> str:
    now = datetime.utcnow()
    return f"{now.year:04d}-{now.month:02d}-{now.day:02d}"


def _is_dev_owner(user_id: str) -> bool:
    # Keep simple: allowlist via env var, comma-separated user IDs.
    raw = str(os.getenv("BOT_OWNER_IDS") or "").strip()
    if not raw:
        return False
    allow = {s.strip() for s in raw.split(",") if s.strip()}
    return str(user_id) in allow


async def _claim_ready_pending_meals(quest_data: Quest_Data, *, guild_id: str, user_id: str) -> int:
    """Move any pending meals whose ready_at has passed into sxf.meals inventory.

    Returns number of meals claimed.
    """
    now = int(time.time())
    try:
        doc = await quest_data.mongoConnect[quest_data.DB_NAME]["Servers"].find_one(
            {"guild_id": guild_id},
            {f"members.{user_id}.inventory.sxf.pending_meals": 1},
        )
    except Exception:
        return 0

    pending = (
        (((doc or {}).get("members") or {}).get(user_id) or {})
        .get("inventory", {})
        .get("sxf", {})
        .get("pending_meals", {})
    )
    if not isinstance(pending, dict) or not pending:
        return 0

    claimed = 0
    for meal_name, ready_at in list(pending.items()):
        try:
            ra = int(ready_at)
        except Exception:
            ra = None
        if not meal_name or ra is None or ra > now:
            continue
        ok = await quest_data.add_item_to_inventory(guild_id, user_id, "sxf.meals", str(meal_name), 1)
        if ok:
            claimed += 1
            try:
                await quest_data.mongoConnect[quest_data.DB_NAME]["Servers"].update_one(
                    {"guild_id": guild_id},
                    {"$unset": {f"members.{user_id}.inventory.sxf.pending_meals.{meal_name}": ""}},
                    upsert=True,
                )
            except Exception:
                pass
    return claimed


async def _can_cook_today(quest_data: Quest_Data, *, guild_id: str, user_id: str, limit: int = 10) -> tuple[bool, int]:
    """Return (allowed, used_today)."""
    day = _today_key_utc()
    if _is_dev_owner(user_id):
        return True, 0
    try:
        doc = await quest_data.mongoConnect[quest_data.DB_NAME]["Servers"].find_one(
            {"guild_id": guild_id},
            {f"members.{user_id}.inventory.sxf.daily_cook.{day}": 1},
        )
        used = (
            (((doc or {}).get("members") or {}).get(user_id) or {})
            .get("inventory", {})
            .get("sxf", {})
            .get("daily_cook", {})
            .get(day, 0)
        )
        used_i = int(used or 0)
    except Exception:
        used_i = 0
    return used_i < int(limit), used_i


async def _note_cook_today(quest_data: Quest_Data, *, guild_id: str, user_id: str) -> None:
    if _is_dev_owner(user_id):
        return
    day = _today_key_utc()
    try:
        await quest_data.mongoConnect[quest_data.DB_NAME]["Servers"].update_one(
            {"guild_id": guild_id},
            {"$inc": {f"members.{user_id}.inventory.sxf.daily_cook.{day}": 1}},
            upsert=True,
        )
    except Exception:
        return


_REPO_ROOT = Path(__file__).resolve().parents[2]


class Quest(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        self.shop_file = str(_REPO_ROOT / "data" / "commands" / "quest" / "shop.json")
        self.shop_data = self.load_shop_data()

    def load_shop_data(self):
        try:
            with open(self.shop_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading shop data: {e}")
            return {}

    @staticmethod
    def _sxf_data_path(*parts: str) -> str:
        return str(_REPO_ROOT / "data" / "commands" / "minigames" / "spy-x-family" / Path(*parts))

    def get_tool_emoji(self, tool_name):
        """Fetches the emoji for a given tool name."""
        for category, items in self.shop_data.items():
            for item in items:
                if item["name"].lower() == tool_name.lower():
                    return item.get("emoji", "")
        return ""

    @commands.command(name="redirect")
    async def redirect(self, ctx, *channel_mentions: discord.TextChannel):
        if not (
            ctx.author.guild_permissions.manage_channels
            or discord.utils.get(ctx.author.roles, name="Anya Manager")
        ):
            await ctx.reply(
                "You need the `Manage Channels` permission or the `Anya Manager` role to use this command.",
                mention_author=False,
            )
            return

        try:
            guild_id = str(ctx.guild.id)
            channel_ids = [str(channel.id) for channel in channel_mentions]

            if await self.quest_data.store_channels_for_guild(guild_id, channel_ids):
                await ctx.reply(
                    f"Now redirecting missions to {', '.join([channel.mention for channel in channel_mentions])}",
                    mention_author=False,
                )
            else:
                await ctx.reply(
                    "Failed to store the channels. Please try again later.",
                    mention_author=False,
                )
        except Exception as e:
            logger.error(f"Error in setchannels command: {e}")
            await ctx.send("An error occurred while setting the channels.")

    @commands.group(name="quest", aliases=["q"], invoke_without_command=True)
    async def quest(self, ctx, args: str = None):
        """Main quest command."""
        logger.debug("Quest command invoked.")

        if args == "newbie":
            logger.debug("Starting newbie tutorial.")
            tutorial_mission = TutorialMission(self.bot)
            await tutorial_mission.wait_for_user_action(ctx)
            return

        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            user_exists = await self.quest_data.find_user_in_server(user_id, guild_id)

            if not user_exists:
                prompt_embed = await Quest_Prompt.get_embed(self.bot)
                await ctx.reply(
                    embed=prompt_embed,
                    view=Quest_Button(self.bot, ctx),
                    mention_author=False,
                )
                return

            quests = await self.quest_data.find_quests_by_user_and_server(user_id, guild_id)

            if quests:
                view = Quest_View(self.bot, quests, ctx)
                embeds = await view.generate_messages()

                image_generator = ImageGenerator(
                    ctx,
                    text="Complete each quest to earn rewards. Click the location link to go to the corresponding channel."
                )

                img = image_generator.create_image()
                img_bytes = BytesIO()
                img.save(img_bytes, format="PNG")
                img_bytes.seek(0)

                image_generator.save_image(file_path="data/images/generated_image.png")
                file = discord.File("data/images/generated_image.png", filename="image.png")

                embeds.set_image(url=f"attachment://image.png")

                if len(quests) > 3:
                    await ctx.reply(embed=embeds, view=view, mention_author=False, file=file)
                else:
                    await ctx.reply(embed=embeds, mention_author=False, file=file)
            else:
                # Use Quest_View which handles empty quests and shows New Quest button
                view = Quest_View(self.bot, [], ctx)
                embed = await view.generate_messages()
                await ctx.reply(
                    embed=embed,
                    view=view,
                    mention_author=False,
                )

        except Exception as e:
            error_message = "An error occurred while fetching quests."
            logger.error(f"{error_message}: {e}")
            traceback.print_exc()
            await ctx.send(error_message)

    @quest.command(name="roles")
    async def quest_roles(self, ctx, *role_mentions: discord.Role):
        """Set or list roles that a target can get randomly."""
        if not (ctx.author.guild_permissions.manage_roles or discord.utils.get(ctx.author.roles, name="Anya Manager")):
            embed = discord.Embed(
                title="Permission Denied",
                description="You need the `Manage Roles` permission or the `Anya Manager` role to use this command.",
                color=discord.Color.red(),
                timestamp=datetime.now(),
            )
            embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
            await ctx.reply(embed=embed, mention_author=False)
            return

        guild_id = str(ctx.guild.id)

        # If no roles mentioned, display current roles
        if not role_mentions:
            current_roles = await self.quest_data.get_roles_for_guild(guild_id)
            if current_roles:
                roles_list = "\n".join([f"<@&{role_id}>" for role_id in current_roles])
            else:
                roles_list = (
                    "No roles have been set yet.\n\n"
                    "**Admins can set roles using the command below:**\n"
                    f"`{ctx.prefix}quest roles <@mention role1> <@mention role2> ... etc`"
                )

            embed = discord.Embed(
                description=f"```Grants the target user a random role from the list of available roles in the server.```\n**Current Set Roles:**\n{roles_list}",
                color=discord.Color.blue(),
                timestamp=datetime.now(),
            )
            embed.set_footer(text="Needed Tool: Key Chain Sheep", icon_url=self.bot.user.avatar.url)
            embed.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
            await ctx.reply(embed=embed, mention_author=False)
            return

        # Store new roles
        role_ids = [str(role.id) for role in role_mentions]
        await self.quest_data.store_roles_for_guild(guild_id, role_ids)

        embed = discord.Embed(
            title="Roles Set Successfully",
            description="Allows targets to get a random role.\n\nThe following roles have been set for this guild:",
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url)
        roles_list = "\n".join([role.mention for role in role_mentions])
        embed.add_field(name="Roles", value=roles_list, inline=False)

        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="profile", aliases=["pf"])
    async def profile(self, ctx, member: discord.Member = None):
     member = member or ctx.author
     g, u, a = str(ctx.guild.id), str(member.id), str(ctx.author.id)

     if not await self.quest_data.find_user_in_server(a, g):
        return await ctx.reply(f"You need to start your quest first using `{ctx.prefix}quest` before viewing profiles.", mention_author=False)

     if not await self.quest_data.find_user_in_server(u, g):
        return await ctx.reply(f"{'You' if member == ctx.author else member.mention} need to start a quest first using `{ctx.prefix}quest` before viewing this profile.\n-# Requested by {ctx.author}", mention_author=False)

     try:
        balance = await self.quest_data.get_balance(u, g)
     except AttributeError:
        balance = 0
        logger.warning(f"Balance fetch failed for user {u} in guild {g}, defaulting to 0")

     await ProfileView(ctx, member, balance, self.quest_data).start(ctx)

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        try:
            guild_id = str(ctx.guild.id)
            user_id = str(ctx.author.id)

            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_collection = db["Servers"]

            user_data = await server_collection.find_one(
                {"guild_id": guild_id, f"members.{user_id}": {"$exists": True}},
                {f"members.{user_id}.inventory"},
            )

            if not user_data:
                await ctx.reply(
                    f"{ctx.author.mention}, you need to start your quest first with `{ctx.prefix}quest` before viewing your inventory.",
                    mention_author=False,
                )
                return

            inventory = (
                user_data.get("members", {})
                .get(user_id, {})
                .get("inventory", {})
            )

            if not inventory:
                await ctx.reply(
                    f"{ctx.author.mention}, your inventory is empty! Start collecting items to see them here.",
                    mention_author=False,
                )
                return

            # Create inventory view with category selection
            inventory_view = InventoryView(self.quest_data, guild_id, user_id, ctx.author)
            await inventory_view.start(ctx)

        except Exception as e:
            await ctx.reply(
                f"An error occurred while fetching your inventory: {e}",
                mention_author=False,
            )
            logger.error(f"Error in inventory command: {e}")

    @commands.command(name="balance", aliases=["bal", "points", "stars", "stp"])
    async def balance(
        self, ctx, method=None, amount: int = None, member: discord.Member = None
    ):
        guild_id = str(ctx.guild.id)
        target_member = member if member else ctx.author
        target_id = str(target_member.id)

        try:
            if method == "add":
                if ctx.author.id in [1030285330739363880, 1124389055598170182]:
                    await self.quest_data.add_balance(target_id, guild_id, amount)
                    amount_with_commas = "{:,}".format(amount)
                    await ctx.send(
                        f"Added {amount_with_commas} Stella Points to {target_member.display_name}'s balance.",
                        mention_author=False,
                    )
                    return
                else:
                    await ctx.reply(
                        "You don't have permission to use this command.",
                        mention_author=False,
                    )
                    return

            balance = await self.quest_data.get_balance(target_id, guild_id)
            
            # Get leaderboard position
            leaderboard = await self.quest_data.get_leaderboard(guild_id)
            position = next((i+1 for i, (user_id, _) in enumerate(leaderboard) if user_id == target_id), None)
            
            embed = discord.Embed(color=primary_color())
            embed.set_author(name=f"{target_member.display_name}'s Balance", icon_url=target_member.display_avatar.url)
            
            embed.add_field(name="Stella Points", value=f"```{balance:,}```")
            if position:
                embed.add_field(name="Server Rank", value=f"`#{position}`")
            
            await ctx.reply(embed=embed, mention_author=False)

        except Exception as e:
            logger.error(f"An error occurred in the balance command: {e}")
            traceback.print_exc()
            await ctx.send(
                "An error occurred while processing your request. Please try again later."
            )

    @quest.command(name="leaderboard", aliases=["lb", "top", "ranking"])
    async def quest_leaderboard(self, ctx, limit: int = 10):
        """Show the stella points leaderboard for this server."""
        try:
            guild_id = str(ctx.guild.id)
            
            # Cap limit between 1 and 15 for image
            limit = max(1, min(15, limit))
            
            leaderboard_data = await self.quest_data.get_leaderboard(guild_id, limit)
            
            if not leaderboard_data:
                embed = discord.Embed(
                    description="No users with stella points found yet!\nComplete quests to earn points and appear on the leaderboard.",
                    color=discord.Color.yellow()
                )
                embed.set_author(name=f"{ctx.guild.name} Leaderboard", icon_url=ctx.guild.icon.url if ctx.guild.icon else None)
                await ctx.reply(embed=embed, mention_author=False)
                return
            
            # Build entries for image generator
            entries = []
            author_rank = None
            author_points = None
            
            for i, entry in enumerate(leaderboard_data):
                user_id = entry.get("user_id")
                points = int(entry.get("stella_points", 0))
                quests_done = int(entry.get("quests_done", 0))
                
                if user_id == str(ctx.author.id):
                    author_rank = i + 1
                    author_points = points
                
                try:
                    member = ctx.guild.get_member(int(user_id)) if user_id else None
                except Exception:
                    member = None
                
                username = member.display_name if member else f"User {user_id[-4:]}" if user_id else "Unknown"
                avatar_url = str(member.display_avatar.url) if member and member.display_avatar else None
                
                entries.append({
                    "rank": i + 1,
                    "username": username,
                    "points": points,
                    "quests_done": quests_done,
                    "avatar_url": avatar_url
                })
            
            # Generate leaderboard image
            generator = LeaderboardImageGenerator()
            image_buffer = await generator.generate(entries)
            
            # Send image directly without embed
            file = discord.File(image_buffer, filename="leaderboard.png")
            
            # Add user's rank info as text content
            content = None
            if author_rank:
                content = f"-# Your rank: **#{author_rank}** with **{author_points:,}** stella points"
            else:
                user_balance = await self.quest_data.get_balance(str(ctx.author.id), guild_id)
                if user_balance > 0:
                    content = f"-# Your stella points: **{user_balance:,}**"
            
            await ctx.reply(content=content, file=file, mention_author=False)
            
        except Exception as e:
            logger.error(f"Error in leaderboard command: {e}")
            traceback.print_exc()
            await ctx.send("An error occurred while fetching the leaderboard.")

    @commands.command(name="shop")
    async def shop(self, ctx):
        try:
            shop_data = self.read_shop_file(self.shop_file)
            view = ShopView(self.bot, shop_data)
            await view.start(ctx)
        except Exception as e:
            await ctx.send(f"An error occurred while processing the shop: {e}")

    @commands.command(name="cook")
    async def cook(self, ctx):
        try:
            user_id = str(ctx.author.id)
            guild_id = str(ctx.guild.id)

            # Claim any finished meals first.
            await _claim_ready_pending_meals(self.quest_data, guild_id=guild_id, user_id=user_id)

            allowed, used = await _can_cook_today(self.quest_data, guild_id=guild_id, user_id=user_id, limit=10)
            if not allowed:
                return await ctx.reply(
                    f"You've reached your daily cooking limit (**10/day**). Try again tomorrow. (used: {used}/10)",
                    mention_author=False,
                )

            if not await self.quest_data.find_user_in_server(user_id, guild_id):
                return await ctx.reply(
                    f"You need to start your quest first using `{ctx.prefix}quest` before cooking.",
                    mention_author=False,
                )

            # Require at least one Spy x Family character
            chars_data = []
            try:
                with open(self._sxf_data_path("characters.json"), "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict):
                    for k, v in raw.items():
                        if isinstance(v, dict):
                            chars_data.append({"id": k, **v})
            except FileNotFoundError:
                chars_data = []

            # Fetch all owned characters in ONE DB query instead of per-character
            owned_char_inventory = await self.quest_data.get_user_inventory_category(
                guild_id, user_id, "sxf.characters"
            ) or {}

            owned_chars = []
            for c in chars_data:
                name = c.get("id")
                if not name:
                    continue
                owned = owned_char_inventory.get(name, 0)
                if isinstance(owned, int) and owned > 0:
                    owned_chars.append(c)

            if not owned_chars:
                return await ctx.reply(
                    "You need at least **one Spy x Family character** before you can cook. Buy one in the shop first.",
                    mention_author=False,
                )

            # Default to the user's selected character (if set)
            selected_char_id = None
            try:
                doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                    {"guild_id": guild_id},
                    {f"members.{user_id}.inventory.sxf.selected_character": 1},
                )
                bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("selected_character", {})
                if isinstance(bucket, dict):
                    for k, v in bucket.items():
                        if isinstance(v, int) and v > 0:
                            selected_char_id = k
                            break
            except Exception:
                selected_char_id = None

            view = CookingRecipeSelectView(self.bot, self.quest_data, ctx, owned_chars)
            if selected_char_id and any(c.get("id") == selected_char_id for c in owned_chars):
                view.selected_char_id = selected_char_id
                chosen = next((c for c in owned_chars if c.get("id") == selected_char_id), None)
                view.selected_char_difficulty = str((chosen or {}).get("cooking-difficulty") or "normal").lower()
            elif owned_chars:
                # If user hasn't selected a character yet, default to the first owned one.
                view.selected_char_id = str(owned_chars[0].get("id") or "") or None
                view.selected_char_difficulty = str((owned_chars[0] or {}).get("cooking-difficulty") or "normal").lower()
            embed = await view.create_embed()
            if ctx.author.avatar:
                embed.set_thumbnail(url=ctx.author.avatar.url)
            await view.update_view()
            await ctx.reply(embed=embed, view=view, mention_author=False)

            # Count this as a cooking attempt/day usage.
            await _note_cook_today(self.quest_data, guild_id=guild_id, user_id=user_id)

        except Exception as e:
            logger.error(f"Error in cook command: {e}")
            traceback.print_exc()
            await ctx.reply(f"An error occurred while starting cooking: `{e}`", mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # CHARACTER COMMAND - View and interact with owned characters
    # ═══════════════════════════════════════════════════════════════
    async def _get_selected_character(self, guild_id: str, user_id: str) -> str | None:
        """Get the currently selected character for a user."""
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("selected_character", {})
        except Exception:
            bucket = {}
        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        return k
                except Exception:
                    continue
        return None

    async def _get_first_owned_character(self, guild_id: str, user_id: str) -> str | None:
        """Get the first owned character if no character is selected."""
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.characters": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("characters", {})
            )
        except Exception:
            bucket = {}

        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        return k
                except Exception:
                    continue
        return None

    async def _resolve_active_character(self, guild_id: str, user_id: str) -> str | None:
        """Resolve the active character - selected or first owned."""
        selected = await self._get_selected_character(guild_id, user_id)
        if selected:
            return selected
        return await self._get_first_owned_character(guild_id, user_id)

    @quest.command(name="character", aliases=["char", "view"])
    async def quest_character(self, ctx: commands.Context):
        """View your active character from the quest system."""
        if not ctx.guild:
            return await ctx.reply("This command can only be used in a server.", mention_author=False)

        guild_id = str(ctx.guild.id)
        user_id = str(ctx.author.id)

        user_exists = await self.quest_data.find_user_in_server(user_id, guild_id)
        if not user_exists:
            return await ctx.reply(
                f"You need to start your quest first using `{ctx.prefix}quest` before viewing your character.",
                mention_author=False
            )

        char_id = await self._resolve_active_character(guild_id, user_id)
        if not char_id:
            return await ctx.reply(
                "You don't own any characters yet. Complete quests to earn characters!",
                mention_author=False
            )

        owned = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.characters", char_id)
        if (owned or 0) <= 0:
            return await ctx.reply("You don't own any characters.", mention_author=False)

        char_def = get_character_def(char_id)
        if not char_def:
            return await ctx.reply("Character not found.", mention_author=False)
        
        max_hp = max(1, int(char_def.base_hp))
        stored_hp = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", char_id)
        hp = int(stored_hp or max_hp)
        hp = max(0, min(hp, max_hp))

        view = CharacterView(self.bot, self.quest_data, ctx, char_id)
        view.image_index = await view._get_selected_image_index()

        next_feed_ts, _ = await view._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=view.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
        )
        msg = await ctx.reply(embed=embed, view=view, files=files, mention_author=False)
        view.message = msg

    @commands.command(name="character", aliases=["char"])
    async def character(self, ctx: commands.Context):
        """View your active character (standalone command)."""
        await self.quest_character(ctx)

    @commands.command(name="feedback", aliases=["fb"])
    async def quest_feedback(self, ctx: commands.Context):
        """Toggle quest feedback messages on/off."""
        try:
            # Get the Quest_Events cog to access feedback settings
            quest_events = self.bot.get_cog("Quest_Events")
            if not quest_events:
                await ctx.reply("Quest system not available.", mention_author=False)
                return
            
            user_id = str(ctx.author.id)
            new_state = quest_events._toggle_feedback(user_id)
            
            embed = discord.Embed(color=0xff6b9d)  # Anya pink
            if new_state:
                embed.title = "✅ Quest Feedback Enabled"
                embed.description = f"{ctx.author.mention}, you will now receive helpful tips when working on quests!"
                embed.add_field(name="What you'll see:", 
                               value="• Reminders to reply to messages\n• Cooldown notifications\n• Duplicate reply warnings", 
                               inline=False)
            else:
                embed.title = "🔕 Quest Feedback Disabled"
                embed.description = f"{ctx.author.mention}, quest feedback messages are now turned off."
                embed.add_field(name="Note:", 
                               value="You can still complete quests, but won't get guidance tips.", 
                               inline=False)
            
            embed.set_footer(text="Use -q feedback again to toggle this setting")
            await ctx.reply(embed=embed, mention_author=False)
            
        except Exception as e:
            logger.error(f"Error in quest feedback command: {e}")
            await ctx.reply("An error occurred while toggling feedback settings.", mention_author=False)

    @staticmethod
    def read_shop_file(filename):
        with open(filename, "r", encoding="utf-8") as file:
            shop_data = json.load(file)
        return shop_data
        
class Quest_Slash(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.quest_data = Quest_Data(bot)
        super().__init__()

    async def check_server_quest_limit(self, guild_id: int) -> bool:
        """
        Check if the server has reached its quest limit.
        """
        server_quest_count = await self.quest_data.get_server_quest_count(guild_id)
        server_quest_limit = await self.quest_data.get_quest_limit(guild_id)
        if server_quest_count >= server_quest_limit:
            return False
        return True

    quest_group = app_commands.Group(
        name="quest", description="Quest related commands")

    @quest_group.command(
        name="create",
        description="Create a new quest.",
    )
    @app_commands.describe(action="The action to perform for the quest.")
    @app_commands.describe(method="The method to use for the quest.")
    @app_commands.describe(content="The content for the quest.")
    @app_commands.choices(
        action=[
            discord.app_commands.Choice(name="send", value="send"),
            discord.app_commands.Choice(name="receive", value="receive"),
        ]
    )
    @app_commands.choices(
        method=[
            discord.app_commands.Choice(name="message", value="message"),
            discord.app_commands.Choice(name="reaction", value="reaction"),
            discord.app_commands.Choice(name="emoji", value="emoji"),
        ]
    )
    async def create_quest(
        self,
        interaction: discord.Interaction,
        action: discord.app_commands.Choice[str],
        method: discord.app_commands.Choice[str],
        channel: discord.TextChannel,
        content: str,
        times: typing.Optional[int] = 1,
    ) -> None:
        try:
            
            if any(mention in content for mention in ["<@", "<@&"]):
                await interaction.response.send_message(
                    "Content cannot contain user or role mentions.", ephemeral=True
                )
                return

            guild_id = str(interaction.guild_id)
            user_id = str(interaction.user.id)
            user = interaction.user

            
            quest_id = await self.quest_data.create_quest(
                guild_id,
                action.value,
                method.value,
                content,
                channel.id,
                times,
                0,
                interaction,
            )
            if quest_id is not None:
                
                embed = await QuestEmbed.create_quest_embed(
                    self.bot,
                    "Created",
                    quest_id,
                    action.value,
                    method.value,
                    channel,
                    times=times,
                    content=content,
                    user=user,
                )

                
                await interaction.response.send_message(embed=embed)
                logger.debug("Quest creation successful.")
            else:
                await interaction.response.send_message(
                    "Try doing `.quest`", ephemeral=True
                )
                logger.debug("Failed to create the quest.")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(self.bot, interaction, e, title="Quest Creation")

    @quest_group.command(
        name="delete",
        description="Delete a quest by its ID.",
    )
    async def delete_quest(
        self, interaction: discord.Interaction, quest_id: int
    ) -> None:
        try:
            guild_id = interaction.guild.id

            
            users_in_guild = await self.quest_data.find_users_in_server(guild_id)

            if not users_in_guild:
                await interaction.response.send_message(
                    "No users found in the server.", ephemeral=True
                )
                return

            quest_deleted = False

            for user_id in users_in_guild:
                
                quest_exists = await self.quest_data.find_users_with_quest(
                    guild_id, quest_id
                )
                if quest_exists:
                    
                    await self.quest_data.delete_quest(guild_id, quest_id)
                    quest_deleted = True

            if quest_deleted:
                await interaction.response.send_message(
                    f"The quest with ID {quest_id} has been deleted for all users who had it.",
                    ephemeral=True,
                ) 
            else:
                await interaction.response.send_message(
                    "The specified quest does not exist for any user.", ephemeral=True
                )

        except Exception as e:
            print(f"An error occurred: {e}")
            traceback.print_exc()
            await self.quest_data.handle_error(interaction, e, title="Quest Deletion")

    @quest_group.command(
        name="removeall",
        description="Remove all server quests from every member.",
    )
    async def remove_all_server_quests(self, interaction: discord.Interaction) -> None:
        try:
            guild_id = str(interaction.guild_id)

            
            await self.quest_data.remove_all_server_quests(guild_id)

            await interaction.response.send_message(
                "All server quests have been removed from every member.", ephemeral=True
            )
            logger.debug("All server quests removed successfully.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await self.quest_data.handle_error(
                interaction, e, title="Remove All Server Quests"
            )

    @quest_group.command(
        name="setlimit",
        description="Set the maximum number of quests a user can have.",
    )
    async def set_quest_limit(
        self, interaction: discord.Interaction, limit: int
    ) -> None:
        try:
            guild_id = str(interaction.guild_id)

            
            await self.quest_data.set_quest_limit(guild_id, limit)

            await interaction.response.send_message(
                f"Quest limit set to {limit} for this server.", ephemeral=True
            )
            logger.debug("Quest limit updated successfully.")
        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await error_custom_embed(
                self.bot, interaction, e, title="Quest Limit Update"
            )

    @quest_group.command(
        name="serverquest",
        description="View all quests created for the server.",
    )
    async def view_all_server_quests(self, interaction: discord.Interaction) -> None:
        try:
            guild_id = str(interaction.guild_id)

            quests = await self.quest_data.server_quests(guild_id)

            embed = discord.Embed(
                title=f"All Server Quests for Server {guild_id}", color=0x7289DA
            )

            for quest_data in quests:
                embed.add_field(
                    name=f"Quest ID: {quest_data['quest_id']}",
                    value=f"**Action:** {quest_data['action']}\n"
                    f"**Method:** {quest_data['method']}\n"
                    f"**Content:** {quest_data['content']}\n"
                    f"**Channel ID:** {quest_data['channel_id']}\n"
                    f"**Times:** {quest_data['times']}\n"
                    f"**Reward:** {quest_data['reward']}\n",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)
            logger.debug("Viewed all server quests successfully.")

        except Exception as e:
            logger.error(f"An error occurred: {e}")
            traceback.print_exc()
            await self.quest_data.handle_error(
                interaction, e, title="View All Server Quests"
            )





# ═══════════════════════════════════════════════════════════════
# CHARACTER VIEW CLASSES - Moved from character.py
# ═══════════════════════════════════════════════════════════════
_REPO_ROOT = Path(__file__).resolve().parents[2]


class CharacterView(discord.ui.View):
    def __init__(self, bot: commands.Bot, quest_data: Quest_Data, ctx: commands.Context, char_id: str):
        super().__init__(timeout=120)
        self.bot = bot
        self.quest_data = quest_data
        self.ctx = ctx
        self.char_id = char_id

        self.message: discord.Message | None = None
        self.image_index: int = 0
        self.last_dialogue: str | None = None

        self.FEED_INTERVAL_SECONDS: int = 6 * 60 * 60  # 6 hours

        self._rebuild_components()

    def _rebuild_components(self) -> None:
        self.clear_items()
        self.add_item(CharacterImageSelect(self))
        self.add_item(InventoryButton())

    async def _get_bucket(self, category_key: str) -> dict:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.{category_key}": 1},
            )
            return (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("category_key", {})
            )
        except Exception:
            return {}

    async def _get_selected_character(self) -> str | None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("selected_character", {})
            )
        except Exception:
            bucket = {}
        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        return k
                except Exception:
                    continue
        return None

    async def _set_selected_character(self, char_id: str) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.selected_character": 1},
            )
            bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("selected_character", {})
        except Exception:
            bucket = {}

        if isinstance(bucket, dict):
            for k, v in bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character", k, -int(v))
                except Exception:
                    continue
        await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character", char_id, 1)

    async def _get_equipped_item(self) -> str | None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.equipped_items": 1},
            )
            bucket = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("equipped_items", {})
            )
        except Exception:
            bucket = {}

        if isinstance(bucket, dict):
            for k, v in bucket.items():
                if k == self.char_id:
                    try:
                        return str(v) if v else None
                    except Exception:
                        return None
        return None

    async def _set_equipped_item(self, item_name: str | None) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.equipped_items.{self.char_id}": item_name or ""}},
                upsert=True,
            )
        except Exception:
            return

    async def inventory_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        items_bucket = await self._get_bucket("items")
        meals_bucket = await self._get_bucket("meals")
        chars_bucket = await self._get_bucket("characters")
        equipped = await self._get_equipped_item()
        selected_char = await self._get_selected_character()

        items = []
        if isinstance(items_bucket, dict):
            for k, v in items_bucket.items():
                if isinstance(v, int) and v > 0:
                    items.append((k, v))
        items.sort(key=lambda t: (t[0].lower(), -t[1]))

        meals = []
        if isinstance(meals_bucket, dict):
            for k, v in meals_bucket.items():
                if isinstance(v, int) and v > 0:
                    meals.append((k, v))
        meals.sort(key=lambda t: (t[0].lower(), -t[1]))

        owned_chars: list[tuple[str, int]] = []
        if isinstance(chars_bucket, dict):
            for k, v in chars_bucket.items():
                if isinstance(v, int) and v > 0:
                    owned_chars.append((k, v))
        owned_chars.sort(key=lambda t: (t[0].lower(), -t[1]))

        current_char = get_character_def(selected_char or self.char_id)
        char_emoji = current_char.emoji if current_char else ""
        char_name = format_character_name(selected_char or self.char_id)

        items_embed = discord.Embed(
            title=f"🎒 {char_emoji} {char_name}'s Inventory",
            description=(
                f"**{char_emoji} {char_name}**\n"
                f"*{current_char.flavor_text if current_char else ''}*\n\n"
                f"Use the buttons below to manage your inventory.\n"
                f"Currently equipped: **{equipped or 'None'}**"
            ),
            color=discord.Color.blurple(),
        )
        if items:
            lines = [f"- **{name}** `x{qty}`" for name, qty in items[:20]]
            items_embed.add_field(name="Items", value="\n".join(lines), inline=False)
        else:
            items_embed.add_field(name="Items", value="No items.", inline=False)

        food_embed = discord.Embed(
            title="🍽️ Inventory - Food",
            description="Select a meal to feed (consumes 1).",
            color=discord.Color.green(),
        )
        if meals:
            lines = [f"- **{name}** `x{qty}`" for name, qty in meals[:20]]
            food_embed.add_field(name="Meals", value="\n".join(lines), inline=False)
        else:
            food_embed.add_field(name="Meals", value="No meals. Cook something first.", inline=False)

        inv_view = CharacterInventoryView(self, items=items, meals=meals, owned_chars=owned_chars, selected_char=selected_char)
        await interaction.response.send_message(
            embeds=[items_embed, food_embed],
            view=inv_view,
            ephemeral=True,
        )

    async def refresh_message(self) -> None:
        char_def = get_character_def(self.char_id)
        if not char_def:
            return

        hp, _ = await self._get_hp()
        self.image_index = await self._get_selected_image_index()

        next_feed_ts, _ = await self._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=self.ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=self.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
            dialogue_footer=self.last_dialogue,
        )
        if self.message:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await self.message.edit(embed=embed, view=self)

    async def _get_selected_image_index(self) -> int:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        idx = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.selected_character_image", self.char_id)
        try:
            return max(0, int(idx or 0))
        except Exception:
            return 0

    async def _set_selected_image_index(self, idx: int) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        current = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.selected_character_image", self.char_id)
        try:
            current = int(current or 0)
        except Exception:
            current = 0
        idx = max(0, int(idx))
        delta = idx - current
        if delta:
            await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.selected_character_image", self.char_id, delta)

    async def _get_hp(self) -> tuple[int, int]:
        char_def = get_character_def(self.char_id)
        if not char_def:
            return 0, 1

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        max_hp = max(1, int(char_def.base_hp))
        stored = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", self.char_id)
        hp = int(stored or max_hp)
        hp = max(0, min(hp, max_hp))
        return hp, max_hp

    async def _set_hp(self, hp: int):
        char_def = get_character_def(self.char_id)
        if not char_def:
            return

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        max_hp = max(1, int(char_def.base_hp))
        hp = max(0, min(int(hp), max_hp))

        current = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.character_hp", self.char_id)
        current = int(current or max_hp)
        delta = hp - current
        if delta:
            await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.character_hp", self.char_id, delta)

    async def refresh(self, interaction: discord.Interaction):
        char_def = get_character_def(self.char_id)
        if not char_def:
            if interaction.response.is_done():
                await interaction.followup.send("Character not found.", ephemeral=True)
            else:
                await interaction.response.send_message("Character not found.", ephemeral=True)
            return

        hp, _ = await self._get_hp()
        self.image_index = await self._get_selected_image_index()
        next_feed_ts, _ = await self._get_next_feed_info()
        embed, files = await build_character_embed_with_files(
            bot=self.bot,
            user=self.ctx.author,
            char_def=char_def,
            current_hp=hp,
            image_index=self.image_index,
            next_feed_ts=next_feed_ts,
            next_feed_in=None,
            dialogue_footer=self.last_dialogue,
        )

        if self.message and interaction.message and interaction.message.id != self.message.id:
            try:
                await self.message.edit(embed=embed, view=self, attachments=[], files=files)
            except TypeError:
                await self.message.edit(embed=embed, view=self)
            return

        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self, attachments=[], files=files)
            else:
                await interaction.response.edit_message(embed=embed, view=self, attachments=[], files=files)
        except TypeError:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)

    async def feed_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        char_def = get_character_def(self.char_id)
        if not char_def:
            return await interaction.followup.send("Character not found.", ephemeral=True)

        next_feed_ts, _ = await self._get_next_feed_info()
        if next_feed_ts is not None:
            now = int(time.time())
            if now < int(next_feed_ts):
                msg = await self._unique_not_hungry_dialogue(char_def)
                self.last_dialogue = msg
                await interaction.followup.send(
                    f"{char_def.emoji} **{self._display_name(char_def)}**: {msg}\n\nNext feed: <t:{int(next_feed_ts)}:R>",
                    ephemeral=True,
                )
                await self.refresh(interaction)
                return

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.meals": 1},
            )
            meal_bucket = (((doc or {}).get("members") or {}).get(user_id) or {}).get("inventory", {}).get("sxf", {}).get("meals", {})
        except Exception:
            meal_bucket = {}

        meal_name = None
        if isinstance(meal_bucket, dict):
            for k, v in meal_bucket.items():
                try:
                    if isinstance(v, int) and v > 0:
                        meal_name = k
                        break
                except Exception:
                    continue

        if not meal_name:
            return await interaction.followup.send("You have no meals to feed. Cook something first.", ephemeral=True)

        removed = await self.quest_data.remove_item_from_inventory(guild_id, user_id, "sxf.meals", meal_name, 1)
        if not removed:
            return await interaction.followup.send("Failed to consume a meal. Try again.", ephemeral=True)

        hp, max_hp = await self._get_hp()
        new_hp = min(max_hp, hp + max(1, int(max_hp * 0.15)))
        await self._set_hp(new_hp)

        await self._set_last_feed_ts(int(time.time()))

        quality = self._meal_quality_from_name(meal_name)
        base_quality = self._meal_base_quality_from_name(meal_name)
        fed_msg = self._dialogue_fed_with_base(
            char_def,
            meal_name=meal_name,
            quality=quality,
            base_quality=base_quality,
        )
        self.last_dialogue = fed_msg
        await interaction.followup.send(
            f"{char_def.emoji} **{self._display_name(char_def)}**: {fed_msg}\n\nAte: **{meal_name}**",
            ephemeral=True,
        )

        await self.refresh(interaction)

    def _display_name(self, char_def) -> str:
        try:
            return str(getattr(char_def, "char_id", "Character")).replace("-", " ").title()
        except Exception:
            return "Character"

    def _load_dialogue_config(self) -> dict:
        try:
            p = _REPO_ROOT / "data" / "commands" / "minigames" / "spy-x-family" / "character_dialogue.json"
            if not p.exists():
                return {}
            with p.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _dialogue_pool(self, char_def, key: str) -> list[str]:
        data = self._load_dialogue_config()
        cid = str(getattr(char_def, "char_id", "") or "")
        pool = []
        try:
            pool = (data.get(cid) or {}).get(key) or []
        except Exception:
            pool = []
        if not isinstance(pool, list) or not pool:
            try:
                pool = (data.get("_default") or {}).get(key) or []
            except Exception:
                pool = []
        return [str(x) for x in pool if isinstance(x, str) and x.strip()]

    def _render_dialogue_template(self, template: str, *, meal_name: str | None = None, quality: str | None = None) -> str:
        t = str(template or "").strip()
        if not t:
            return ""
        return (
            t.replace("{meal}", str(meal_name or "food"))
            .replace("{quality}", str((quality or "")).title() if quality else "")
            .strip()
        )

    def _meal_quality_from_name(self, meal_name: str) -> str | None:
        s = str(meal_name or "")
        for q in ("Perfect", "Great", "Good", "Bad", "Burnt"):
            if f"[{q}]" in s:
                return q.lower()
        return None

    def _meal_base_quality_from_name(self, meal_name: str) -> str | None:
        s = str(meal_name or "")
        if "|base:" not in s:
            return None
        try:
            inside = s.split("[", 1)[-1].split("]", 1)[0]
            parts = [p.strip() for p in inside.split("|") if p.strip()]
            for p in parts:
                if p.lower().startswith("base:"):
                    v = p.split(":", 1)[-1].strip().lower()
                    return v or None
        except Exception:
            return None
        return None

    def _normalize_base_quality(self, base_quality: str | None) -> str | None:
        if not base_quality:
            return None
        b = str(base_quality).strip().lower()
        if not b:
            return None
        if b in ("poor", "terrible", "trash"):
            return "poor"
        if b in ("okay", "ok", "average", "normal"):
            return "average"
        if b in ("good", "decent"):
            return "good"
        if b in ("great"):
            return "great"
        if b in ("excellent", "amazing", "premium"):
            return "excellent"
        return b

    async def _unique_not_hungry_dialogue(self, char_def) -> str:
        pool = self._dialogue_pool(char_def, "not_hungry")
        if not pool:
            return "I'm not hungry right now."

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        cid = str(getattr(char_def, "char_id", "") or "")

        used: list[int] = []
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.dialogue_used.not_hungry.{cid}": 1},
            )
            raw = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("dialogue_used", {})
                .get("not_hungry", {})
                .get(cid, [])
            )
            if isinstance(raw, list):
                used = [int(x) for x in raw if isinstance(x, int) or (isinstance(x, str) and str(x).isdigit())]
        except Exception:
            used = []

        used_set = {i for i in used if 0 <= i < len(pool)}
        remaining = [i for i in range(len(pool)) if i not in used_set]
        if not remaining:
            used_set = set()
            remaining = list(range(len(pool)))

        idx = remaining[0]
        used_set.add(idx)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.dialogue_used.not_hungry.{cid}": sorted(list(used_set))}},
                upsert=True,
            )
        except Exception:
            pass

        return pool[idx]

    def _dialogue_fed_with_base(self, char_def, *, meal_name: str | None = None, quality: str | None = None, base_quality: str | None = None) -> str:
        pool: list[str] = []
        if quality:
            pool = self._dialogue_pool(char_def, f"fed_{quality}")
        bq = self._normalize_base_quality(base_quality)
        if not pool and bq:
            pool = self._dialogue_pool(char_def, f"fed_base_{bq}")
        if not pool:
            pool = self._dialogue_pool(char_def, "fed")
        if not pool:
            return "Thanks!"
        chosen = random.choice(pool)
        q_for_tpl = quality or bq
        return self._render_dialogue_template(chosen, meal_name=meal_name, quality=q_for_tpl)

    async def _get_last_feed_ts(self) -> int | None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            doc = await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.inventory.sxf.last_feed_ts.{self.char_id}": 1},
            )
            ts = (
                (((doc or {}).get("members") or {}).get(user_id) or {})
                .get("inventory", {})
                .get("sxf", {})
                .get("last_feed_ts", {})
                .get(self.char_id)
            )
        except Exception:
            ts = None
        try:
            return int(ts) if ts is not None else None
        except Exception:
            return None

    async def _set_last_feed_ts(self, ts: int) -> None:
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.last_feed_ts.{self.char_id}": int(ts)}},
                upsert=True,
            )
        except Exception:
            return

    async def _get_next_feed_info(self) -> tuple[int | None, str | None]:
        last = await self._get_last_feed_ts()
        if not last:
            return None, "Feed now"
        nxt = int(last) + self.FEED_INTERVAL_SECONDS
        return nxt, None


class InventoryButton(discord.ui.Button['CharacterView']):
    def __init__(self):
        super().__init__(
            style=discord.ButtonStyle.secondary,
            label="Inventory",
            custom_id="character_inventory",
        )

    async def callback(self, interaction: discord.Interaction):
        if not getattr(self, "view", None) or not hasattr(self.view, "inventory_callback"):
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ This button is not properly configured.", ephemeral=True)
            return

        view: CharacterView = self.view  # type: ignore

        if interaction.user != view.ctx.author:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ This is not your character view.", ephemeral=True)
            return

        await view.inventory_callback(interaction)


class CharacterImageSelect(discord.ui.Select):
    def __init__(self, parent_view: CharacterView):
        self.parent_view = parent_view
        char_def = get_character_def(parent_view.char_id)
        options = []
        if char_def and getattr(char_def, "images", None):
            for i in range(min(25, len(char_def.images))):
                variant = None
                try:
                    if getattr(char_def, "image_variants", None) and i < len(char_def.image_variants):
                        variant = str(char_def.image_variants[i])
                except Exception:
                    variant = None
                label = variant or f"Image {i + 1}"
                options.append(
                    discord.SelectOption(
                        label=label[:100],
                        value=str(i),
                        description=(f"Use {label}" if variant else f"Use variant #{i + 1}")[:100],
                    )
                )

        super().__init__(
            placeholder="Select character image...",
            options=options or [discord.SelectOption(label="No images", value="0", description="This character has no images")],
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your character view.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        try:
            idx = int(self.values[0])
        except Exception:
            idx = 0

        await self.parent_view._set_selected_image_index(idx)
        await self.parent_view.refresh(interaction)


class CharacterInventoryView(discord.ui.View):
    def __init__(
        self,
        parent_view: CharacterView,
        items: list[tuple[str, int]],
        meals: list[tuple[str, int]],
        owned_chars: list[tuple[str, int]],
        selected_char: str | None = None,
    ):
        super().__init__(timeout=180)
        self.parent_view = parent_view
        self.items = items
        self.meals = meals
        self.owned_chars = owned_chars
        self.selected_char = selected_char or parent_view.char_id
        self.quest_data = parent_view.quest_data
        self.ctx = parent_view.ctx
        self.bot = parent_view.bot
        self._add_components()
        
    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        try:
            if hasattr(self, 'message'):
                await self.message.edit(view=self)
        except:
            pass

    def _add_components(self):
        self.add_item(NavigationButton("Characters", discord.ButtonStyle.primary, row=0))
        self.add_item(NavigationButton("Items", discord.ButtonStyle.secondary, row=0))
        self.add_item(NavigationButton("Meals", discord.ButtonStyle.success, row=0))


class NavigationButton(discord.ui.Button):
    def __init__(self, label: str, style: discord.ButtonStyle, row: int = 0):
        super().__init__(label=label, style=style, row=row)
        self.label = label
    
    async def callback(self, interaction: discord.Interaction):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
                
            if interaction.user != self.view.ctx.author:
                return await interaction.followup.send("This is not your inventory.", ephemeral=True)
            
            view = discord.ui.View(timeout=180)
            
            try:
                if self.label == "Characters":
                    if len(self.view.owned_chars) > 1:
                        view.add_item(CharacterSelectSelect(self.view))
                        message = "Select a character:"
                    else:
                        return await interaction.followup.send("You only have one character.", ephemeral=True)
                elif self.label == "Items":
                    view.add_item(CharacterEquipSelect(self.view))
                    message = "Select an item to equip:"
                elif self.label == "Meals":
                    view.add_item(CharacterFoodSelect(self.view))
                    message = "Select a meal to feed:"
                else:
                    return await interaction.followup.send("Unknown action.", ephemeral=True)
                
                await interaction.followup.send(message, view=view, ephemeral=True)
                
            except Exception:
                await interaction.followup.send("An error occurred while processing your request. Please try again.", ephemeral=True)
                
        except Exception:
            pass


class CharacterSelectSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = []
        for cid, _qty in (inv_view.owned_chars or [])[:25]:
            char_def = get_character_def(cid)
            if not char_def:
                continue
                
            char_name = ' '.join(word.capitalize() for word in cid.split('-'))
            emoji = char_def.emoji if char_def.emoji else "❔"
            
            label = f"{char_name}"[:100]
            
            is_selected = cid == (inv_view.selected_char or inv_view.parent_view.char_id)
            if is_selected:
                inv_view.selected_char = cid
                
            options.append(discord.SelectOption(
                label=label,
                value=cid,
                emoji=emoji,
                description="Currently selected" if is_selected else "Click to select"
            ))

        placeholder = "Select a character..."
        if inv_view.selected_char:
            char_def = get_character_def(inv_view.selected_char)
            if char_def:
                placeholder = f"Current: {inv_view.selected_char.replace('-', ' ').title()}"

        super().__init__(placeholder=placeholder, options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        cid = self.values[0]
        owned = await self.inv_view.parent_view.quest_data.get_user_inventory_count(
            str(self.inv_view.parent_view.ctx.guild.id),
            str(self.inv_view.parent_view.ctx.author.id),
            "sxf.characters",
            cid,
        )
        if (owned or 0) <= 0:
            return await interaction.followup.send("You don't own that character.", ephemeral=True)

        if not get_character_def(cid):
            return await interaction.followup.send("Character not found.", ephemeral=True)

        await self.inv_view.parent_view._set_selected_character(cid)
        self.inv_view.parent_view.char_id = cid
        
        self.inv_view.parent_view.image_index = 0
        await self.inv_view.parent_view._set_selected_image_index(0)
        
        self.inv_view.parent_view._rebuild_components()

        char_def = get_character_def(cid)
        if char_def:
            hp, _ = await self.inv_view.parent_view._get_hp()
            next_feed_ts, _ = await self.inv_view.parent_view._get_next_feed_info()
            
            embed, files = await build_character_embed_with_files(
                bot=self.inv_view.parent_view.bot,
                user=self.inv_view.parent_view.ctx.author,
                char_def=char_def,
                current_hp=hp,
                image_index=0,
                next_feed_ts=next_feed_ts,
                next_feed_in=None,
                dialogue_footer=self.inv_view.parent_view.last_dialogue,
            )
            
            if self.inv_view.parent_view.message:
                try:
                    channel = self.inv_view.parent_view.message.channel
                    await self.inv_view.parent_view.message.delete()
                    new_msg = await channel.send(embed=embed, view=self.inv_view.parent_view, files=files)
                    self.inv_view.parent_view.message = new_msg
                except Exception:
                    try:
                        await self.inv_view.parent_view.message.edit(embed=embed, view=self.inv_view.parent_view, attachments=files)
                    except Exception:
                        pass

            char_name = ' '.join(word.capitalize() for word in cid.split('-'))
            emoji = char_def.emoji if char_def.emoji else ""
            await interaction.followup.send(f"Selected character: {emoji} **{char_name}**", ephemeral=True)


class CharacterEquipSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = [discord.SelectOption(label="Unequip", value="__none__", description="Remove equipped item")]
        for name, qty in (inv_view.items or [])[:24]:
            options.append(
                discord.SelectOption(
                    label=str(name)[:100],
                    value=str(name),
                    description=f"x{qty}"[:100],
                )
            )

        super().__init__(placeholder="Equip item...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        val = self.values[0]
        item_name = None if val == "__none__" else val
        await self.inv_view.parent_view._set_equipped_item(item_name)

        await interaction.followup.send(f"Equipped: **{item_name or 'None'}**", ephemeral=True)


class CharacterFoodSelect(discord.ui.Select):
    def __init__(self, inv_view: CharacterInventoryView):
        self.inv_view = inv_view

        options = []
        for name, qty in (inv_view.meals or [])[:25]:
            options.append(
                discord.SelectOption(
                    label=str(name)[:100],
                    value=str(name),
                    description=f"x{qty}"[:100],
                )
            )

        super().__init__(
            placeholder="Feed meal...",
            options=options or [
                discord.SelectOption(label="No meals", value="__none__", description="Cook something first")
            ],
            row=2,
        )

    async def callback(self, interaction: discord.Interaction):
        if interaction.user != self.inv_view.parent_view.ctx.author:
            return await interaction.response.send_message("This is not your inventory.", ephemeral=True)

        val = self.values[0]
        if val == "__none__":
            return await interaction.response.send_message("No meals available.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        guild_id = str(self.inv_view.parent_view.ctx.guild.id)
        user_id = str(self.inv_view.parent_view.ctx.author.id)

        removed = await self.inv_view.parent_view.quest_data.remove_item_from_inventory(
            guild_id, user_id, "sxf.meals", val, 1
        )
        if not removed:
            return await interaction.followup.send("Failed to consume that meal.", ephemeral=True)

        hp, max_hp = await self.inv_view.parent_view._get_hp()
        new_hp = min(max_hp, hp + max(1, int(max_hp * 0.15)))
        await self.inv_view.parent_view._set_hp(new_hp)

        await interaction.followup.send(f"Fed **{val}**. HP is now `{new_hp}/{max_hp}`.", ephemeral=True)

        try:
            await self.inv_view.parent_view.refresh_message()
        except Exception:
            pass


def setup(bot):

    bot.add_cog(Quest_Data(bot))
    bot.add_cog(Quest(bot))
    bot.add_cog(Quest_Slash(bot))


class CookingRecipeSelectView(discord.ui.View):
    def __init__(self, bot, quest_data, ctx, owned_chars: list[dict]):
        super().__init__(timeout=120)
        self.bot = bot
        self.quest_data = quest_data
        self.ctx = ctx
        self.owned_chars = owned_chars or []

        self.selected_char_id: str | None = None
        self.selected_char_difficulty: str = "normal"

        self._recipes: list[dict] = []
        self._ingredient_emoji: dict[str, str] = {}
        self._ingredient_map: dict[str, dict] = {}
        self._cookable_recipes: list[dict] = []
        self._cookable_computed: bool = False
        self._owned_ingredients: dict[str, int] = {}

    @staticmethod
    def _sxf_data_path(*parts: str) -> str:
        return str(_REPO_ROOT / "data" / "commands" / "minigames" / "spy-x-family" / Path(*parts))

    def _load_ingredient_emoji(self) -> dict[str, str]:
        try:
            with open(self._sxf_data_path("ingredients.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}
        ingredient_emoji: dict[str, str] = {}
        if isinstance(data, dict):
            for group in data.values():
                if not isinstance(group, dict):
                    continue
                for ing_key, item in group.items():
                    if not isinstance(item, dict):
                        continue
                    emoji = item.get("emoji") or "🥕"
                    ingredient_emoji[str(ing_key).lower()] = emoji
                    name = item.get("name")
                    if name:
                        ingredient_emoji[str(name).lower()] = emoji
        return ingredient_emoji

    def _load_ingredient_map(self) -> dict[str, dict]:
        try:
            with open(self._sxf_data_path("ingredients.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}

        out: dict[str, dict] = {}
        # ingredients.json is grouped by category at top-level
        if isinstance(data, dict):
            for group in data.values():
                if not isinstance(group, dict):
                    continue
                for ing_key, item in group.items():
                    if not isinstance(item, dict):
                        continue
                    out[str(ing_key).lower()] = item
        return out

    def _ingredient_display_name(self, ing_key: str) -> str:
        item = (self._ingredient_map or {}).get(str(ing_key).lower())
        if isinstance(item, dict):
            nm = item.get("name")
            if isinstance(nm, str) and nm.strip():
                return nm.strip()
        return str(ing_key)

    def _ingredient_inventory_names(self, ing_key: str) -> list[str]:
        # backward compatible: some inventories stored by key, some by display name
        names = [str(ing_key).strip()]
        disp = self._ingredient_display_name(ing_key)
        if disp and disp not in names:
            names.append(disp)
        return [n for n in names if n]

    async def _fetch_all_ingredients(self) -> dict[str, int]:
        """Fetch all ingredients in one DB query and cache them."""
        if self._owned_ingredients:
            return self._owned_ingredients
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        try:
            self._owned_ingredients = await self.quest_data.get_user_inventory_category(
                guild_id, user_id, "sxf.ingredients"
            ) or {}
        except Exception:
            self._owned_ingredients = {}
        return self._owned_ingredients

    def _owned_ingredient_count_cached(self, ing_key: str) -> int:
        """Get ingredient count from cached inventory (must call _fetch_all_ingredients first)."""
        best = 0
        for nm in self._ingredient_inventory_names(ing_key):
            c = self._owned_ingredients.get(nm, 0)
            if isinstance(c, int) and c > best:
                best = c
        return best

    def _required_ingredients(self, recipe: dict) -> list[tuple[str, int]]:
        req = recipe.get("ingredients") or []
        out: list[tuple[str, int]] = []
        for ing in req:
            if isinstance(ing, dict):
                k = str(ing.get("item") or "").strip()
                a = int(ing.get("amount") or 1)
            else:
                k = str(ing).strip()
                a = 1
            if not k:
                continue
            out.append((k, max(1, a)))
        return out

    async def _get_cookable_recipes(self) -> list[dict]:
        # Return cached result if already computed
        if self._cookable_computed:
            return self._cookable_recipes

        if not self._recipes:
            self._recipes = self._load_recipes()
        if not self._ingredient_emoji:
            self._ingredient_emoji = self._load_ingredient_emoji()
        if not self._ingredient_map:
            self._ingredient_map = self._load_ingredient_map()

        # Fetch all ingredients in ONE DB query
        await self._fetch_all_ingredients()

        cookable: list[dict] = []
        for r in self._recipes:
            ok = True
            for ing_key, amt in self._required_ingredients(r):
                owned = self._owned_ingredient_count_cached(ing_key)
                if owned < amt:
                    ok = False
                    break
            if ok:
                cookable.append(r)

        self._cookable_recipes = cookable
        self._cookable_computed = True
        return cookable

    def _load_recipes(self) -> list[dict]:
        try:
            with open(self._sxf_data_path("recipes.json"), "r", encoding="utf-8") as f:
                recipes_data = json.load(f)
        except FileNotFoundError:
            return []

        flat: list[dict] = []
        if isinstance(recipes_data, dict):
            for section_name, section in recipes_data.items():
                if not isinstance(section, dict):
                    continue
                for recipe_id, recipe in section.items():
                    if not isinstance(recipe, dict):
                        continue
                    flat.append({"section": section_name, "id": recipe_id, **recipe})

        flat.sort(key=lambda r: (str(r.get("section") or ""), str(r.get("name") or r.get("id") or "")))
        return flat

    async def create_embed(self) -> discord.Embed:
        if not self._recipes:
            self._recipes = self._load_recipes()
        if not self._ingredient_map:
            self._ingredient_map = self._load_ingredient_map()

        cookable = await self._get_cookable_recipes()

        embed = discord.Embed(
            title="Cook a Meal",
            description="Pick a recipe number. (Showing recipes you can cook right now)",
            color=discord.Color.from_rgb(255, 182, 193),
            timestamp=datetime.now(),
        )
        try:
            if getattr(self.ctx.author, "avatar", None):
                embed.set_thumbnail(url=self.ctx.author.avatar.url)
        except Exception:
            pass

        def _diff_full_name(diff: str) -> str:
            s = str(diff or "normal").strip().lower()
            if s in ("easy", "e"):
                return "Easy"
            if s in ("hard", "h"):
                return "Hard"
            return "Normal"

        # Show current selected character only
        if self.selected_char_id:
            chosen = next((c for c in (self.owned_chars or []) if c.get("id") == self.selected_char_id), None)
            emoji = (chosen or {}).get("emoji") or "👥"
            diff = _diff_full_name((chosen or {}).get("cooking-difficulty") or self.selected_char_difficulty)
            chef_name = format_character_name(self.selected_char_id)
            embed.add_field(name="Chef", value=f"{emoji} **{chef_name}**\nDifficulty: **{diff}**", inline=False)
        else:
            embed.add_field(name="Chef", value="No character selected. Use `character select <id>` first.", inline=False)

        lines = []
        for i, r in enumerate((cookable or [])[:10]):
            name = r.get("name") or r.get("id") or "Unknown"
            emoji = r.get("emoji") or "🍽️"
            req = r.get("ingredients") or []
            preview = []
            for ing in req[:4]:
                if isinstance(ing, dict):
                    ing_key = str(ing.get("item") or "").strip()
                    amt = int(ing.get("amount") or 1)
                else:
                    ing_key = str(ing).strip()
                    amt = 1
                if not ing_key:
                    continue
                em = self._ingredient_emoji.get(ing_key.lower()) or "🥕"
                preview.append(f"{em}{amt}x")
            lines.append(f"`{i+1}.` {emoji} **{name}**  {' '.join(preview)}")

        embed.add_field(
            name="Recipes",
            value="\n".join(lines) if lines else "You can't cook anything yet. Buy ingredients in the cooking shop.",
            inline=False,
        )
        return embed

    async def update_view(self):
        self.clear_items()
        if not self._recipes:
            self._recipes = self._load_recipes()
        if not self._ingredient_map:
            self._ingredient_map = self._load_ingredient_map()

        cookable = await self._get_cookable_recipes()

        count = min(10, len(cookable or []))
        for i in range(count):
            row = 0 if i < 5 else 1
            btn = discord.ui.Button(
                style=discord.ButtonStyle.success,
                label=str(i + 1),
                custom_id=f"cook_recipe_{i}",
                row=row,
            )
            btn.callback = self.pick_recipe_callback
            self.add_item(btn)

    async def pick_recipe_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user != self.ctx.author:
                return await interaction.response.send_message("This is not your cooking session.", ephemeral=True)

            if not self.selected_char_id:
                if interaction.response.is_done():
                    return await interaction.followup.send("Select a character first with `character select <id>`.", ephemeral=True)
                return await interaction.response.send_message("Select a character first with `character select <id>`.", ephemeral=True)

            index = int(str(interaction.data["custom_id"]).split("_")[-1])

            # This callback can be slow (inventory checks, building views). Defer to avoid 3s expiry.
            if not interaction.response.is_done():
                await interaction.response.defer()

            cookable = await self._get_cookable_recipes()
            if index < 0 or index >= len(cookable or []):
                return await interaction.followup.send("Recipe not found.", ephemeral=True)

            recipe = cookable[index]
            game_view = CookingTimingGameView(
                self.bot,
                self.quest_data,
                self.ctx,
                recipe,
                character_id=self.selected_char_id,
                difficulty=self.selected_char_difficulty,
            )
            embed = await game_view.create_intro_embed()
            await game_view.start_round(interaction, embed)

        except Exception as e:
            traceback.print_exc()
            if interaction.response.is_done():
                await interaction.followup.send(f"Cooking error: `{e}`", ephemeral=True)
            else:
                await interaction.response.send_message(f"Cooking error: `{e}`", ephemeral=True)


class CookingTimingGameView(discord.ui.View):
    def __init__(self, bot, quest_data, ctx, recipe: dict, character_id: str, difficulty: str):
        super().__init__(timeout=180)
        self.bot = bot
        self.quest_data = quest_data
        self.ctx = ctx
        self.recipe = recipe
        self.character_id = character_id
        self.difficulty = str(difficulty or "normal").lower()

        self.round = 0
        # A short, fun loop: up to 5 rounds, or number of required ingredients if less
        self.total_rounds = 0
        self._start_ts: float | None = None
        self._reaction_times: list[float] = []
        self._ready = False

        self._correct_count = 0
        self._target_key: str | None = None
        self._round_time_limit = 2.0

        self._required_keys: list[str] = []

        self._ingredient_map: dict[str, dict] = {}

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        logger.error(
            f"Unhandled view error in {self.__class__.__name__} (user={getattr(interaction.user, 'id', None)} guild={getattr(interaction.guild, 'id', None)}): {error}",
            exc_info=True,
        )
        try:
            traceback.print_exception(type(error), error, error.__traceback__)
        except Exception:
            pass
        try:
            if interaction.response.is_done():
                await interaction.followup.send("❌ An error occurred while cooking. Please try again.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ An error occurred while cooking. Please try again.", ephemeral=True)
        except Exception:
            return

    def _required_ingredients(self) -> list[tuple[str, int]]:
        req = self.recipe.get("ingredients") or []
        parsed: list[tuple[str, int]] = []
        for ing in req:
            if isinstance(ing, dict):
                key = str(ing.get("item") or "").strip()
                amt = int(ing.get("amount") or 1)
            else:
                key = str(ing).strip()
                amt = 1
            if key:
                parsed.append((key, max(1, amt)))
        return parsed

    def _required_key_sequence(self) -> list[str]:
        # Sequential cooking: repeat ingredient keys based on required amount.
        out: list[str] = []
        for key, amt in self._required_ingredients():
            for _i in range(max(1, int(amt))):
                out.append(str(key))
        return out

    def _load_ingredient_map(self) -> dict[str, dict]:
        try:
            with open(Quest._sxf_data_path("ingredients.json"), "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return {}

        m: dict[str, dict] = {}
        if isinstance(data, dict):
            for group in data.values():
                if not isinstance(group, dict):
                    continue
                for key, item in group.items():
                    if not isinstance(item, dict):
                        continue
                    m[str(key).strip().lower()] = {"key": str(key).strip(), **item}
        return m

    def _ingredient_display_name(self, ing_key: str) -> str:
        item = (self._ingredient_map or {}).get(str(ing_key).lower())
        if not item:
            return ing_key
        return item.get("name") or ing_key

    def _ingredient_inventory_names(self, ing_key: str) -> list[str]:
        # Backward compatibility: old system stored by display name, new stores by key
        names = [ing_key]
        display = self._ingredient_display_name(ing_key)
        if display and display not in names:
            names.append(display)
        return names

    async def _owned_ingredient_count(self, ing_key: str) -> int:
        total = 0
        for n in self._ingredient_inventory_names(ing_key):
            total += (
                await self.quest_data.get_user_inventory_count(
                    str(self.ctx.guild.id), str(self.ctx.author.id), "sxf.ingredients", n
                )
                or 0
            )
        return total

    async def _build_requirements_lines(self) -> tuple[bool, list[str]]:
        if not self._ingredient_map:
            self._ingredient_map = self._load_ingredient_map()

        can_cook = True
        lines: list[str] = []
        for ing_key, amt in self._required_ingredients():
            owned = await self._owned_ingredient_count(ing_key)
            if owned < amt:
                can_cook = False
            display = self._ingredient_display_name(ing_key)
            lines.append(f"`{owned}/{amt}` {display}")
        return can_cook, lines

    async def _consume_ingredients(self) -> tuple[bool, str]:
        if not self._ingredient_map:
            self._ingredient_map = self._load_ingredient_map()

        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)

        # check first
        for ing_key, amt in self._required_ingredients():
            owned = await self._owned_ingredient_count(ing_key)
            if owned < amt:
                return False, f"Missing `{self._ingredient_display_name(ing_key)}` x{amt} (you have {owned})."

        # consume using key first, then display name if needed
        for ing_key, amt in self._required_ingredients():
            remaining = amt
            # try key
            key_owned = await self.quest_data.get_user_inventory_count(guild_id, user_id, "sxf.ingredients", ing_key)
            key_owned = key_owned or 0
            use_key = min(key_owned, remaining)
            if use_key > 0:
                ok = await self.quest_data.remove_item_from_inventory(guild_id, user_id, "sxf.ingredients", ing_key, use_key)
                if not ok:
                    return False, f"Failed to consume `{ing_key}` x{use_key}."
                remaining -= use_key

            if remaining > 0:
                display = self._ingredient_display_name(ing_key)
                if display != ing_key:
                    ok = await self.quest_data.remove_item_from_inventory(guild_id, user_id, "sxf.ingredients", display, remaining)
                    if not ok:
                        return False, f"Failed to consume `{display}` x{remaining}."
                    remaining = 0

        return True, ""

    async def create_intro_embed(self) -> discord.Embed:
        name = self.recipe.get("name") or self.recipe.get("id") or "Unknown"
        emoji = self.recipe.get("emoji") or "🍽️"
        can_cook, req_lines = await self._build_requirements_lines()

        # difficulty -> button count/time limit
        btn_count, time_limit = self._difficulty_settings()
        self._round_time_limit = time_limit
        self.total_rounds = min(5, max(1, len(self._required_ingredients())))

        embed = discord.Embed(
            title=f"🍳 Cooking: {emoji} {name}",
            description=(
                "Check your ingredients below. When you're ready, press **Start Cooking**.\n"
                f"Minigame: click the correct ingredient emoji. `buttons:` {btn_count} | `timer:` {time_limit:.1f}s"
            ),
            color=discord.Color.from_rgb(255, 182, 193),
            timestamp=datetime.now(),
        )
        try:
            if getattr(self.ctx.author, "avatar", None):
                embed.set_thumbnail(url=self.ctx.author.avatar.url)
        except Exception:
            pass
        embed.add_field(
            name=f"Ingredients ({'READY' if can_cook else 'MISSING'})",
            value="\n".join(req_lines) if req_lines else "None",
            inline=False,
        )
        embed.add_field(
            name="Chef",
            value=f"**{format_character_name(self.character_id)}**\nDifficulty: **{self.difficulty.title()}**",
            inline=False,
        )
        return embed

    async def start_round(self, interaction: discord.Interaction, embed: discord.Embed):
        # Don't consume yet; just block if missing so user can go buy ingredients.
        can_cook, _lines = await self._build_requirements_lines()
        if not can_cook:
            if interaction.response.is_done():
                return await interaction.followup.send(
                    "You're missing ingredients for that recipe. Buy them in the cooking shop first.",
                    ephemeral=True,
                )
            return await interaction.response.send_message(
                "You're missing ingredients for that recipe. Buy them in the cooking shop first.",
                ephemeral=True,
            )

        self.clear_items()
        self.round = 0
        self._reaction_times = []
        self._ready = False
        self._correct_count = 0

        self._required_keys = self._required_key_sequence()
        self.total_rounds = min(5, max(1, len(self._required_keys)))

        start_button = discord.ui.Button(
            style=discord.ButtonStyle.primary,
            label="Start Cooking",
            custom_id="cook_start",
            row=0,
        )
        start_button.callback = self.begin_callback
        self.add_item(start_button)

        # Caller may have deferred already; use a safe edit method.
        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            return

    async def begin_callback(self, interaction: discord.Interaction):
        try:
            if interaction.user != self.ctx.author:
                return await interaction.response.send_message("This is not your cooking session.", ephemeral=True)

            # Consuming ingredients + building the next round can take >3s.
            if not interaction.response.is_done():
                await interaction.response.defer()

            ok, msg = await self._consume_ingredients()
            if not ok:
                return await interaction.followup.send(msg, ephemeral=True)

            self.round = 0
            self._reaction_times = []
            self._correct_count = 0
            if not self._required_keys:
                self._required_keys = self._required_key_sequence()
            await self._start_next_pick_round(interaction)
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__}.begin_callback: {e}", exc_info=True)
            try:
                traceback.print_exc()
            except Exception:
                pass
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"Cooking error: `{e}`", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Cooking error: `{e}`", ephemeral=True)
            except Exception:
                return

    def _difficulty_settings(self) -> tuple[int, float]:
        # button_count (max 10), time limit per round
        # Time is based on BOTH meal difficulty and character skill.
        # User requirement: hard min reaction time should be 5-10s random.
        base_btn = {"none": 3, "easy": 5, "normal": 7, "hard": 10}.get(self.difficulty, 7)

        # Character skill proxy: Speed + AttackSpeed. Higher skill -> slightly lower time.
        char_def = get_character_def(self.character_id)
        speed = int(getattr(char_def, "speed", 0) or 0) if char_def else 0
        atk_spd = int(getattr(char_def, "attack_speed", 0) or 0) if char_def else 0
        skill = max(0, min(100, int(speed + atk_spd)))

        # Reduce time by up to 25% for very high skill.
        skill_mult = 1.0 - (0.25 * (skill / 100.0))

        if self.difficulty == "hard":
            # Hard: enforce 5-10s per round random.
            t = random.uniform(5.0, 10.0) * skill_mult
            t = max(5.0, t)
            return base_btn, float(t)

        # Other difficulties: reasonable windows.
        base_time = {
            "none": 10.0,
            "easy": 8.0,
            "normal": 7.0,
        }.get(self.difficulty, 7.0)
        t = base_time * skill_mult
        t = max(4.5, float(t))
        return base_btn, t

    async def _start_next_pick_round(self, interaction: discord.Interaction):
        # Sequential target: follow recipe order (with amounts expanded).
        if not self._required_keys:
            self._required_keys = self._required_key_sequence()
        if not self._required_keys:
            return await self.finish(interaction)

        btn_count, time_limit = self._difficulty_settings()
        self._round_time_limit = time_limit

        # Clamp round index and choose the next ingredient in sequence.
        idx = max(0, min(int(self.round), len(self._required_keys) - 1))
        self._target_key = str(self._required_keys[idx])

        # build options: target + decoys from all ingredients
        if not self._ingredient_map:
            self._ingredient_map = self._load_ingredient_map()
        pool = [k for k in (self._ingredient_map or {}).keys() if k and k.lower() != self._target_key.lower()]
        random.shuffle(pool)
        options = [self._target_key] + pool[: max(0, btn_count - 1)]
        random.shuffle(options)

        self.clear_items()
        self._ready = True
        self._start_ts = asyncio.get_running_loop().time()

        # create emoji-only buttons, max 10 across 2 rows
        for i, ing_key in enumerate(options[:10]):
            row = 0 if i < 5 else 1
            emoji = None
            try:
                # Use emoji from ingredients.json if available
                item = (self._ingredient_map or {}).get(str(ing_key).lower())
                emoji = (item or {}).get("emoji") if isinstance(item, dict) else None
            except Exception:
                emoji = None

            btn = discord.ui.Button(
                style=discord.ButtonStyle.secondary,
                label="",
                emoji=_safe_select_emoji(emoji) or "🥕",
                custom_id=f"cook_pick_{ing_key}",
                row=row,
            )
            btn.callback = self.pick_callback
            self.add_item(btn)

        # embed prompt
        disp = self._ingredient_display_name(self._target_key)
        embed = discord.Embed(
            title=f"🍳 Round {self.round + 1}/{self.total_rounds}",
            description=f"Click: **{disp}**  (time: {time_limit:.1f}s)",
            color=discord.Color.from_rgb(255, 182, 193),
            timestamp=datetime.now(),
        )
        try:
            if getattr(self.ctx.author, "avatar", None):
                embed.set_thumbnail(url=self.ctx.author.avatar.url)
        except Exception:
            pass

        # If they don't click in time, auto-fail the round
        async def _timeout_guard(expected_round: int):
            await asyncio.sleep(time_limit)
            if self.round != expected_round:
                return
            if not self._ready:
                return
            self._ready = False
            self._start_ts = None
            self.round += 1
            if self.round >= self.total_rounds:
                await self.finish(interaction)
                return
            await self._start_next_pick_round(interaction)

        asyncio.create_task(_timeout_guard(self.round))

        try:
            if interaction.response.is_done():
                await interaction.edit_original_response(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        except discord.NotFound:
            return

    async def pick_callback(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your cooking session.", ephemeral=True)
        if not self._ready or self._start_ts is None or not self._target_key:
            return await interaction.response.send_message("Too early.", ephemeral=True)

        picked = str(interaction.data["custom_id"]).split("cook_pick_", 1)[-1]
        now = asyncio.get_running_loop().time()
        rt = max(0.0, now - self._start_ts)

        self._ready = False
        self._start_ts = None

        correct = picked.lower() == self._target_key.lower()
        if correct:
            self._correct_count += 1
            self._reaction_times.append(rt)

        self.round += 1
        if self.round >= self.total_rounds:
            await self.finish(interaction)
            return

        # quick feedback, then next
        title = "✅ Correct" if correct else "❌ Wrong"
        await interaction.response.edit_message(
            embed=discord.Embed(
                title=f"{title} ({rt:.3f}s)",
                description="Next ingredient...",
                color=discord.Color.from_rgb(255, 182, 193),
                timestamp=datetime.now(),
            ),
            view=self,
        )
        await asyncio.sleep(random.uniform(0.4, 0.9))
        await self._start_next_pick_round(interaction)

    def _quality_from_performance(self, accuracy: float, avg_rt: float) -> tuple[str, float]:
        # speed_score 0..1
        speed_score = max(0.0, min(1.0, 1.0 - (avg_rt / max(0.5, self._round_time_limit))))
        score = max(0.0, min(1.0, accuracy * 0.7 + speed_score * 0.3))

        if score >= 0.92:
            return "Perfect", score
        if score >= 0.78:
            return "Great", score
        if score >= 0.60:
            return "Good", score
        if score >= 0.40:
            return "Bad", score
        return "Burnt", score

    async def finish(self, interaction: discord.Interaction):
        avg_rt = sum(self._reaction_times) / max(1, len(self._reaction_times)) if self._reaction_times else self._round_time_limit
        accuracy = self._correct_count / max(1, self.total_rounds)
        quality, score = self._quality_from_performance(accuracy, avg_rt)

        base_hp = self.recipe.get("hp-restore")
        if not isinstance(base_hp, int):
            base_hp = 10
        hp_final = max(1, int(base_hp * (0.5 + 0.75 * score)))

        # Store meal with a completion timer.
        guild_id = str(self.ctx.guild.id)
        user_id = str(self.ctx.author.id)
        meal_name = self.recipe.get("name") or self.recipe.get("id") or "Meal"
        meal_emoji = self.recipe.get("emoji") or "🍽️"
        base_quality = str(self.recipe.get("base-quality") or "").strip().lower() or "good"
        item_name = f"{meal_name} [{quality}|base:{base_quality}] +{hp_final}%"

        # Persist a "ready at" timestamp (seconds) for the cooked meal.
        # Default cook time: 2 minutes, scaled by difficulty.
        cook_seconds = {"none": 30, "easy": 60, "normal": 120, "hard": 240}.get(self.difficulty, 120)
        now_ts = int(time.time())
        ready_at = now_ts + int(cook_seconds)
        try:
            await self.quest_data.mongoConnect[self.quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {"$set": {f"members.{user_id}.inventory.sxf.pending_meals.{item_name}": ready_at}},
                upsert=True,
            )
        except Exception:
            # fallback: still give the meal immediately
            await self.quest_data.add_item_to_inventory(guild_id, user_id, "sxf.meals", item_name, 1)

        ready_text = "Ready" if ready_at <= now_ts else f"<t:{ready_at}:R>"

        char_def = get_character_def(self.character_id)
        chef_emoji = (char_def.emoji if char_def else "👨‍🍳")
        chef_name = format_character_name(self.character_id)

        embed = discord.Embed(
            title=f"{meal_emoji} Meal Cooked!",
            description=(
                f"**{meal_name}**\n"
                f"> Quality: **{quality}**\n"
                f"> Accuracy: **{int(accuracy*100)}%**\n"
                f"> Avg time: `{avg_rt:.3f}s`\n"
                f"> Meal HP: **+{hp_final}%**\n"
                f"> Status: **{ready_text}**"
            ),
            color=discord.Color.green(),
            timestamp=datetime.now(),
        )

        embed.add_field(
            name="Chef",
            value=f"{chef_emoji} **{chef_name}**\nDifficulty: **{self.difficulty.title()}**",
            inline=False,
        )

        # Meal emoji as thumbnail (nice visual even without custom art)
        try:
            # If it's a unicode emoji, Discord can't use it as an image URL; keep thumbnail unset.
            pass
        except Exception:
            pass

        # If the character has a local image, attach it and show as embed image.
        files = []
        try:
            if char_def and char_def.images:
                from utils.character_utils import _resolve_image_source

                url, f = _resolve_image_source(char_def.images[0], fallback_name=f"cook_{char_def.char_id}")
                if url:
                    embed.set_image(url=url)
                if f:
                    files.append(f)
        except Exception:
            files = []

        self.clear_items()
        try:
            if interaction.response.is_done():
                try:
                    await interaction.edit_original_response(embed=embed, view=None, attachments=[], files=files)
                except TypeError:
                    await interaction.edit_original_response(embed=embed, view=None)
            else:
                try:
                    await interaction.response.edit_message(embed=embed, view=None, attachments=[], files=files)
                except TypeError:
                    await interaction.response.edit_message(embed=embed, view=None)
        except discord.NotFound:
            return
