import aiohttp
import discord
import asyncio
import random
import logging
import re
from typing import Optional, List, Dict, Set
from datetime import datetime, timedelta
from imports.discord_imports import *
from data.local.const import primary_color
from data.local.emojis import *
from bot.utils.cogs.art import ArtAggregator, ART_SOURCES
from motor.motor_asyncio import AsyncIOMotorClient
import os

# Setup logging
cover_logger = logging.getLogger('cover_art')
cover_logger.setLevel(logging.DEBUG)

class CoverArtDatabase:
    """MongoDB interface for cover art system"""
    
    def __init__(self, db):
        self.db = db
        self.characters_collection = db["characters"]
        self.cover_purchases_collection = db["cover_purchases"]
        self.cover_inventory_collection = db["cover_inventory"]
        # Use quest_data for balances instead of separate collection
        self.quest_collection = db["Quest_Data"]
        # Explicit collection access (MotorCollection is subscriptable, not callable)
        self.servers_collection = db["Servers"]
    
    @staticmethod
    def normalize_key(raw: str) -> str:
        """Lowercase, trim, replace spaces with underscores, strip non-word separators."""
        cleaned = str(raw or "").strip().lower()
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned
    
    async def _ensure_character_id(self, doc: Dict) -> Dict:
        """If a character document is missing _id, add one based on name."""
        if not doc:
            return doc
        if "_id" not in doc or not doc.get("_id"):
            fallback = self.normalize_key(doc.get("name") or "")
            if fallback:
                doc["_id"] = fallback
                await self.characters_collection.update_one({"_id": fallback}, {"$set": doc}, upsert=True)
        return doc
    
    async def ensure_character_exists(self, name: str, server_id: int, member_id: int, extra: Optional[Dict] = None) -> Optional[Dict]:
        """
        Ensure a character document exists. Creates a minimal record if missing.
        Server-specific characters.
        """
        if not name:
            return None
        normalized_id = self.normalize_key(name)
        existing = await self.characters_collection.find_one({
            "_id": normalized_id,
            "server_id": server_id,
            "member_id": member_id
        })
        if existing:
            enriched = await self.enrich_character_metadata(existing, name)
            return await self._ensure_character_id(enriched)
        
        # Pull metadata from Servers if available
        meta = extra or await self.find_character_metadata(name) or {}
        rarity = meta.get("rarity", "C")
        # Map gacha rarity -> cover rarity
        rarity_map = {
            "common": "C",
            "uncommon": "C",
            "rare": "R",
            "epic": "SR",
            "legendary": "SSR"
        }
        rarity = rarity_map.get(str(rarity).lower(), rarity)
        
        now = datetime.utcnow()
        doc = {
            "_id": normalized_id,
            "name": name,
            "server_id": server_id,
            "member_id": member_id,
            "series": meta.get("anime") or meta.get("series") or "Unknown",
            "description": meta.get("description", ""),
            "rarity": rarity,
            "default_image": meta.get("image_url") or meta.get("default_image"),
            "aliases": meta.get("aliases", []),
            "tags": meta.get("tags", []),
            "favorites": meta.get("favorites", 0),
            "created_at": now,
            "updated_at": now,
        }
        await self.characters_collection.insert_one(doc)
        return doc

    async def enrich_character_metadata(self, doc: Dict, name_hint: str, guild_id: Optional[int] = None) -> Dict:
        """
        If doc is missing good metadata, try to fill from gacha inventory.
        """
        needs_update = False
        meta = await self.find_character_metadata(name_hint, guild_id)
        
        if meta:
            # Series - update if Unknown or missing
            series_val = doc.get("series")
            if not series_val or series_val == "Unknown":
                new_series = meta.get("anime") or meta.get("series")
                if new_series and new_series != "Unknown":
                    doc["series"] = new_series
                    needs_update = True
            
            # Rarity - map gacha rarity to cover rarity
            rarity_map = {
                "common": "C",
                "uncommon": "C",
                "rare": "R",
                "epic": "SR",
                "legendary": "SSR"
            }
            gacha_rarity = str(meta.get("rarity", "")).lower()
            meta_rarity = rarity_map.get(gacha_rarity, None)
            
            # Only update if current is C/Unknown and we have better data
            current_rarity = doc.get("rarity")
            if meta_rarity and current_rarity in (None, "", "Unknown", "C") and gacha_rarity != "common":
                doc["rarity"] = meta_rarity
                needs_update = True
            
            # Favorites
            if not doc.get("favorites") and meta.get("favorites"):
                doc["favorites"] = meta.get("favorites", 0)
                needs_update = True
            
            # Default image
            if not doc.get("default_image") and meta.get("image_url"):
                doc["default_image"] = meta.get("image_url")
                needs_update = True
            
            # About/description
            if not doc.get("description") and meta.get("about"):
                doc["description"] = meta.get("about")
                needs_update = True
        
        if needs_update:
            cover_logger.info(f"Enriching character {doc.get('_id')} with metadata from gacha DB")
            await self.characters_collection.update_one(
                {"_id": doc.get("_id")}, 
                {"$set": doc}, 
                upsert=True
            )
        
        return doc
    
    async def find_character_metadata(self, name: str, guild_id: Optional[int] = None) -> Optional[Dict]:
        """
        Look up character metadata from Servers.gacha_inventory by name.
        Returns anime, rarity, favorites, image_url if found.
        If guild_id is provided, searches only within that server.
        """
        if not name or self.servers_collection is None:
            return None
        
        # Build match filter
        match_filter = {"gacha.name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        if guild_id:
            match_filter["guild_id"] = str(guild_id)
        
        # Try exact match first
        pipeline = [
            {"$match": {"guild_id": str(guild_id)} if guild_id else {}},
            {"$project": {"members": {"$objectToArray": "$members"}}},
            {"$unwind": "$members"},
            {"$project": {"gacha": "$members.v.gacha_inventory"}},
            {"$unwind": "$gacha"},
            {"$match": match_filter},
            {"$limit": 1},
            {"$project": {
                "name": "$gacha.name",
                "anime": "$gacha.anime",
                "rarity": "$gacha.rarity",
                "favorites": "$gacha.favorites",
                "image_url": "$gacha.image_url",
                "about": "$gacha.about",
                "uid": "$gacha.uid"
            }}
        ]
        async for doc in self.servers_collection.aggregate(pipeline):
            cover_logger.info(f"Found exact match for '{name}': {doc.get('anime')} - {doc.get('rarity')}")
            return doc
        
        # Try partial match if exact failed
        normalized = name.lower().replace(" ", "")
        match_filter2 = {"gacha.name": {"$regex": re.escape(normalized), "$options": "i"}}
        if guild_id:
            match_filter2["guild_id"] = str(guild_id)
            
        pipeline2 = [
            {"$match": {"guild_id": str(guild_id)} if guild_id else {}},
            {"$project": {"members": {"$objectToArray": "$members"}}},
            {"$unwind": "$members"},
            {"$project": {"gacha": "$members.v.gacha_inventory"}},
            {"$unwind": "$gacha"},
            {"$match": match_filter2},
            {"$limit": 1},
            {"$project": {
                "name": "$gacha.name",
                "anime": "$gacha.anime",
                "rarity": "$gacha.rarity",
                "favorites": "$gacha.favorites",
                "image_url": "$gacha.image_url",
                "about": "$gacha.about",
                "uid": "$gacha.uid"
            }}
        ]
        async for doc in self.servers_collection.aggregate(pipeline2):
            cover_logger.info(f"Found partial match for '{name}': {doc.get('anime')} - {doc.get('rarity')}")
            return doc
        
        cover_logger.warning(f"No metadata found for character '{name}'")
        return None
    
    async def get_character_by_id(self, character_id: str, server_id: int, member_id: int) -> Optional[Dict]:
        """Get character data by normalized ID; also recover outdated docs missing _id."""
        normalized_id = self.normalize_key(character_id)
        doc = await self.characters_collection.find_one({
            "_id": normalized_id,
            "server_id": server_id,
            "member_id": member_id
        })
        if doc:
            enriched = await self.enrich_character_metadata(doc, doc.get("name") or character_id, server_id)
            return await self._ensure_character_id(enriched)
        
        # Fallback: try name match if _id missing/outdated
        doc = await self.characters_collection.find_one({"name": {"$regex": f"^{re.escape(character_id)}$", "$options": "i"}})
        if doc:
            enriched = await self.enrich_character_metadata(doc, doc.get("name") or character_id, server_id)
            return await self._ensure_character_id(enriched)
        return None
    
    async def smart_search_covers(self, character_name: str, series: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Smart search for cover art using character name and optional series filter."""
        # Build search query: character name + series if available
        search_query = character_name
        if series and series.lower() != "unknown":
            # For single-word names, add extra disambiguation
            if len(character_name.split()) == 1:
                search_query = f"{character_name} {series} anime"
            else:
                search_query = f"{character_name} {series}"
        return search_query

    async def resolve_character_id_from_uid(self, uid: str) -> Optional[str]:
        """
        Resolve a gacha UID to a character id (normalized name) by scanning Servers members.
        This lets .draw view accept gacha UIDs (e.g., 738E0000).
        """
        if not uid or self.servers_collection is None:
            return None
        
        # Try exact UID match first
        pipeline = [
            {"$project": {"members": {"$objectToArray": "$members"}}},
            {"$unwind": "$members"},
            {"$project": {"gacha": "$members.v.gacha_inventory"}},
            {"$unwind": "$gacha"},
            {"$match": {"gacha.uid": {"$regex": f"^{re.escape(uid)}$", "$options": "i"}}},
            {"$limit": 1},
            {"$project": {"name": "$gacha.name"}}
        ]
        async for doc in self.servers_collection.aggregate(pipeline):
            name = doc.get("name")
            if name:
                cover_logger.info(f"Resolved UID '{uid}' to name '{name}'")
                return self.normalize_key(name)
        
        # Try case-insensitive match if exact failed
        pipeline2 = [
            {"$project": {"members": {"$objectToArray": "$members"}}},
            {"$unwind": "$members"},
            {"$project": {"gacha": "$members.v.gacha_inventory"}},
            {"$unwind": "$gacha"},
            {"$match": {"gacha.uid": {"$regex": re.escape(uid), "$options": "i"}}},
            {"$limit": 1},
            {"$project": {"name": "$gacha.name"}}
        ]
        async for doc in self.servers_collection.aggregate(pipeline2):
            name = doc.get("name")
            if name:
                cover_logger.info(f"Resolved UID '{uid}' (case-insensitive) to name '{name}'")
                return self.normalize_key(name)
        
        cover_logger.warning(f"Could not resolve UID '{uid}' to any character name")
        return None
    
    async def get_user_balance(self, user_id: int) -> int:
        """Get user's stella points balance from quest_data"""
        doc = await self.quest_collection.find_one({"user_id": str(user_id)})
        return doc.get("stella_points", 0) if doc else 0
    
    async def update_user_balance(self, user_id: int, amount: int) -> bool:
        """Update user stella points balance (can be negative for purchases)"""
        await self.quest_collection.update_one(
            {"user_id": str(user_id)},
            {"$inc": {"stella_points": amount}},
            upsert=True
        )
        return True
    
    async def get_user_cover_inventory(self, user_id: int, character_id: str) -> List[Dict]:
        """Get user's purchased cover art for a character"""
        normalized_id = character_id.lower().replace(" ", "_")
        doc = await self.cover_inventory_collection.find_one({
            "user_id": user_id,
            "character_id": normalized_id
        })
        return doc.get("covers", []) if doc else []
    
    async def add_cover_to_inventory(self, user_id: int, character_id: str, cover_data: Dict) -> bool:
        """Add purchased cover art to user's inventory"""
        normalized_id = character_id.lower().replace(" ", "_")
        await self.cover_inventory_collection.update_one(
            {"user_id": user_id, "character_id": normalized_id},
            {"$push": {"covers": cover_data}},
            upsert=True
        )
        return True
    
    async def has_cover_unlocked(self, user_id: int, character_id: str) -> bool:
        """
        Check if user has unlocked cover art system for this character.
        Now unlocked by default (returns True when character exists).
        """
        character = await self.get_character_by_id(character_id)
        return character is not None


class CoverArtBrowseView(discord.ui.View):
    """Browse view for cover art shop - displays 3 embeds at once like art command"""
    
    def __init__(self, user_id: int, character_id: str, character_name: str, covers: List[Dict], db: CoverArtDatabase, owned_covers: Set[str], ctx):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.character_id = character_id
        self.character_name = character_name
        self.covers = covers
        self.db = db
        self.owned_covers = owned_covers
        self.ctx = ctx
        self.page = 0
        self.images_per_page = 3
        
        self.update_buttons()
    
    @property
    def max_pages(self) -> int:
        if not self.covers:
            return 1
        return max(1, (len(self.covers) + self.images_per_page - 1) // self.images_per_page)
    
    def build_embeds(self) -> List[discord.Embed]:
        """Build 3 embeds for current page"""
        if not self.covers:
            embed = discord.Embed(
                title="🎨 Cover Art Shop",
                description=f"No cover art found for **{self.character_name}**",
                color=discord.Color.red()
            )
            return [embed]
        
        start_idx = self.page * self.images_per_page
        end_idx = min(start_idx + self.images_per_page, len(self.covers))
        page_covers = self.covers[start_idx:end_idx]
        
        embeds = []
        for i, cover in enumerate(page_covers):
            cover_id = cover.get("id", "")
            is_owned = cover_id in self.owned_covers
            
            embed = discord.Embed(
                title=f"🎨 {self.character_name} - Cover #{start_idx + i + 1}",
                color=discord.Color.green() if is_owned else discord.Color.gold()
            )
            
            if cover.get("url"):
                embed.set_image(url=cover["url"])
            
            # Details
            details = f"**Source:** {cover.get('source', 'Unknown')}\n"
            details += f"**Price:** {cover.get('price', 0):,} stella points\n"
            details += f"**Quality:** {cover.get('width', 'N/A')}x{cover.get('height', 'N/A')}\n"
            
            if is_owned:
                details += "\n✅ **OWNED**"
            else:
                details += f"\nUse `.draw cover -buy {cover_id}` to purchase"
            
            embed.add_field(name="Details", value=details, inline=False)
            embed.set_footer(text=f"ID: {cover_id} | Page {self.page + 1}/{self.max_pages}")
            
            embeds.append(embed)
        
        return embeds
    
    def update_buttons(self):
        self.clear_items()
        
        # Row 0: Buy buttons for current page covers
        start_idx = self.page * self.images_per_page
        end_idx = min(start_idx + self.images_per_page, len(self.covers))
        page_covers = self.covers[start_idx:end_idx]
        
        for i, cover in enumerate(page_covers):
            cover_id = cover.get("id", "")
            is_owned = cover_id in self.owned_covers
            
            if is_owned:
                btn = discord.ui.Button(
                    label=f"#{start_idx + i + 1} ✅ Owned",
                    style=discord.ButtonStyle.success,
                    disabled=True,
                    row=0
                )
            else:
                price = cover.get("price", 0)
                btn = discord.ui.Button(
                    label=f"#{start_idx + i + 1} Buy ({price//1000}k)",
                    style=discord.ButtonStyle.primary,
                    custom_id=f"buy_{cover_id}",
                    row=0
                )
                btn.callback = lambda inter, cid=cover_id, c=cover: self.buy_cover(inter, cid, c)
            
            self.add_item(btn)
        
        # Row 1: Navigation
        prev_btn = discord.ui.Button(label="◀", style=discord.ButtonStyle.secondary, disabled=self.page == 0, row=1)
        prev_btn.callback = self.prev_page
        self.add_item(prev_btn)
        
        page_btn = discord.ui.Button(label=f"Page {self.page + 1}/{self.max_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1)
        self.add_item(page_btn)
        
        next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.secondary, disabled=self.page >= self.max_pages - 1, row=1)
        next_btn.callback = self.next_page
        self.add_item(next_btn)
    
    async def prev_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Not your shop!", ephemeral=True)
        
        self.page = max(0, self.page - 1)
        self.update_buttons()
        embeds = self.build_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Not your shop!", ephemeral=True)
        
        self.page = min(self.max_pages - 1, self.page + 1)
        self.update_buttons()
        embeds = self.build_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    async def buy_cover(self, interaction: discord.Interaction, cover_id: str, cover_data: dict):
        """Handle cover purchase with confirmation"""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Not your shop!", ephemeral=True)
        
        price = cover_data.get("price", 0)
        
        # Check balance
        balance = await self.db.get_user_balance(interaction.user.id)
        if balance < price:
            return await interaction.response.send_message(
                f"❌ Insufficient funds! You need {price:,} stella points but only have {balance:,} stella points.",
                ephemeral=True
            )
        
        # Create confirmation view
        confirm_view = CoverPurchaseConfirmView(
            self.user_id,
            cover_data,
            price,
            self.db,
            self.character_id
        )
        
        embed = discord.Embed(
            title="🛒 Confirm Purchase",
            description=f"Buy this cover art for **{price:,} stella points**?",
            color=discord.Color.orange()
        )
        embed.set_image(url=cover_data.get("url"))
        embed.add_field(
            name="Character",
            value=self.character_name,
            inline=True
        )
        embed.add_field(
            name="Your Balance",
            value=f"{balance:,} stella points",
            inline=True
        )
        embed.set_footer(text=f"After purchase: {balance - price:,} stella points")
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class CoverArtShopView(discord.ui.View):
    """Paginated view for cover art shop (legacy single-embed view)"""
    
    def __init__(self, user_id: int, character_id: str, covers: List[Dict], db: CoverArtDatabase, owned_covers: Set[str]):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.character_id = character_id
        self.covers = covers
        self.db = db
        self.owned_covers = owned_covers
        self.current_page = 0
        self.items_per_page = 1
        self.max_pages = max(len(covers) - 1, 0)
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        # Navigation buttons
        if self.current_page > 0:
            self.add_item(CoverShopButton("◀️ Previous", discord.ButtonStyle.secondary, "previous", self))
        
        if self.current_page < self.max_pages:
            self.add_item(CoverShopButton("▶️ Next", discord.ButtonStyle.secondary, "next", self))
        
        # Purchase button
        current_cover = self.covers[self.current_page]
        cover_id = current_cover.get("id", "")
        
        if cover_id in self.owned_covers:
            self.add_item(CoverShopButton("✅ Owned", discord.ButtonStyle.success, "owned", self, disabled=True))
        else:
            price = current_cover.get("price", 0)
            self.add_item(CoverShopButton(f"💰 Buy ({price:,} stella)", discord.ButtonStyle.primary, "buy", self))
    
    async def create_embed(self) -> discord.Embed:
        if not self.covers:
            return discord.Embed(
                title="🎨 Cover Art Shop",
                description="No cover art available for this character.",
                color=discord.Color.red()
            )
        
        current_cover = self.covers[self.current_page]
        cover_id = current_cover.get("id", "")
        is_owned = cover_id in self.owned_covers
        
        embed = discord.Embed(
            title=f"🎨 Cover Art Shop - {self.character_id.replace('_', ' ').title()}",
            color=discord.Color.gold() if not is_owned else discord.Color.green()
        )
        
        # Set cover image
        if current_cover.get("url"):
            embed.set_image(url=current_cover["url"])
        
        # Cover details
        embed.add_field(
            name="📋 Details",
            value=f"**Source:** {current_cover.get('source', 'Unknown')}\n"
                  f"**Artist:** {current_cover.get('artist', 'Unknown')}\n"
                  f"**Quality:** {current_cover.get('width', 'N/A')}x{current_cover.get('height', 'N/A')}\n"
                  f"**Price:** {current_cover.get('price', 0):,} stella points",
            inline=False
        )
        
        # Ownership status
        status = "✅ **OWNED**" if is_owned else "🛒 **Available for Purchase**"
        embed.add_field(name="Status", value=status, inline=False)
        
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.max_pages + 1} • ID: {cover_id}")
        
        return embed


class CoverShopButton(discord.ui.Button):
    """Button for cover art shop interactions"""
    
    def __init__(self, label: str, style: discord.ButtonStyle, action: str, shop_view, disabled: bool = False):
        super().__init__(label=label, style=style, disabled=disabled)
        self.action = action
        self.shop_view = shop_view
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.shop_view.user_id:
            await interaction.response.send_message("❌ You can only interact with your own cover art shop!", ephemeral=True)
            return
        
        if self.action == "previous":
            self.shop_view.current_page = max(0, self.shop_view.current_page - 1)
        elif self.action == "next":
            self.shop_view.current_page = min(self.shop_view.max_pages, self.shop_view.current_page + 1)
        elif self.action == "buy":
            await self.handle_purchase(interaction)
            return
        elif self.action == "owned":
            await interaction.response.send_message("✅ You already own this cover art!", ephemeral=True)
            return
        
        # Update view and embed
        self.shop_view.update_buttons()
        embed = await self.shop_view.create_embed()
        await interaction.response.edit_message(embed=embed, view=self.shop_view)
    
    async def handle_purchase(self, interaction: discord.Interaction):
        """Handle cover art purchase with confirmation"""
        current_cover = self.shop_view.covers[self.shop_view.current_page]
        price = current_cover.get("price", 0)
        
        # Check user balance
        balance = await self.shop_view.db.get_user_balance(interaction.user.id)
        if balance < price:
            await interaction.response.send_message(
                f"❌ Insufficient funds! You need {price:,} stella points but only have {balance:,} stella points.",
                ephemeral=True
            )
            return
        
        # Create confirmation view
        confirm_view = CoverPurchaseConfirmView(
            self.shop_view.user_id,
            current_cover,
            price,
            self.shop_view.db,
            self.shop_view.character_id
        )
        
        embed = discord.Embed(
            title="🛒 Confirm Purchase",
            description=f"Are you sure you want to buy this cover art for **{price:,} stella points**?",
            color=discord.Color.orange()
        )
        embed.set_image(url=current_cover.get("url"))
        embed.add_field(name="Your Balance", value=f"{balance:,} stella points", inline=True)
        embed.add_field(name="After Purchase", value=f"{balance - price:,} stella points", inline=True)
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class CoverPurchaseConfirmView(discord.ui.View):
    """Confirmation view for cover art purchases"""
    
    def __init__(self, user_id: int, cover_data: Dict, price: int, db: CoverArtDatabase, character_id: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.cover_data = cover_data
        self.price = price
        self.db = db
        self.character_id = character_id
    
    @discord.ui.button(label="✅ Confirm Purchase", style=discord.ButtonStyle.success)
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your purchase!", ephemeral=True)
            return
        
        # Double-check balance
        balance = await self.db.get_user_balance(interaction.user.id)
        if balance < self.price:
            await interaction.response.send_message("❌ Insufficient funds!", ephemeral=True)
            return
        
        # Process purchase
        await self.db.update_user_balance(interaction.user.id, -self.price)
        await self.db.add_cover_to_inventory(interaction.user.id, self.character_id, self.cover_data)
        
        embed = discord.Embed(
            title="✅ Purchase Successful!",
            description=f"You've successfully purchased this cover art for **{self.price:,} stella points**!",
            color=discord.Color.green()
        )
        embed.add_field(name="New Balance", value=f"{balance - self.price:,} stella points", inline=True)
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This is not your purchase!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❌ Purchase Cancelled",
            description="Your purchase has been cancelled.",
            color=discord.Color.red()
        )
        
        self.clear_items()
        await interaction.response.edit_message(embed=embed, view=self)


class CoverUnlockInfoView(discord.ui.View):
    """Provides unlock instructions when cover art is locked"""

    def __init__(self):
        super().__init__(timeout=120)

    @discord.ui.button(label="How to unlock cover art", style=discord.ButtonStyle.primary)
    async def how_to_unlock(self, interaction: discord.Interaction, button: discord.ui.Button):
        instructions = (
            "Cover art unlocks when the character reaches enough interactions/favorites.\n"
            "Earn progress by drawing, claiming, and interacting with the character.\n"
            "Once unlocked, rerun `.draw view <character_id>` to access the Cover Art Shop."
        )
        await interaction.response.send_message(instructions, ephemeral=True)


class CoverArtVariantView(discord.ui.View):
    """View for selecting cover art variants in draw view"""
    
    def __init__(self, user_id: int, character_id: str, character_data: Dict, owned_covers: List[Dict], db: CoverArtDatabase):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.character_id = character_id
        self.character_data = character_data
        self.owned_covers = owned_covers
        self.db = db
        self.current_variant = 0
        
        self.update_buttons()
    
    def update_buttons(self):
        self.clear_items()
        
        if len(self.owned_covers) > 1:
            # Navigation buttons for multiple covers
            if self.current_variant > 0:
                self.add_item(CoverVariantButton("◀️ Previous", discord.ButtonStyle.secondary, "previous", self))
            
            if self.current_variant < len(self.owned_covers) - 1:
                self.add_item(CoverVariantButton("▶️ Next", discord.ButtonStyle.secondary, "next", self))
        
        # Cover art shop button (always available if character has cover art unlocked)
        self.add_item(CoverVariantButton("🛒 Cover Art Shop", discord.ButtonStyle.primary, "shop", self))
        
        # Inventory button (ephemeral list of owned covers)
        self.add_item(CoverVariantButton("Inventory", discord.ButtonStyle.secondary, "inventory", self))
    
    def get_image_url(self) -> Optional[str]:
        """Get the current image URL for display"""
        if self.owned_covers and self.current_variant < len(self.owned_covers):
            return self.owned_covers[self.current_variant].get("url")
        elif self.character_data.get("default_image"):
            return self.character_data["default_image"]
        return None
    
    def create_content_message(self) -> str:
        """Create formatted content message without emojis"""
        character_name = self.character_data.get("name", self.character_id.replace("_", " ").title())
        description = self.character_data.get("description", "A mysterious character...")
        rarity = self.character_data.get("rarity", "Unknown")
        series = self.character_data.get("series", "Unknown")
        
        content = f"**{character_name}**\n"
        content += f"*{description}*\n\n"
        content += f"**Series:** {series}\n"
        content += f"**Rarity:** {rarity}\n"
        content += f"**Covers Owned:** {len(self.owned_covers)}\n"
        
        if self.owned_covers and self.current_variant < len(self.owned_covers):
            current_cover = self.owned_covers[self.current_variant]
            content += f"\n**Current Cover:**\n"
            content += f"Source: {current_cover.get('source', 'Unknown')}\n"
            content += f"Artist: {current_cover.get('artist', 'Unknown')}"
        
        if len(self.owned_covers) > 1:
            content += f"\n\nCover {self.current_variant + 1} of {len(self.owned_covers)}"
        
        return content


class CoverVariantButton(discord.ui.Button):
    """Button for cover art variant interactions"""
    
    def __init__(self, label: str, style: discord.ButtonStyle, action: str, variant_view):
        super().__init__(label=label, style=style)
        self.action = action
        self.variant_view = variant_view
    
    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.variant_view.user_id:
            await interaction.response.send_message("❌ You can only interact with your own character view!", ephemeral=True)
            return
        
        if self.action == "previous":
            self.variant_view.current_variant = max(0, self.variant_view.current_variant - 1)
        elif self.action == "next":
            self.variant_view.current_variant = min(len(self.variant_view.owned_covers) - 1, self.variant_view.current_variant + 1)
        elif self.action == "shop":
            await self.open_cover_shop(interaction)
            return
        elif self.action == "inventory":
            await self.show_inventory(interaction)
            return
        
        # Update view and send image with content
        self.variant_view.update_buttons()
        content = self.variant_view.create_content_message()
        image_url = self.variant_view.get_image_url()
        
        if image_url:
            await interaction.response.edit_message(content=content, attachments=[], view=self.variant_view)
            await interaction.followup.send(image_url, ephemeral=True)
        else:
            await interaction.response.edit_message(content=content, view=self.variant_view)
    
    async def open_cover_shop(self, interaction: discord.Interaction):
        """Open the cover art shop for this character"""
        # Generate available covers using art aggregator
        session = aiohttp.ClientSession()
        try:
            art_aggregator = ArtAggregator(session)
            
            # Search for character art
            character_name = self.variant_view.character_id.replace("_", " ")
            search_results = await art_aggregator.search_all(
                query=character_name,
                limit=20,
                nsfw=False,
                selected_sources={"safebooru", "wallhaven", "konachan_safe", "aibooru"},
                aggressive_load=False
            )
            
            if not search_results:
                await interaction.response.send_message(
                    f"❌ No cover art found for {character_name}. Try again later!",
                    ephemeral=True
                )
                return
            
            # Convert search results to shop format with pricing
            character_data = self.variant_view.character_data
            rarity = character_data.get("rarity", "C")
            
            # Rarity-based pricing (extremely expensive as requested)
            base_prices = {"C": 50000, "R": 100000, "SR": 250000, "SSR": 500000}
            base_price = base_prices.get(rarity, 50000)
            
            covers = []
            for i, result in enumerate(search_results[:10]):  # Limit to 10 covers
                price_multiplier = random.uniform(0.8, 1.5)  # Add some price variation
                final_price = int(base_price * price_multiplier)
                
                covers.append({
                    "id": f"{self.variant_view.character_id}_{i}_{result.get('id', 'unknown')}",
                    "url": result.get("url"),
                    "source": result.get("source"),
                    "artist": result.get("artist"),
                    "width": result.get("width"),
                    "height": result.get("height"),
                    "price": final_price
                })
            
            # Get user's owned covers
            owned_covers = await self.variant_view.db.get_user_cover_inventory(
                interaction.user.id, 
                self.variant_view.character_id
            )
            owned_cover_ids = {cover.get("id") for cover in owned_covers}
            
            # Create shop view
            shop_view = CoverArtShopView(
                interaction.user.id,
                self.variant_view.character_id,
                covers,
                self.variant_view.db,
                owned_cover_ids
            )
            
            embed = await shop_view.create_embed()
            await interaction.response.send_message(embed=embed, view=shop_view, ephemeral=True)
            
        finally:
            await session.close()

    async def show_inventory(self, interaction: discord.Interaction):
        """Show an ephemeral list of owned covers"""
        covers = self.variant_view.owned_covers or []
        if not covers:
            await interaction.response.send_message("You don't own any covers for this character yet.", ephemeral=True)
            return
        
        lines = []
        for idx, cover in enumerate(covers, start=1):
            source = cover.get("source", "Unknown")
            artist = cover.get("artist", "Unknown")
            lines.append(f"{idx}. {source} — {artist}")
        
        msg = "Your covers:\n" + "\n".join(lines)
        await interaction.response.send_message(msg, ephemeral=True)


class CoverArt(commands.Cog):
    """Cover Art System - Dynamic character cover art with shop functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = None
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize MongoDB connection"""
        try:
            mongo_url = os.getenv("MONGO_URI")
            if not mongo_url:
                cover_logger.error("MONGO_URL/MONGO_URI is not set; cover art system disabled.")
                self.db = None
                return
            client = AsyncIOMotorClient(mongo_url)
            database = client["anya_bot"]
            self.db = CoverArtDatabase(database)
        except Exception as e:
            cover_logger.error(f"Failed to initialize database: {e}")
    
    @commands.group(name="draw", invoke_without_command=True)
    async def draw_view(self, ctx, action: str = None, character_id: str = None):
        """
        View character with cover art variants
        Usage: .draw view <character_id>
        """
        if not self.db:
            await ctx.send("❌ Database connection not available!")
            return
        
        if action != "view" or not character_id:
            embed = discord.Embed(
                title="🎨 Draw Command Help",
                description="**Usage:** `.draw view <character_id>`\n\n"
                           "**Examples:**\n"
                           "• `.draw view anya_forger`\n"
                           "• `.draw view naruto_uzumaki`\n"
                           "• `.draw view zero_two`",
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
            return
        
        # Support gacha UID input (e.g., 738E0000) by resolving to character name/id
        normalized_id = None
        uid_candidate = character_id.strip()
        if re.fullmatch(r"[A-F0-9]{8}", uid_candidate.upper()):
            resolved = await self.db.resolve_character_id_from_uid(uid_candidate.upper())
            if resolved:
                normalized_id = resolved
        
        # Fallback to direct normalization of provided id/name
        if not normalized_id:
            normalized_id = self.db.normalize_key(character_id)
        
        # Get character data from MongoDB
        character_data = await self.db.get_character_by_id(normalized_id)
        if not character_data:
            await ctx.send(f"❌ Character `{character_id}` not found in database!")
            return
        
        # Check if user has cover art unlocked for this character
        has_unlocked = await self.db.has_cover_unlocked(ctx.author.id, normalized_id)
        if not has_unlocked:
            view = CoverUnlockInfoView()
            await ctx.send(
                content=(
                    f"Cover art is locked for {character_data.get('name', character_id)}.\n"
                    "Use the button below to learn how to unlock it."
                ),
                view=view
            )
            return
        
        # Get user's owned covers for this character
        owned_covers = await self.db.get_user_cover_inventory(ctx.author.id, normalized_id)
        
        # Create character view with cover art variants
        view = CoverArtVariantView(
            ctx.author.id,
            normalized_id,
            character_data,
            owned_covers,
            self.db
        )
        
        content = view.create_content_message()
        image_url = view.get_image_url()
        
        if image_url:
            await ctx.send(content=content, view=view)
            await ctx.send(image_url)
        else:
            await ctx.send(content=content, view=view)
    
    @draw_view.command(name="cover", aliases=["shop"])
    async def draw_cover(self, ctx, *, character_name: str = None):
        """Browse and buy cover art for a character
        
        Usage: .draw cover <character_name>
        Example: .draw cover Maka Albarn
        """
        if not self.db:
            return await ctx.reply("❌ Cover art system is not available.", mention_author=False)
        
        if not character_name:
            return await ctx.reply(
                f"Usage: `{ctx.prefix}draw cover <character_name>`\n"
                "Example: `.draw cover Maka Albarn`",
                mention_author=False
            )
        
        # Get character from DB or create minimal entry
        normalized_id = self.db.normalize_key(character_name)
        character_data = await self.db.get_character_by_id(normalized_id)
        
        if not character_data:
            # Auto-create character entry
            character_data = await self.db.ensure_character_exists(character_name)
        
        series = character_data.get("series", "Unknown")
        
        # Smart search for covers
        processing_msg = await ctx.reply(
            f"🔍 Searching for cover art for **{character_name}**...\n"
            f"Series: *{series}*",
            mention_author=False
        )
        
        # Build smart query (character + series for better matches)
        search_query = await self.db.smart_search_covers(character_name, series)
        
        # Fetch cover art using art aggregator
        if not hasattr(self, 'art_aggregator'):
            import aiohttp
            session = aiohttp.ClientSession()
            from utils.cogs.art import ArtAggregator
            self.art_aggregator = ArtAggregator(session)
        
        # Fetch SFW covers only (anime-safe sources)
        sfw_sources = {"safebooru", "konachan_safe", "wallhaven", "aibooru", "yandere", "e926"}
        results = await self.art_aggregator.search_all(
            query=search_query,
            limit=100,
            nsfw=False,
            selected_sources=sfw_sources,
            aggressive_load=True,
            max_pages_per_source=3
        )
        
        if not results:
            await processing_msg.edit(content=f"❌ No cover art found for **{character_name}**.")
            return
        
        # Get user's owned covers
        owned_covers = await self.db.get_user_cover_inventory(ctx.author.id, normalized_id)
        owned_ids = {c.get("id") for c in owned_covers}
        
        # Price covers based on character rarity
        rarity = character_data.get("rarity", "C")
        base_prices = {"C": 50000, "R": 100000, "SR": 250000, "SSR": 500000}
        base_price = base_prices.get(rarity, 50000)
        
        # Add pricing to results
        for i, result in enumerate(results):
            variation = random.randint(-20, 20) / 100
            result["price"] = int(base_price * (1 + variation))
            result["id"] = f"{result.get('source', 'unknown')}_{result.get('id', i)}"
        
        # Create cover shop view (3 embeds at once like art command)
        view = CoverArtBrowseView(
            user_id=ctx.author.id,
            character_id=normalized_id,
            character_name=character_name,
            covers=results,
            db=self.db,
            owned_covers=owned_ids,
            ctx=ctx
        )
        
        embeds = view.build_embeds()
        
        await processing_msg.delete()
        await ctx.reply(embeds=embeds, view=view, mention_author=False)
    
    @draw_view.command(name="-buy", aliases=["buy", "-b", "b"])
    async def draw_cover_buy(self, ctx, cover_id: str = None):
        """Buy a cover art by ID
        
        Usage: .draw cover -buy <cover_id>
        Example: .draw cover -buy safebooru_12345
        """
        if not self.db:
            return await ctx.reply("❌ Cover art system is not available.", mention_author=False)
        
        if not cover_id:
            return await ctx.reply(
                f"Usage: `{ctx.prefix}draw cover -buy <cover_id>`\n"
                "Get the cover ID from the shop embed footer.",
                mention_author=False
            )
        
        # Find the cover in recent searches (we'll need to store this temporarily)
        # For now, send a message that they need to use the shop
        return await ctx.reply(
            "❌ Please use `.draw cover <character_name>` to browse covers first, "
            "then use the ID shown in the embed footer to purchase.",
            mention_author=False
        )
    
    @commands.command(name="balance")
    async def check_balance(self, ctx):
        """Check your current stella points balance"""
        if not self.db:
            await ctx.send("❌ Database connection not available!")
            return
        
        balance = await self.db.get_user_balance(ctx.author.id)
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"You have **{balance:,} stella points**",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="addcoins")
    @commands.has_permissions(administrator=True)
    async def add_coins(self, ctx, user: discord.Member, amount: int):
        """Add coins to a user (Admin only)"""
        if not self.db:
            await ctx.send("❌ Database connection not available!")
            return
        
        await self.db.update_user_balance(user.id, amount)
        new_balance = await self.db.get_user_balance(user.id)
        
        embed = discord.Embed(
            title="Coins Added",
            description=f"Added **{amount:,} coins** to {user.mention}\n"
                       f"New balance: **{new_balance:,} coins**",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(CoverArt(bot))
