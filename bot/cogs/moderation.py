# Ban, Timeout, Note, Mod Log Config
from imports.discord_imports import *
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import timedelta
import os, asyncio
from typing import Optional, Literal


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = AsyncIOMotorClient(os.getenv("MONGO_URI"))["Commands"]["moderation"]

    # ---------------- Mod Log Channel ----------------
    @commands.command(name="log")
    @commands.has_permissions(manage_guild=True)
    async def set_log_channel(self, ctx, channel: discord.TextChannel):
        await self.db.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"log_channel": channel.id}},
            upsert=True
        )
        await ctx.reply(f"Mod log channel set to {channel.mention}")

    async def get_log_channel(self, guild: discord.Guild):
        config = await self.db.find_one({"guild_id": guild.id})
        if config and "log_channel" in config:
            return guild.get_channel(config["log_channel"])
        return None

    # ---------------- Purge ----------------
    @commands.group(name="purge", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx, amount: int):
        """Purge the last N messages from the channel."""
        if amount <= 0:
            return await ctx.reply("Amount must be positive.")
        if amount > 1000:
            amount = 1000  # Discord limit
        deleted = await ctx.channel.purge(limit=amount)
        embed = discord.Embed(
            title="Messages Purged",
            description=f"Purged {len(deleted)} messages.",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await msg.delete()
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    @purge.command(name="user")
    @commands.has_permissions(manage_messages=True)
    async def purge_user(self, ctx, member: discord.Member, amount: int):
        """Purge the last N messages from a specific user."""
        if amount <= 0:
            return await ctx.reply("Amount must be positive.")
        if amount > 1000:
            amount = 1000
        def is_user(m):
            return m.author == member
        deleted = await ctx.channel.purge(limit=amount, check=is_user)
        embed = discord.Embed(
            title="User Messages Purged",
            description=f"Purged {len(deleted)} messages from {member.mention}.",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await msg.delete()
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    @purge.command(name="bot")
    @commands.has_permissions(manage_messages=True)
    async def purge_bot(self, ctx, amount: int):
        """Purge the last N bot messages from the channel."""
        if amount <= 0:
            return await ctx.reply("Amount must be positive.")
        if amount > 1000:
            amount = 1000
        def is_bot(m):
            return m.author.bot
        deleted = await ctx.channel.purge(limit=amount, check=is_bot)
        embed = discord.Embed(
            title="Bot Messages Purged",
            description=f"Purged {len(deleted)} bot messages.",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        msg = await ctx.send(embed=embed)
        await asyncio.sleep(5)
        await msg.delete()
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    # ---------------- Ban ----------------
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: Optional[str] = None):
        await member.ban(reason=reason)
        embed = discord.Embed(
            title="Member Banned",
            description=f"{member.mention} was banned.\nReason: {reason or 'No reason provided.'}",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def unban(self, ctx, user: discord.User, *, reason: Optional[str] = None):
        await ctx.guild.unban(user, reason=reason)
        embed = discord.Embed(
            title="Member Unbanned",
            description=f"{user.mention} was unbanned.\nReason: {reason or 'No reason provided.'}",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    # ---------------- Timeout ----------------
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, time: str, *, reason: Optional[str] = None):
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        char = time[-1].lower()
        if char not in units:
            await ctx.reply("Invalid time format. Use s/m/h/d (e.g. 1h, 30m).")
            return
            
        try:
            duration = int(time[:-1]) * units[char]
        except ValueError:
             await ctx.reply("Invalid time format. Use s/m/h/d (e.g. 1h, 30m).")
             return

        until = discord.utils.utcnow() + timedelta(seconds=duration)
        await member.timeout(until, reason=reason)
        embed = discord.Embed(
            title="Member Timed Out",
            description=f"{member.mention} was timed out for {time}.\nReason: {reason or 'No reason provided.'}",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def untimeout(self, ctx, member: discord.Member, *, reason: Optional[str] = None):
        await member.timeout(None, reason=reason)
        embed = discord.Embed(
            title="Member Timeout Removed",
            description=f"{member.mention} timeout was removed.\nReason: {reason or 'No reason provided.'}",
        )
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        await ctx.reply(embed=embed)
        log_channel = await self.get_log_channel(ctx.guild)
        if log_channel:
            await log_channel.send(embed=embed)

    # ---------------- Notes ----------------
    @commands.group(name="notes", invoke_without_command=True)
    async def notes_group(self, ctx, member: discord.Member = None):
        """Manage notes for members and note-taker roles."""
        if member:
            roles = await self.get_notetaker_roles(ctx.guild)
            if roles and not any(r in ctx.author.roles for r in roles):
                await ctx.reply("You are not authorized to view notes.")
                return

            record = await self.db.find_one({"user_id": member.id, "guild_id": ctx.guild.id}) or {"notes": []}
            notes = record.get("notes", [])
            view = NoteView(self.db, member, ctx, notes)
            embed = view.format_page(0)
            embed.set_footer(text=f"Use {ctx.prefix}notes help for all commands")
            await ctx.reply(embed=embed, view=view)
        else:
            embed = discord.Embed(
                title="Notes Commands",
                description="Manage notes for members and configure note-taker roles.",
            )
            embed.add_field(
                name=f"{ctx.prefix}notes <member>",
                value="View notes for a member",
                inline=False
            )
            embed.add_field(
                name=f"{ctx.prefix}notes add <member> <note>",
                value="Add a note to a member",
                inline=False
            )
            embed.add_field(
                name=f"{ctx.prefix}notes config [roles...]",
                value="Configure note-taker roles (requires Manage Server)",
                inline=False
            )
            embed.add_field(
                name=f"{ctx.prefix}notes help",
                value="Show this help message",
                inline=False
            )
            embed.set_footer(text=f"Use {ctx.prefix}notes help for more details")
            await ctx.reply(embed=embed)

    @notes_group.command(name="add")
    async def add_note(self, ctx, member: discord.Member, *, note: str):
        """Add a note to a member."""
        roles = await self.get_notetaker_roles(ctx.guild)
        if roles and not any(r in ctx.author.roles for r in roles):
            await ctx.reply("You are not authorized to add notes.")
            return

        record = await self.db.find_one({"user_id": member.id, "guild_id": ctx.guild.id}) or {"notes": []}
        record["notes"].append({
            "notetaker": ctx.author.mention,
            "note": note,
            "timestamp": discord.utils.utcnow().isoformat(),
        })
        await self.db.update_one(
            {"user_id": member.id, "guild_id": ctx.guild.id},
            {"$set": record},
            upsert=True
        )
        confirm_msg = await ctx.reply(f"Note added for {member.mention}.")
        await asyncio.sleep(0.5)
        await confirm_msg.delete()
        await ctx.message.delete()

    @notes_group.command(name="view")
    async def view_notes(self, ctx, member: discord.Member):
        """View notes for a member."""
        roles = await self.get_notetaker_roles(ctx.guild)
        if roles and not any(r in ctx.author.roles for r in roles):
            await ctx.reply("You are not authorized to view notes.")
            return

        record = await self.db.find_one({"user_id": member.id, "guild_id": ctx.guild.id}) or {"notes": []}
        notes = record.get("notes", [])
        view = NoteView(self.db, member, ctx, notes)
        await ctx.reply(embed=view.format_page(0), view=view)

    @notes_group.command(name="help")
    async def notes_help(self, ctx):
        """Show detailed help for notes commands."""
        embed = discord.Embed(
            title="Notes System",
            description="Note-taking system for server moderation.",
        )
        embed.add_field(
            name=f"{ctx.prefix}notes <member>",
            value="View all notes for a specific member. Shows paginated results with timestamps and note-taker information.",
            inline=False
        )
        embed.add_field(
            name=f"{ctx.prefix}notes add <member> <note>",
            value="Add a note to a member's record. Only users with note-taker roles can add notes.",
            inline=False
        )
        embed.add_field(
            name=f"{ctx.prefix}notes config [roles...]",
            value="Configure which roles can add/view notes. Use without arguments to view current roles. Use 'clear' to remove all roles. Requires Manage Server permission.",
            inline=False
        )
        embed.set_footer(text="Notes are stored per-server and persist across sessions")
        await ctx.reply(embed=embed)

    @notes_group.command(name="config")
    @commands.has_permissions(manage_guild=True)
    async def config_notes(self, ctx, *roles: discord.Role):
        """Configure note-taker roles."""
        guild_id = ctx.guild.id
        config = await self.db.find_one({"guild_id": guild_id}) or {}
        existing_ids = config.get("note_taker_roles", [])

        if not roles:
            if not existing_ids:
                desc = "No note-taker roles configured."
            else:
                current_roles = [ctx.guild.get_role(rid) for rid in existing_ids if ctx.guild.get_role(rid)]
                desc = f"Current note-taker roles: {', '.join(r.mention for r in current_roles)}"

            embed = discord.Embed(description=desc)
            embed.set_footer(text=f"Use: {ctx.prefix}notes config @Role1 @Role2 to add roles | {ctx.prefix}notes config clear to remove all")
            return await ctx.reply(embed=embed)
        
        if "clear" in [r.name.lower() for r in roles]:
            await self.db.update_one(
                {"guild_id": guild_id},
                {"$unset": {"note_taker_roles": ""}}
            )
            await ctx.reply("Cleared all note-taker roles.")
            return
        
        role_ids = [r.id for r in roles]
        await self.db.update_one(
            {"guild_id": guild_id},
            {"$addToSet": {"note_taker_roles": {"$each": role_ids}}},
            upsert=True
        )
        await ctx.reply(f"Added note-taker roles: {', '.join(r.mention for r in roles)}")

    async def get_notetaker_roles(self, guild: discord.Guild):
        config = await self.db.find_one({"guild_id": guild.id})
        if config and "note_taker_roles" in config:
            return [guild.get_role(rid) for rid in config["note_taker_roles"] if guild.get_role(rid)]
        return []

class NoteView(discord.ui.View):
    def __init__(self, db, member, ctx, notes):
        super().__init__(timeout=180)
        self.db = db
        self.member = member
        self.ctx = ctx
        self.page = 0
        self.pages = [notes[i:i+5] for i in range(0, len(notes), 5)] or [[]]
        self.total_pages = len(self.pages)
        self.show_delete_menu = False
        self.update_view()

    def format_page(self, page_idx):
        page = self.pages[page_idx]
        desc = "\n\n".join(f"{n['notetaker']}: {n['note']}" for n in page) or "No notes yet."
        embed = discord.Embed(
            title=f"{self.member.display_name}'s Notes",
            description=desc,
        )
        embed.set_thumbnail(url=self.member.display_avatar.url)
        embed.set_footer(text=f"Page {page_idx + 1}/{self.total_pages}")
        return embed

    def update_view(self):
        self.clear_items()
        
        # Check if current page has notes
        page_notes = self.pages[self.page]
        has_notes = page_notes and page_notes != [{}] and len(page_notes) > 0
        
        # Add pagination buttons only if multiple pages exist
        if self.total_pages > 1:
            # Previous button (only if not on first page)
            if self.page > 0:
                prev_btn = discord.ui.Button(style=discord.ButtonStyle.gray, label="<", row=0)
                prev_btn.callback = self.previous_callback
                self.add_item(prev_btn)
            
            # Next button (only if not on last page)
            if self.page < self.total_pages - 1:
                next_btn = discord.ui.Button(style=discord.ButtonStyle.gray, label=">", row=0)
                next_btn.callback = self.next_callback
                self.add_item(next_btn)
        
        # Delete button (only if notes exist and not in delete mode)
        if has_notes and not self.show_delete_menu:
            delete_btn = discord.ui.Button(style=discord.ButtonStyle.red, label="Delete", row=1)
            delete_btn.callback = self.delete_callback
            self.add_item(delete_btn)
        
        # Cancel button (only in delete mode)
        if self.show_delete_menu:
            cancel_btn = discord.ui.Button(style=discord.ButtonStyle.secondary, label="Cancel", row=1)
            cancel_btn.callback = self.cancel_callback
            self.add_item(cancel_btn)
            
            # Add select menu for deletion
            if has_notes:
                options = [
                    discord.SelectOption(
                        label=f"{i+1}: {n['notetaker']}",
                        description=n['note'][:100],
                        value=str(i)
                    )
                    for i, n in enumerate(page_notes)
                ]
                if options:
                    self.add_item(self.note_select(options))

    async def previous_callback(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.update_view()
            await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    async def next_callback(self, interaction: discord.Interaction):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_view()
            await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    async def delete_callback(self, interaction: discord.Interaction):
        self.show_delete_menu = True
        self.update_view()
        await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    async def cancel_callback(self, interaction: discord.Interaction):
        self.show_delete_menu = False
        self.update_view()
        await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    class note_select(discord.ui.Select):
        def __init__(self, options):
            super().__init__(placeholder="Select notes to delete...", min_values=1, max_values=len(options), options=options)

        async def callback(self, interaction: discord.Interaction):
            idxs = [int(v) for v in self.values]
            page_notes = self.view.pages[self.view.page]
            for i in sorted(idxs, reverse=True):
                page_notes.pop(i)
            all_notes = [n for pg in self.view.pages for n in pg]
            await self.view.db.update_one(
                {"user_id": self.view.member.id, "guild_id": self.view.ctx.guild.id},
                {"$set": {"notes": all_notes}},
                upsert=True
            )
            self.view.pages = [all_notes[i:i+5] for i in range(0, len(all_notes), 5)] or [[]]
            self.view.total_pages = len(self.view.pages)
            if self.view.page >= self.view.total_pages:
                self.view.page = max(0, self.view.total_pages - 1)
            self.view.show_delete_menu = False
            self.view.update_view()
            await interaction.response.edit_message(embed=self.view.format_page(self.view.page), view=self.view)