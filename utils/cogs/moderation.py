"""
Moderation Utilities - Comprehensive moderation system for Discord servers
Includes: warnings, kicks, bans, mutes, slowmode, lockdown, role management, and logging
"""

import os
import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List, Dict, Any, Literal
from motor.motor_asyncio import AsyncIOMotorClient
from imports.discord_imports import *
from data.local.const import primary_color


class ModerationDB:
    """Database handler for moderation data"""
    
    def __init__(self):
        self.client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
        self.db = self.client["Commands"]["moderation"]
        self.warnings_db = self.client["Commands"]["warnings"]
        self.cases_db = self.client["Commands"]["mod_cases"]
    
    async def get_config(self, guild_id: int) -> dict:
        """Get server moderation config"""
        config = await self.db.find_one({"guild_id": guild_id})
        return config or {}
    
    async def set_config(self, guild_id: int, key: str, value: Any) -> bool:
        """Set a config value"""
        await self.db.update_one(
            {"guild_id": guild_id},
            {"$set": {key: value}},
            upsert=True
        )
        return True
    
    async def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """Get the mod log channel for a guild"""
        config = await self.get_config(guild.id)
        if config and "log_channel" in config:
            return guild.get_channel(config["log_channel"])
        return None
    
    async def add_warning(self, guild_id: int, user_id: int, mod_id: int, reason: str) -> int:
        """Add a warning and return the warning count"""
        await self.warnings_db.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$push": {"warnings": {
                "mod_id": mod_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }}},
            upsert=True
        )
        doc = await self.warnings_db.find_one({"guild_id": guild_id, "user_id": user_id})
        return len(doc.get("warnings", []))
    
    async def get_warnings(self, guild_id: int, user_id: int) -> List[dict]:
        """Get all warnings for a user"""
        doc = await self.warnings_db.find_one({"guild_id": guild_id, "user_id": user_id})
        return doc.get("warnings", []) if doc else []
    
    async def clear_warnings(self, guild_id: int, user_id: int) -> int:
        """Clear all warnings for a user, return count cleared"""
        doc = await self.warnings_db.find_one({"guild_id": guild_id, "user_id": user_id})
        count = len(doc.get("warnings", [])) if doc else 0
        await self.warnings_db.delete_one({"guild_id": guild_id, "user_id": user_id})
        return count
    
    async def remove_warning(self, guild_id: int, user_id: int, index: int) -> bool:
        """Remove a specific warning by index"""
        doc = await self.warnings_db.find_one({"guild_id": guild_id, "user_id": user_id})
        if not doc or "warnings" not in doc:
            return False
        warnings = doc["warnings"]
        if index < 0 or index >= len(warnings):
            return False
        warnings.pop(index)
        await self.warnings_db.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": {"warnings": warnings}}
        )
        return True
    
    async def add_case(self, guild_id: int, case_type: str, user_id: int, mod_id: int, reason: str) -> int:
        """Add a moderation case and return case number"""
        result = await self.cases_db.find_one_and_update(
            {"guild_id": guild_id},
            {"$inc": {"case_count": 1}},
            upsert=True,
            return_document=True
        )
        case_num = result.get("case_count", 1)
        
        await self.cases_db.update_one(
            {"guild_id": guild_id},
            {"$push": {"cases": {
                "case_num": case_num,
                "type": case_type,
                "user_id": user_id,
                "mod_id": mod_id,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }}}
        )
        return case_num
    
    async def get_cases(self, guild_id: int, user_id: int = None, limit: int = 10) -> List[dict]:
        """Get moderation cases, optionally filtered by user"""
        doc = await self.cases_db.find_one({"guild_id": guild_id})
        if not doc:
            return []
        cases = doc.get("cases", [])
        if user_id:
            cases = [c for c in cases if c.get("user_id") == user_id]
        return cases[-limit:]


