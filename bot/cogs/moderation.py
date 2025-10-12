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

    # ---------------- Timeout ----------------
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def timeout(self, ctx, member: discord.Member, *, time: str, reason: Optional[str]=None):
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        duration = int(time[:-1]) * units.get(time[-1], 1)
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

    # ---------------- Note-Taker Roles Config ----------------
    @commands.group(name="notetaker", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def notetaker(self, ctx):
        roles = await self.get_notetaker_roles(ctx.guild)
        if not roles:
            await ctx.reply("No note-taker roles configured.")
        else:
            await ctx.reply(f"Current note-taker roles: {', '.join(r.mention for r in roles)}")

    @notetaker.command(name="add")
    async def add_notetaker(self, ctx, *roles: discord.Role):
        role_ids = [r.id for r in roles]
        await self.db.update_one(
            {"guild_id": ctx.guild.id},
            {"$addToSet": {"note_taker_roles": {"$each": role_ids}}},
            upsert=True
        )
        await ctx.reply(f"Added note-taker roles: {', '.join(r.mention for r in roles)}")

    @notetaker.command(name="overwrite")
    async def overwrite_notetaker(self, ctx, *roles: discord.Role):
        role_ids = [r.id for r in roles]
        await self.db.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"note_taker_roles": role_ids}},
            upsert=True
        )
        await ctx.reply(f"Overwritten note-taker roles: {', '.join(r.mention for r in roles)}")

    @notetaker.command(name="clear")
    async def clear_notetaker(self, ctx):
        await self.db.update_one(
            {"guild_id": ctx.guild.id},
            {"$unset": {"note_taker_roles": ""}}
        )
        await ctx.reply("Cleared all note-taker roles.")

    async def get_notetaker_roles(self, guild: discord.Guild):
        config = await self.db.find_one({"guild_id": guild.id})
        if config and "note_taker_roles" in config:
            return [guild.get_role(rid) for rid in config["note_taker_roles"] if guild.get_role(rid)]
        return []

    # ---------------- Note ----------------
    @commands.command()
    async def note(
        self,
        ctx,
        member: discord.Member,
        *,
        note: Optional[str] = None,
        mode: Optional[Literal["notetaker"]] = None,
        role: Optional[discord.Role] = None,
    ):
        roles = await self.get_notetaker_roles(ctx.guild)
        if roles and not any(r in ctx.author.roles for r in roles):
            await ctx.reply("You are not authorized to add/view notes.")
            return

        record = await self.db.find_one({"user_id": member.id, "guild_id": ctx.guild.id}) or {"notes": []}

        # Add note
        if note:
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
            return

        # Show notes (paginated)
        notes = record.get("notes", [])
        view = NoteView(self.db, member, ctx, notes)
        await ctx.reply(embed=view.format_page(0), view=view)

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
        # Pagination buttons
        if self.page > 0:
            self.add_item(self.previous)
        if self.page < self.total_pages - 1:
            self.add_item(self.next)
        # Delete button as a "gateway"
        self.add_item(self.delete_button)
        # Cancel button
        if self.show_delete_menu:
            self.add_item(self.cancel_button)
            options = [
                discord.SelectOption(
                    label=f"{i+1}: {n['notetaker']}",
                    description=n['note'][:100],
                    value=str(i)
                )
                for i, n in enumerate(self.pages[self.page])
            ]
            if options:
                self.add_item(self.note_select(options))

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
            self.view.update_view()
            await interaction.response.edit_message(embed=self.view.format_page(self.view.page), view=self.view)

    @discord.ui.button(style=discord.ButtonStyle.red, label="Delete", row=1)
    async def delete_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.show_delete_menu = True
        self.update_view()
        await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, label="Cancel", row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.show_delete_menu = False
        self.update_view()
        await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, label="<", row=0)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_view()
            await interaction.response.edit_message(embed=self.format_page(self.page), view=self)

    @discord.ui.button(style=discord.ButtonStyle.gray, label=">", row=0)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_view()
            await interaction.response.edit_message(embed=self.format_page(self.page), view=self)