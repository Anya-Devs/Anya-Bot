import os
import json
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from typing import Optional, Dict, Any, List
import random
import discord
from discord.ext import commands

class Config:
    def __init__(self, config_path: str = "data/commands/halloween/config.json"):
        with open(config_path, 'r') as f:
            self.data = json.load(f)
    
    def get(self, *keys):
        """Get nested config value using dot notation"""
        result = self.data
        for key in keys:
            result = result[key]
        return result
    
    def set(self, *keys, value):
        """Set nested config value and save"""
        result = self.data
        for key in keys[:-1]:
            result = result[key]
        result[keys[-1]] = value
        with open("config.json", 'w') as f:
            json.dump(self.data, f, indent=2)

    @property
    def server_id(self):
        return self.get("bot", "server_id")
    
    @property
    def host_id(self):
        return self.get("bot", "host_id")
    
    @property
    def banner_url(self):
        return self.get("event", "banner_url")
    
    @property
    def apostle_banner_url(self):
        return self.get("event", "apostle_banner_url")
    
    @property
    def story(self):
        return self.get("story", "intro")
    
    @property
    def duration_days(self):
        return self.get("event", "duration_days")

class DatabaseManager:
    def __init__(self):
        self.client = None
        self.db = None
        self.users = None
        self.event_stats = None
        self._connected = False
    
    async def connect(self):
        """Connect to MongoDB"""
        if self._connected:
            return
            
        mongo_uri = os.getenv("MONGO_URI")
        if not mongo_uri:
            raise ValueError("MONGO_URI environment variable not set")
        
        self.client = AsyncIOMotorClient(mongo_uri)
        self.db = self.client.celestial_tribute
        self.users = self.db.users
        self.event_stats = self.db.event_stats
        self._connected = True
        
        if not await self.event_stats.find_one({"_id": "global"}):
            await self.event_stats.insert_one({
                "_id": "global",
                "total_offerings": 0,
                "corruption_level": 0,
                "total_participants": 0,
                "last_updated": datetime.utcnow(),
                "event_start": None,
                "event_end": None
            })
    
    def get_user(self, user_id: int) -> Dict[str, Any]:
        return asyncio.create_task(self._get_user_async(user_id))
    
    async def _get_user_async(self, user_id: int) -> Dict[str, Any]:
        await self.connect()
        user = await self.users.find_one({"_id": user_id})
        if not user:
            user = {
                "_id": user_id,
                "shards": 0,
                "contribution": 0.0,
                "offerings": 0,
                "last_message_time": None,
                "total_messages": 0,
                "joined_event": datetime.utcnow()
            }
            await self.users.insert_one(user)
        return user
    
    def update_user(self, user_data: Dict[str, Any]):
        return asyncio.create_task(self._update_user_async(user_data))
    
    async def _update_user_async(self, user_data: Dict[str, Any]):
        await self.connect()
        await self.users.replace_one(
            {"_id": user_data["_id"]},
            user_data,
            upsert=True
        )
    
    async def make_offering_async(self, user_id: int) -> Dict[str, Any]:
        await self.connect()
        user = await self._get_user_async(user_id)
        offerings_made = user.get("offerings", 0)
        
        cost = 10 + (5 * offerings_made)
        current_shards = user.get("shards", 0)
        
        if current_shards < cost:
            return {"success": False, "message": f"Not enough shards! Need {cost}, have {current_shards}"}
        
        user["shards"] = current_shards - cost
        user["offerings"] = offerings_made + 1
        await self._update_user_async(user)
        
        await self.event_stats.update_one(
            {"_id": "global"},
            {
                "$inc": {"total_offerings": 1},
                "$set": {"last_updated": datetime.utcnow()}
            }
        )
        
        rewards = self._generate_rewards(offerings_made + 1)
        return {"success": True, "cost": cost, "offerings_made": offerings_made + 1, "rewards": rewards}
    
    def _generate_rewards(self, offerings_made: int) -> Dict[str, Any]:
        rewards = {}
        if random.random() < 0.7:
            base_coins = random.randint(1000, 5000)
            multiplier = 1.2 ** (offerings_made - 1)
            rewards["pokecoins"] = int(base_coins * multiplier)
        
        if random.random() < 0.3:
            shiny_chance = min(0.05 + 0.02 * (offerings_made - 1), 0.3)
            rewards["pokemon"] = {
                "received": True,
                "is_shiny": random.random() < shiny_chance,
                "rarity": random.choice(["common", "uncommon", "rare"])
            }
        
        if offerings_made >= 20 and random.random() < 0.01:
            rewards["special_arceus"] = True
        return rewards
    
    def leaderboard(self, limit: int = 10) -> List[Dict[str, Any]]:
        return asyncio.create_task(self._leaderboard_async(limit))
    
    async def _leaderboard_async(self, limit: int = 10) -> List[Dict[str, Any]]:
        await self.connect()
        cursor = self.users.find().sort("offerings", -1).limit(limit)
        leaderboard = []
        async for user in cursor:
            leaderboard.append({
                "user_id": user["_id"],
                "offerings": user.get("offerings", 0),
                "shards": user.get("shards", 0),
                "contribution": user.get("contribution", 0.0)
            })
        return leaderboard
    
    async def get_event_stats(self) -> Dict[str, Any]:
        await self.connect()
        return await self.event_stats.find_one({"_id": "global"})
    
    async def update_event_stats(self, update_data: Dict[str, Any]):
        await self.connect()
        await self.event_stats.update_one(
            {"_id": "global"},
            {"$set": update_data}
        )
    
    async def increment_offerings(self):
        await self.connect()
        await self.event_stats.update_one(
            {"_id": "global"},
            {"$inc": {"total_offerings": 1}, "$set": {"last_updated": datetime.utcnow()}}
        )

class EventManager:
    def __init__(self, config: Config, db: DatabaseManager):
        self.config = config
        self.db = db
    
    async def is_event_active(self) -> bool:
        stats = await self.db.get_event_stats()
        if not stats.get("event_start") or not stats.get("event_end"):
            return False
        now = datetime.utcnow()
        return stats["event_start"] <= now <= stats["event_end"]
    
    async def get_time_remaining(self) -> str:
        stats = await self.db.get_event_stats()
        if not stats.get("event_end"):
            return "Event not scheduled"
        now = datetime.utcnow()
        end_time = stats["event_end"]
        if now > end_time:
            return "Event has ended"
        remaining = end_time - now
        days = remaining.days
        hours, remainder = divmod(remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m"
    
    async def set_event_time(self, start_time: datetime, end_time: datetime):
        await self.db.update_event_stats({
            "event_start": start_time,
            "event_end": end_time,
            "last_updated": datetime.utcnow()
        })
    
    async def get_corruption_stage(self) -> Dict[str, str]:
        stats = await self.db.get_event_stats()
        total_offerings = stats.get("total_offerings", 0)
        stages = self.config.get("story", "corruption_stages")
        if total_offerings >= stages["final"]["threshold"]:
            return stages["final"]
        elif total_offerings >= stages["stage_3"]["threshold"]:
            return stages["stage_3"]
        elif total_offerings >= stages["stage_2"]["threshold"]:
            return stages["stage_2"]
        else:
            return stages["stage_1"]

class PaginationView(discord.ui.View):
    def __init__(self, pages: List[discord.Embed], timeout: float = 180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.current_page = 0
        self.max_pages = len(pages)
        self.update_buttons()
    
    def update_buttons(self):
        self.previous_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.max_pages - 1
    
    @discord.ui.button(label="◄◄", style=discord.ButtonStyle.secondary, disabled=True)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    @discord.ui.button(label="►►", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