class ModerationEmbeds:
    """Embed builders for moderation actions"""
    
    @staticmethod
    def action_embed(
        action: str,
        user: Union[discord.Member, discord.User],
        moderator: discord.Member,
        reason: str = None,
        duration: str = None,
        case_num: int = None,
        color: discord.Color = None
    ) -> discord.Embed:
        """Create a standard moderation action embed"""
        colors = {
            "warn": discord.Color.yellow(),
            "kick": discord.Color.orange(),
            "ban": discord.Color.red(),
            "unban": discord.Color.green(),
            "mute": discord.Color.dark_gray(),
            "unmute": discord.Color.green(),
            "timeout": discord.Color.dark_gray(),
            "untimeout": discord.Color.green(),
        }
        
        embed = discord.Embed(
            title=f"🔨 {action.title()}",
            color=color or colors.get(action.lower(), primary_color()),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(name="User", value=f"{user.mention} (`{user.id}`)", inline=True)
        embed.add_field(name="Moderator", value=moderator.mention, inline=True)
        
        if duration:
            embed.add_field(name="Duration", value=duration, inline=True)
        
        embed.add_field(
            name="Reason",
            value=reason or "No reason provided",
            inline=False
        )
        
        if case_num:
            embed.set_footer(text=f"Case #{case_num}")
        
        embed.set_thumbnail(url=user.display_avatar.url)
        return embed
    
    @staticmethod
    def warnings_embed(user: discord.Member, warnings: List[dict], guild: discord.Guild) -> discord.Embed:
        """Create warnings list embed"""
        embed = discord.Embed(
            title=f"⚠️ Warnings for {user.display_name}",
            color=discord.Color.yellow(),
            timestamp=datetime.now(timezone.utc)
        )
        
        if not warnings:
            embed.description = "This user has no warnings."
        else:
            for i, warn in enumerate(warnings, 1):
                mod = guild.get_member(warn.get("mod_id"))
                mod_name = mod.display_name if mod else "Unknown Moderator"
                timestamp = warn.get("timestamp", "Unknown")
                if isinstance(timestamp, str):
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        timestamp = f"<t:{int(dt.timestamp())}:R>"
                    except:
                        pass
                
                embed.add_field(
                    name=f"Warning #{i}",
                    value=f"**Reason:** {warn.get('reason', 'No reason')}\n"
                          f"**By:** {mod_name}\n"
                          f"**When:** {timestamp}",
                    inline=False
                )
        
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"Total: {len(warnings)} warning(s)")
        return embed


class ModerationViews:
    """Interactive views for moderation"""
    
    class ConfirmAction(discord.ui.View):
        """Confirmation view for dangerous actions"""
        
        def __init__(self, author: discord.Member, timeout: float = 30):
            super().__init__(timeout=timeout)
            self.author = author
            self.value = None
        
        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                return await interaction.response.send_message("This isn't your confirmation!", ephemeral=True)
            self.value = True
            self.stop()
            await interaction.response.defer()
        
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                return await interaction.response.send_message("This isn't your confirmation!", ephemeral=True)
            self.value = False
            self.stop()
            await interaction.response.defer()
    
    class CasesPaginator(discord.ui.View):
        """Paginated view for moderation cases"""
        
        def __init__(self, cases: List[dict], guild: discord.Guild, author: discord.Member, per_page: int = 5):
            super().__init__(timeout=120)
            self.cases = cases
            self.guild = guild
            self.author = author
            self.per_page = per_page
            self.page = 0
            self.max_pages = max(1, (len(cases) + per_page - 1) // per_page)
            self.update_buttons()
        
        def update_buttons(self):
            self.prev_btn.disabled = self.page <= 0
            self.next_btn.disabled = self.page >= self.max_pages - 1
        
        def build_embed(self) -> discord.Embed:
            embed = discord.Embed(
                title="📋 Moderation Cases",
                color=primary_color(),
                timestamp=datetime.now(timezone.utc)
            )
            
            start = self.page * self.per_page
            end = start + self.per_page
            page_cases = self.cases[start:end]
            
            if not page_cases:
                embed.description = "No cases found."
            else:
                for case in page_cases:
                    user = self.guild.get_member(case.get("user_id"))
                    mod = self.guild.get_member(case.get("mod_id"))
                    user_str = user.mention if user else f"ID: {case.get('user_id')}"
                    mod_str = mod.display_name if mod else "Unknown"
                    
                    embed.add_field(
                        name=f"Case #{case.get('case_num')} - {case.get('type', 'Unknown').upper()}",
                        value=f"**User:** {user_str}\n"
                              f"**Mod:** {mod_str}\n"
                              f"**Reason:** {case.get('reason', 'No reason')}",
                        inline=False
                    )
            
            embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages}")
            return embed
        
        @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
        async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                return await interaction.response.send_message("Not your view!", ephemeral=True)
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        
        @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
        async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                return await interaction.response.send_message("Not your view!", ephemeral=True)
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)


