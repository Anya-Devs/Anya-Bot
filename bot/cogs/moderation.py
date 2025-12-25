# Comprehensive Moderation System
# Commands: mod, warn, kick, ban, unban, timeout, mute, unmute, purge, slowmode, lock, unlock, role, cases, notes, log
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import timedelta, datetime, timezone
import os, asyncio, re
from typing import Optional, Literal, Union
from utils.cogs.moderation import (
    ModerationDB, ModerationEmbeds, ModerationViews, 
    ModerationUtils, RoleManagement
)
from data.local.const import primary_color


class Moderation(commands.Cog):
    """🔨 Server Moderation - Complete moderation toolkit for server management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.mod_db = ModerationDB()
        self.legacy_db = AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["moderation"]

    async def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the mod log channel for a guild"""
        return await self.mod_db.get_log_channel(guild)

    async def log_action(self, guild: discord.Guild, embed: discord.Embed):
        """Send an embed to the mod log channel if configured"""
        log_channel = await self.get_log_channel(guild)
        if log_channel:
            try:
                await log_channel.send(embed=embed)
            except discord.Forbidden:
                pass

    # ═══════════════════════════════════════════════════════════════
    # MOD GROUP - Main moderation command hub
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="mod", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def mod_group(self, ctx):
        """🔨 Moderation command hub - View all moderation commands"""
        embed = discord.Embed(
            title="Moderation Commands",
            description="Complete server moderation toolkit",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="User Actions",
            value=f"`{ctx.prefix}warn` - Warn a member\n"
                  f"`{ctx.prefix}kick` - Kick a member\n"
                  f"`{ctx.prefix}ban` - Ban a member\n"
                  f"`{ctx.prefix}unban` - Unban a user\n"
                  f"`{ctx.prefix}timeout` - Timeout a member\n"
                  f"`{ctx.prefix}mute` - Mute a member\n"
                  f"`{ctx.prefix}unmute` - Unmute a member",
            inline=True
        )
        
        embed.add_field(
            name="Channel Management",
            value=f"`{ctx.prefix}purge` - Delete messages\n"
                  f"`{ctx.prefix}slowmode` - Set slowmode\n"
                  f"`{ctx.prefix}lock` - Lock a channel\n"
                  f"`{ctx.prefix}unlock` - Unlock a channel\n"
                  f"`{ctx.prefix}nuke` - Clone & delete channel",
            inline=True
        )
        
        embed.add_field(
            name="Configuration",
            value=f"`{ctx.prefix}mod log` - Set log channel\n"
                  f"`{ctx.prefix}mod muterole` - Set mute role\n"
                  f"`{ctx.prefix}mod cases` - View mod cases\n"
                  f"`{ctx.prefix}notes` - Manage user notes",
            inline=True
        )
        
        embed.add_field(
            name="Role Management",
            value=f"`{ctx.prefix}role add` - Add role to user\n"
                  f"`{ctx.prefix}role remove` - Remove role from user\n"
                  f"`{ctx.prefix}role all` - Add role to everyone\n"
                  f"`{ctx.prefix}role bots` - Add role to all bots\n"
                  f"`{ctx.prefix}role humans` - Add role to all humans",
            inline=True
        )
        
        embed.set_footer(text=f"Use {ctx.prefix}help <command> for more details")
        await ctx.reply(embed=embed, mention_author=False)

    @mod_group.command(name="log")
    @commands.has_permissions(manage_guild=True)
    async def mod_log(self, ctx, channel: discord.TextChannel = None):
        """Set or view the moderation log channel"""
        if channel is None:
            current = await self.get_log_channel(ctx.guild)
            if current:
                embed = discord.Embed(
                    description=f"📋 Current mod log channel: {current.mention}",
                    color=primary_color()
                )
            else:
                embed = discord.Embed(
                    description=f"📋 No mod log channel set. Use `{ctx.prefix}mod log #channel` to set one.",
                    color=discord.Color.orange()
                )
            return await ctx.reply(embed=embed, mention_author=False)
        
        await self.mod_db.set_config(ctx.guild.id, "log_channel", channel.id)
        embed = discord.Embed(
            title="✅ Mod Log Channel Set",
            description=f"Moderation actions will now be logged to {channel.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @mod_group.command(name="muterole")
    @commands.has_permissions(manage_guild=True)
    async def mod_muterole(self, ctx, role: discord.Role = None):
        """Set or view the mute role"""
        if role is None:
            config = await self.mod_db.get_config(ctx.guild.id)
            role_id = config.get("mute_role")
            if role_id:
                mute_role = ctx.guild.get_role(role_id)
                if mute_role:
                    return await ctx.reply(f"📋 Current mute role: {mute_role.mention}", mention_author=False)
            return await ctx.reply(f"📋 No mute role set. Use `{ctx.prefix}mod muterole @Role` to set one.", mention_author=False)
        
        await self.mod_db.set_config(ctx.guild.id, "mute_role", role.id)
        await ctx.reply(f"✅ Mute role set to {role.mention}", mention_author=False)

    @mod_group.command(name="cases")
    @commands.has_permissions(manage_messages=True)
    async def mod_cases(self, ctx, member: discord.Member = None):
        """View moderation cases for the server or a specific user"""
        cases = await self.mod_db.get_cases(ctx.guild.id, member.id if member else None, limit=50)
        
        if not cases:
            desc = f"No moderation cases found" + (f" for {member.mention}" if member else "")
            embed = discord.Embed(description=desc, color=discord.Color.orange())
            return await ctx.reply(embed=embed, mention_author=False)
        
        view = ModerationViews.CasesPaginator(cases, ctx.guild, ctx.author)
        await ctx.reply(embed=view.build_embed(), view=view, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # WARN COMMAND
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="warn", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """⚠️ Warn a member"""
        can_mod, msg = ModerationUtils.can_moderate(ctx.author, member)
        if not can_mod:
            return await ctx.reply(f"❌ {msg}", mention_author=False)
        
        warn_count = await self.mod_db.add_warning(ctx.guild.id, member.id, ctx.author.id, reason)
        case_num = await self.mod_db.add_case(ctx.guild.id, "warn", member.id, ctx.author.id, reason)
        
        embed = ModerationEmbeds.action_embed(
            "Warning", member, ctx.author, reason, case_num=case_num
        )
        embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
        
        # Try to DM the user
        dm_embed = discord.Embed(
            title=f"⚠️ Warning in {ctx.guild.name}",
            description=f"**Reason:** {reason}",
            color=discord.Color.yellow()
        )
        dm_embed.add_field(name="Total Warnings", value=str(warn_count), inline=True)
        dm_sent = await ModerationUtils.send_dm(member, dm_embed)
        
        if not dm_sent:
            embed.set_footer(text=f"Case #{case_num} • Could not DM user")
        
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @warn.command(name="list")
    @commands.has_permissions(manage_messages=True)
    async def warn_list(self, ctx, member: discord.Member):
        """View all warnings for a member"""
        warnings = await self.mod_db.get_warnings(ctx.guild.id, member.id)
        embed = ModerationEmbeds.warnings_embed(member, warnings, ctx.guild)
        await ctx.reply(embed=embed, mention_author=False)

    @warn.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def warn_clear(self, ctx, member: discord.Member):
        """Clear all warnings for a member"""
        count = await self.mod_db.clear_warnings(ctx.guild.id, member.id)
        embed = discord.Embed(
            title="✅ Warnings Cleared",
            description=f"Cleared **{count}** warning(s) for {member.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @warn.command(name="remove")
    @commands.has_permissions(manage_guild=True)
    async def warn_remove(self, ctx, member: discord.Member, index: int):
        """Remove a specific warning by index (1-based)"""
        success = await self.mod_db.remove_warning(ctx.guild.id, member.id, index - 1)
        if success:
            embed = discord.Embed(
                title="✅ Warning Removed",
                description=f"Removed warning #{index} from {member.mention}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Could not find warning #{index} for {member.mention}",
                color=discord.Color.red()
            )
        await ctx.reply(embed=embed, mention_author=False)

    # ═══════════════════════════════════════════════════════════════
    # KICK COMMAND
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """👢 Kick a member from the server"""
        can_mod, msg = ModerationUtils.can_moderate(ctx.author, member)
        if not can_mod:
            return await ctx.reply(f"❌ {msg}", mention_author=False)
        
        # DM before kick
        dm_embed = discord.Embed(
            title=f"👢 Kicked from {ctx.guild.name}",
            description=f"**Reason:** {reason}",
            color=discord.Color.orange()
        )
        await ModerationUtils.send_dm(member, dm_embed)
        
        await member.kick(reason=f"{ctx.author}: {reason}")
        case_num = await self.mod_db.add_case(ctx.guild.id, "kick", member.id, ctx.author.id, reason)
        
        embed = ModerationEmbeds.action_embed("Kick", member, ctx.author, reason, case_num=case_num)
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    # ═══════════════════════════════════════════════════════════════
    # BAN / UNBAN COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: Union[discord.Member, discord.User], *, reason: str = "No reason provided"):
        """🔨 Ban a member from the server"""
        if isinstance(member, discord.Member):
            can_mod, msg = ModerationUtils.can_moderate(ctx.author, member)
            if not can_mod:
                return await ctx.reply(f"❌ {msg}", mention_author=False)
            
            # DM before ban
            dm_embed = discord.Embed(
                title=f"🔨 Banned from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=discord.Color.red()
            )
            await ModerationUtils.send_dm(member, dm_embed)
        
        await ctx.guild.ban(member, reason=f"{ctx.author}: {reason}", delete_message_days=0)
        case_num = await self.mod_db.add_case(ctx.guild.id, "ban", member.id, ctx.author.id, reason)
        
        embed = ModerationEmbeds.action_embed("Ban", member, ctx.author, reason, case_num=case_num)
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @commands.command(name="unban")
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, reason: str = "No reason provided"):
        """🔓 Unban a user from the server"""
        try:
            await ctx.guild.unban(user, reason=f"{ctx.author}: {reason}")
            case_num = await self.mod_db.add_case(ctx.guild.id, "unban", user.id, ctx.author.id, reason)
            
            embed = ModerationEmbeds.action_embed("Unban", user, ctx.author, reason, case_num=case_num)
            await ctx.reply(embed=embed, mention_author=False)
            await self.log_action(ctx.guild, embed)
        except discord.NotFound:
            await ctx.reply("❌ This user is not banned.", mention_author=False)

    @commands.command(name="softban")
    @commands.has_permissions(ban_members=True)
    async def softban(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """🔨 Softban (ban + unban) to delete messages"""
        can_mod, msg = ModerationUtils.can_moderate(ctx.author, member)
        if not can_mod:
            return await ctx.reply(f"❌ {msg}", mention_author=False)
        
        await ctx.guild.ban(member, reason=f"Softban by {ctx.author}: {reason}", delete_message_days=7)
        await ctx.guild.unban(member, reason="Softban unban")
        case_num = await self.mod_db.add_case(ctx.guild.id, "softban", member.id, ctx.author.id, reason)
        
        embed = ModerationEmbeds.action_embed("Softban", member, ctx.author, reason, case_num=case_num)
        embed.description = "User was banned and unbanned to delete their messages."
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    # ═══════════════════════════════════════════════════════════════
    # TIMEOUT / MUTE COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="timeout")
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, duration: str, *, reason: str = "No reason provided"):
        """⏰ Timeout a member (e.g., 1h, 30m, 7d)"""
        can_mod, msg = ModerationUtils.can_moderate(ctx.author, member)
        if not can_mod:
            return await ctx.reply(f"❌ {msg}", mention_author=False)
        
        td = ModerationUtils.parse_duration(duration)
        if not td:
            return await ctx.reply("❌ Invalid duration. Use format like `1h`, `30m`, `7d`", mention_author=False)
        
        if td > timedelta(days=28):
            return await ctx.reply("❌ Maximum timeout duration is 28 days.", mention_author=False)
        
        until = discord.utils.utcnow() + td
        await member.timeout(until, reason=f"{ctx.author}: {reason}")
        case_num = await self.mod_db.add_case(ctx.guild.id, "timeout", member.id, ctx.author.id, reason)
        
        duration_str = ModerationUtils.format_duration(td)
        embed = ModerationEmbeds.action_embed("Timeout", member, ctx.author, reason, duration=duration_str, case_num=case_num)
        
        # DM user
        dm_embed = discord.Embed(
            title=f"⏰ Timed out in {ctx.guild.name}",
            description=f"**Duration:** {duration_str}\n**Reason:** {reason}",
            color=discord.Color.dark_gray()
        )
        await ModerationUtils.send_dm(member, dm_embed)
        
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @commands.command(name="untimeout", aliases=["removetimeout"])
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """⏰ Remove timeout from a member"""
        await member.timeout(None, reason=f"{ctx.author}: {reason}")
        case_num = await self.mod_db.add_case(ctx.guild.id, "untimeout", member.id, ctx.author.id, reason)
        
        embed = ModerationEmbeds.action_embed("Timeout Removed", member, ctx.author, reason, case_num=case_num)
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @commands.command(name="mute")
    @commands.has_permissions(manage_roles=True)
    async def mute(self, ctx, member: discord.Member, duration: str = None, *, reason: str = "No reason provided"):
        """🔇 Mute a member using mute role"""
        can_mod, msg = ModerationUtils.can_moderate(ctx.author, member)
        if not can_mod:
            return await ctx.reply(f"❌ {msg}", mention_author=False)
        
        config = await self.mod_db.get_config(ctx.guild.id)
        mute_role_id = config.get("mute_role")
        
        if not mute_role_id:
            return await ctx.reply(f"❌ No mute role set. Use `{ctx.prefix}mod muterole @Role` first.", mention_author=False)
        
        mute_role = ctx.guild.get_role(mute_role_id)
        if not mute_role:
            return await ctx.reply("❌ Mute role not found. Please reconfigure.", mention_author=False)
        
        await member.add_roles(mute_role, reason=f"{ctx.author}: {reason}")
        case_num = await self.mod_db.add_case(ctx.guild.id, "mute", member.id, ctx.author.id, reason)
        
        duration_str = None
        if duration:
            td = ModerationUtils.parse_duration(duration)
            if td:
                duration_str = ModerationUtils.format_duration(td)
                # Schedule unmute
                await asyncio.sleep(td.total_seconds())
                if mute_role in member.roles:
                    await member.remove_roles(mute_role, reason="Mute duration expired")
        
        embed = ModerationEmbeds.action_embed("Mute", member, ctx.author, reason, duration=duration_str, case_num=case_num)
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @commands.command(name="unmute")
    @commands.has_permissions(manage_roles=True)
    async def unmute(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        """🔊 Unmute a member"""
        config = await self.mod_db.get_config(ctx.guild.id)
        mute_role_id = config.get("mute_role")
        
        if not mute_role_id:
            return await ctx.reply(f"❌ No mute role set.", mention_author=False)
        
        mute_role = ctx.guild.get_role(mute_role_id)
        if not mute_role or mute_role not in member.roles:
            return await ctx.reply("❌ This member is not muted.", mention_author=False)
        
        await member.remove_roles(mute_role, reason=f"{ctx.author}: {reason}")
        case_num = await self.mod_db.add_case(ctx.guild.id, "unmute", member.id, ctx.author.id, reason)
        
        embed = ModerationEmbeds.action_embed("Unmute", member, ctx.author, reason, case_num=case_num)
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    # ═══════════════════════════════════════════════════════════════
    # PURGE COMMANDS
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="purge", aliases=["clear", "prune"], invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """🗑️ Delete messages from the channel"""
        if amount <= 0:
            return await ctx.reply("❌ Amount must be positive.", mention_author=False)
        if amount > 1000:
            amount = 1000
        
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount)
        
        embed = discord.Embed(
            title="🗑️ Messages Purged",
            description=f"Deleted **{len(deleted)}** messages",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass
        
        await self.log_action(ctx.guild, embed)

    @purge.command(name="user")
    @commands.has_permissions(manage_messages=True)
    async def purge_user(self, ctx, member: discord.Member, amount: int = 100):
        """Delete messages from a specific user"""
        if amount > 1000:
            amount = 1000
        
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author == member)
        
        embed = discord.Embed(
            title="🗑️ User Messages Purged",
            description=f"Deleted **{len(deleted)}** messages from {member.mention}",
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

    @purge.command(name="bots")
    @commands.has_permissions(manage_messages=True)
    async def purge_bots(self, ctx, amount: int = 100):
        """Delete bot messages"""
        if amount > 1000:
            amount = 1000
        
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: m.author.bot)
        
        embed = discord.Embed(
            title="🗑️ Bot Messages Purged",
            description=f"Deleted **{len(deleted)}** bot messages",
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

    @purge.command(name="embeds")
    @commands.has_permissions(manage_messages=True)
    async def purge_embeds(self, ctx, amount: int = 100):
        """Delete messages with embeds"""
        if amount > 1000:
            amount = 1000
        
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: len(m.embeds) > 0)
        
        embed = discord.Embed(
            title="🗑️ Embed Messages Purged",
            description=f"Deleted **{len(deleted)}** messages with embeds",
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

    @purge.command(name="images")
    @commands.has_permissions(manage_messages=True)
    async def purge_images(self, ctx, amount: int = 100):
        """Delete messages with attachments"""
        if amount > 1000:
            amount = 1000
        
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: len(m.attachments) > 0)
        
        embed = discord.Embed(
            title="🗑️ Image Messages Purged",
            description=f"Deleted **{len(deleted)}** messages with attachments",
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

    @purge.command(name="contains")
    @commands.has_permissions(manage_messages=True)
    async def purge_contains(self, ctx, text: str, amount: int = 100):
        """Delete messages containing specific text"""
        if amount > 1000:
            amount = 1000
        
        await ctx.message.delete()
        deleted = await ctx.channel.purge(limit=amount, check=lambda m: text.lower() in m.content.lower())
        
        embed = discord.Embed(
            title="🗑️ Messages Purged",
            description=f"Deleted **{len(deleted)}** messages containing `{text}`",
            color=discord.Color.green()
        )
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except:
            pass

    # ═══════════════════════════════════════════════════════════════
    # CHANNEL MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode(self, ctx, seconds: int = 0, channel: discord.TextChannel = None):
        """🐌 Set slowmode for a channel (0 to disable)"""
        channel = channel or ctx.channel
        
        if seconds < 0 or seconds > 21600:
            return await ctx.reply("❌ Slowmode must be between 0 and 21600 seconds (6 hours).", mention_author=False)
        
        await channel.edit(slowmode_delay=seconds)
        
        if seconds == 0:
            embed = discord.Embed(
                title="🐌 Slowmode Disabled",
                description=f"Slowmode has been disabled in {channel.mention}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="🐌 Slowmode Set",
                description=f"Slowmode set to **{seconds}** seconds in {channel.mention}",
                color=discord.Color.green()
            )
        
        await ctx.reply(embed=embed, mention_author=False)

    @commands.command(name="lock")
    @commands.has_permissions(manage_channels=True)
    async def lock(self, ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
        """🔒 Lock a channel"""
        channel = channel or ctx.channel
        
        await channel.set_permissions(ctx.guild.default_role, send_messages=False, reason=f"{ctx.author}: {reason}")
        
        embed = discord.Embed(
            title="🔒 Channel Locked",
            description=f"{channel.mention} has been locked.\n**Reason:** {reason}",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @commands.command(name="unlock")
    @commands.has_permissions(manage_channels=True)
    async def unlock(self, ctx, channel: discord.TextChannel = None, *, reason: str = "No reason provided"):
        """🔓 Unlock a channel"""
        channel = channel or ctx.channel
        
        await channel.set_permissions(ctx.guild.default_role, send_messages=None, reason=f"{ctx.author}: {reason}")
        
        embed = discord.Embed(
            title="🔓 Channel Unlocked",
            description=f"{channel.mention} has been unlocked.\n**Reason:** {reason}",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        await ctx.reply(embed=embed, mention_author=False)
        await self.log_action(ctx.guild, embed)

    @commands.command(name="nuke")
    @commands.has_permissions(manage_channels=True)
    async def nuke(self, ctx):
        """💥 Clone and delete channel (reset all messages)"""
        view = ModerationViews.ConfirmAction(ctx.author)
        
        embed = discord.Embed(
            title="⚠️ Confirm Channel Nuke",
            description=f"This will **delete** {ctx.channel.mention} and create an identical copy.\n"
                        f"All messages will be permanently lost.\n\n"
                        f"**Are you sure?**",
            color=discord.Color.red()
        )
        
        msg = await ctx.reply(embed=embed, view=view, mention_author=False)
        await view.wait()
        
        if view.value is None:
            embed.title = "⏰ Timed Out"
            embed.description = "Nuke cancelled - no response received."
            embed.color = discord.Color.orange()
            return await msg.edit(embed=embed, view=None)
        
        if not view.value:
            embed.title = "❌ Cancelled"
            embed.description = "Channel nuke has been cancelled."
            embed.color = discord.Color.green()
            return await msg.edit(embed=embed, view=None)
        
        # Perform nuke
        new_channel = await ctx.channel.clone(reason=f"Channel nuked by {ctx.author}")
        await ctx.channel.delete(reason=f"Channel nuked by {ctx.author}")
        
        embed = discord.Embed(
            title="💥 Channel Nuked",
            description=f"Channel has been reset by {ctx.author.mention}",
            color=discord.Color.red()
        )
        await new_channel.send(embed=embed)

    # ═══════════════════════════════════════════════════════════════
    # ROLE MANAGEMENT
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="role", invoke_without_command=True)
    @commands.has_permissions(manage_roles=True)
    async def role_group(self, ctx):
        """Role management commands"""
        embed = discord.Embed(
            title="Role Commands",
            description=f"`{ctx.prefix}role add @user @role` - Add role to user\n"
                        f"`{ctx.prefix}role remove @user @role` - Remove role from user\n"
                        f"`{ctx.prefix}role all @role` - Add role to everyone\n"
                        f"`{ctx.prefix}role bots @role` - Add role to all bots\n"
                        f"`{ctx.prefix}role humans @role` - Add role to all humans\n"
                        f"`{ctx.prefix}role removeall @role` - Remove role from everyone",
            color=primary_color()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @role_group.command(name="add")
    @commands.has_permissions(manage_roles=True)
    async def role_add(self, ctx, member: discord.Member, role: discord.Role, *, reason: str = "No reason"):
        """Add a role to a member"""
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply("❌ You cannot assign a role equal to or higher than your top role.", mention_author=False)
        
        if role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I cannot assign a role equal to or higher than my top role.", mention_author=False)
        
        await member.add_roles(role, reason=f"{ctx.author}: {reason}")
        
        embed = discord.Embed(
            title="✅ Role Added",
            description=f"Added {role.mention} to {member.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @role_group.command(name="remove")
    @commands.has_permissions(manage_roles=True)
    async def role_remove(self, ctx, member: discord.Member, role: discord.Role, *, reason: str = "No reason"):
        """Remove a role from a member"""
        if role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.reply("❌ You cannot remove a role equal to or higher than your top role.", mention_author=False)
        
        await member.remove_roles(role, reason=f"{ctx.author}: {reason}")
        
        embed = discord.Embed(
            title="✅ Role Removed",
            description=f"Removed {role.mention} from {member.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @role_group.command(name="all")
    @commands.has_permissions(administrator=True)
    async def role_all(self, ctx, role: discord.Role):
        """Add a role to all members"""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I cannot assign this role.", mention_author=False)
        
        msg = await ctx.reply("⏳ Adding role to all members...", mention_author=False)
        
        count = 0
        for member in ctx.guild.members:
            if role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Mass role add by {ctx.author}")
                    count += 1
                except:
                    pass
        
        embed = discord.Embed(
            title="✅ Mass Role Add Complete",
            description=f"Added {role.mention} to **{count}** members",
            color=discord.Color.green()
        )
        await msg.edit(content=None, embed=embed)

    @role_group.command(name="bots")
    @commands.has_permissions(administrator=True)
    async def role_bots(self, ctx, role: discord.Role):
        """Add a role to all bots"""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I cannot assign this role.", mention_author=False)
        
        msg = await ctx.reply("⏳ Adding role to all bots...", mention_author=False)
        
        count = 0
        for member in ctx.guild.members:
            if member.bot and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Bot role add by {ctx.author}")
                    count += 1
                except:
                    pass
        
        embed = discord.Embed(
            title="✅ Bot Role Add Complete",
            description=f"Added {role.mention} to **{count}** bots",
            color=discord.Color.green()
        )
        await msg.edit(content=None, embed=embed)

    @role_group.command(name="humans")
    @commands.has_permissions(administrator=True)
    async def role_humans(self, ctx, role: discord.Role):
        """Add a role to all humans"""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I cannot assign this role.", mention_author=False)
        
        msg = await ctx.reply("⏳ Adding role to all humans...", mention_author=False)
        
        count = 0
        for member in ctx.guild.members:
            if not member.bot and role not in member.roles:
                try:
                    await member.add_roles(role, reason=f"Human role add by {ctx.author}")
                    count += 1
                except:
                    pass
        
        embed = discord.Embed(
            title="✅ Human Role Add Complete",
            description=f"Added {role.mention} to **{count}** humans",
            color=discord.Color.green()
        )
        await msg.edit(content=None, embed=embed)

    @role_group.command(name="removeall")
    @commands.has_permissions(administrator=True)
    async def role_removeall(self, ctx, role: discord.Role):
        """Remove a role from all members"""
        if role >= ctx.guild.me.top_role:
            return await ctx.reply("❌ I cannot remove this role.", mention_author=False)
        
        msg = await ctx.reply("⏳ Removing role from all members...", mention_author=False)
        
        count = 0
        for member in ctx.guild.members:
            if role in member.roles:
                try:
                    await member.remove_roles(role, reason=f"Mass role remove by {ctx.author}")
                    count += 1
                except:
                    pass
        
        embed = discord.Embed(
            title="✅ Mass Role Remove Complete",
            description=f"Removed {role.mention} from **{count}** members",
            color=discord.Color.green()
        )
        await msg.edit(content=None, embed=embed)

    # ═══════════════════════════════════════════════════════════════
    # NOTES SYSTEM (kept from original)
    # ═══════════════════════════════════════════════════════════════
    @commands.group(name="notes", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def notes_group(self, ctx, member: discord.Member = None):
        """📝 Manage notes for members"""
        if member:
            warnings = await self.mod_db.get_warnings(ctx.guild.id, member.id)
            embed = ModerationEmbeds.warnings_embed(member, warnings, ctx.guild)
            embed.title = f"Notes for {member.display_name}"
            await ctx.reply(embed=embed, mention_author=False)
        else:
            embed = discord.Embed(
                title="Notes Commands",
                description=f"`{ctx.prefix}notes @member` - View notes for a member\n"
                            f"`{ctx.prefix}notes add @member <note>` - Add a note\n"
                            f"`{ctx.prefix}notes clear @member` - Clear all notes",
                color=primary_color()
            )
            await ctx.reply(embed=embed, mention_author=False)

    @notes_group.command(name="add")
    @commands.has_permissions(manage_messages=True)
    async def notes_add(self, ctx, member: discord.Member, *, note: str):
        """Add a note to a member"""
        await self.mod_db.add_warning(ctx.guild.id, member.id, ctx.author.id, f"[NOTE] {note}")
        
        embed = discord.Embed(
            title="Note Added",
            description=f"Added note for {member.mention}:\n```{note}```",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed, mention_author=False)

    @notes_group.command(name="clear")
    @commands.has_permissions(manage_guild=True)
    async def notes_clear(self, ctx, member: discord.Member):
        """Clear all notes for a member"""
        count = await self.mod_db.clear_warnings(ctx.guild.id, member.id)
        
        embed = discord.Embed(
            title="📝 Notes Cleared",
            description=f"Cleared **{count}** note(s) for {member.mention}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed, mention_author=False)


async def setup(bot):
    await bot.add_cog(Moderation(bot))