class ModerationUtils:
    """Utility functions for moderation"""
    
    @staticmethod
    def parse_duration(duration_str: str) -> Optional[timedelta]:
        """Parse duration string like '1h', '30m', '7d' into timedelta"""
        if not duration_str:
            return None
        
        units = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800
        }
        
        match = re.match(r"^(\d+)([smhdw])$", duration_str.lower())
        if not match:
            return None
        
        amount, unit = match.groups()
        seconds = int(amount) * units[unit]
        return timedelta(seconds=seconds)
    
    @staticmethod
    def format_duration(td: timedelta) -> str:
        """Format timedelta into human readable string"""
        total_seconds = int(td.total_seconds())
        
        if total_seconds < 60:
            return f"{total_seconds} second(s)"
        elif total_seconds < 3600:
            return f"{total_seconds // 60} minute(s)"
        elif total_seconds < 86400:
            return f"{total_seconds // 3600} hour(s)"
        else:
            return f"{total_seconds // 86400} day(s)"
    
    @staticmethod
    def can_moderate(moderator: discord.Member, target: discord.Member) -> tuple[bool, str]:
        """Check if moderator can take action on target"""
        if target.id == moderator.id:
            return False, "You cannot moderate yourself."
        
        if target.id == moderator.guild.owner_id:
            return False, "You cannot moderate the server owner."
        
        if target.top_role >= moderator.top_role and moderator.id != moderator.guild.owner_id:
            return False, "You cannot moderate someone with an equal or higher role."
        
        bot_member = moderator.guild.me
        if target.top_role >= bot_member.top_role:
            return False, "I cannot moderate someone with an equal or higher role than me."
        
        return True, ""
    
    @staticmethod
    async def send_dm(user: Union[discord.Member, discord.User], embed: discord.Embed) -> bool:
        """Try to send a DM to user, return success status"""
        try:
            await user.send(embed=embed)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False


class AutoModConfig:
    """Auto-moderation configuration"""
    
    DEFAULT_CONFIG = {
        "enabled": False,
        "anti_spam": {
            "enabled": False,
            "message_limit": 5,
            "time_window": 5,
            "action": "mute",
            "duration": "5m"
        },
        "anti_invite": {
            "enabled": False,
            "action": "delete",
            "whitelist": []
        },
        "anti_caps": {
            "enabled": False,
            "threshold": 70,
            "min_length": 10,
            "action": "delete"
        },
        "anti_mention": {
            "enabled": False,
            "max_mentions": 5,
            "action": "mute",
            "duration": "10m"
        },
        "word_filter": {
            "enabled": False,
            "words": [],
            "action": "delete"
        }
    }


class RoleManagement:
    """Role management utilities"""
    
    @staticmethod
    async def add_role(member: discord.Member, role: discord.Role, reason: str = None) -> bool:
        """Add a role to a member"""
        try:
            await member.add_roles(role, reason=reason)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False
    
    @staticmethod
    async def remove_role(member: discord.Member, role: discord.Role, reason: str = None) -> bool:
        """Remove a role from a member"""
        try:
            await member.remove_roles(role, reason=reason)
            return True
        except (discord.Forbidden, discord.HTTPException):
            return False
    
    @staticmethod
    async def create_mute_role(guild: discord.Guild) -> Optional[discord.Role]:
        """Create a mute role with proper permissions"""
        try:
            role = await guild.create_role(
                name="Muted",
                color=discord.Color.dark_gray(),
                reason="Auto-created mute role"
            )
            
            for channel in guild.channels:
                try:
                    await channel.set_permissions(
                        role,
                        send_messages=False,
                        add_reactions=False,
                        speak=False,
                        reason="Mute role setup"
                    )
                except discord.Forbidden:
                    continue
            
            return role
        except (discord.Forbidden, discord.HTTPException):
            return None
