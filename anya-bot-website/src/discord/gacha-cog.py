"""
Discord bot cog for character gacha system
Integrates with Firebase character database
"""

import discord
from discord.ext import commands
from discord import app_commands
import random
from datetime import datetime, timedelta
import asyncio
from typing import Optional

# Import Firebase modules (adjust path as needed)
import sys
sys.path.append('..')
from database.character_db import CharacterDatabase

class GachaCog(commands.Cog):
    """Character Gacha System"""
    
    RARITY_CONFIG = {
        'C': {'name': 'Common', 'weight': 50, 'emoji': '⚪', 'color': 0x9CA3AF},
        'R': {'name': 'Rare', 'weight': 30, 'emoji': '🔵', 'color': 0x3B82F6},
        'SR': {'name': 'Super Rare', 'weight': 15, 'emoji': '🟣', 'color': 0xA855F7},
        'SSR': {'name': 'Ultra Rare', 'weight': 5, 'emoji': '🟡', 'color': 0xF59E0B}
    }
    
    def __init__(self, bot):
        self.bot = bot
        self.db = CharacterDatabase()
        self.user_cooldowns = {}
        
    async def get_random_rarity(self) -> str:
        """Get random rarity based on weights"""
        rarities = list(self.RARITY_CONFIG.keys())
        weights = [self.RARITY_CONFIG[r]['weight'] for r in rarities]
        return random.choices(rarities, weights=weights)[0]
    
    async def check_daily_cooldown(self, user_id: int) -> bool:
        """Check if user can claim daily roll"""
        if user_id not in self.user_cooldowns:
            return True
        
        last_claim = self.user_cooldowns[user_id]
        time_passed = datetime.now() - last_claim
        return time_passed >= timedelta(hours=24)
    
    async def create_character_embed(self, character: dict, rarity: str) -> discord.Embed:
        """Create embed for character roll"""
        rarity_config = self.RARITY_CONFIG[rarity]
        
        embed = discord.Embed(
            title=f"{rarity_config['emoji']} {character['name']}",
            description=f"**Series:** {character['series']}\n**Rarity:** {rarity_config['name']}",
            color=rarity_config['color']
        )
        
        # Add random image from character's collection
        if character.get('images'):
            random_image = random.choice(character['images'])
            embed.set_image(url=random_image)
        
        # Add tags
        if character.get('tags'):
            tags_str = ', '.join(character['tags'][:5])
            embed.add_field(name="Tags", value=tags_str, inline=False)
        
        # Add voice actors
        if character.get('voiceActors'):
            va_text = []
            if character['voiceActors'].get('japanese'):
                va_text.append(f"🇯🇵 {character['voiceActors']['japanese']}")
            if character['voiceActors'].get('english'):
                va_text.append(f"🇺🇸 {character['voiceActors']['english']}")
            if va_text:
                embed.add_field(name="Voice Actors", value='\n'.join(va_text), inline=False)
        
        embed.set_footer(text=f"Character ID: {character['id']}")
        return embed
    
    @app_commands.command(name="roll", description="Roll for a random character!")
    async def roll(self, interaction: discord.Interaction):
        """Roll for a random character"""
        await interaction.response.defer()
        
        try:
            # Get random rarity
            rarity = await self.get_random_rarity()
            
            # Get random character of that rarity
            character = await asyncio.to_thread(self.db.get_random_character, rarity)
            
            if not character:
                await interaction.followup.send("❌ No characters available to roll!")
                return
            
            # Create embed
            embed = await self.create_character_embed(character, rarity)
            
            # Send result
            await interaction.followup.send(
                content=f"🎴 {interaction.user.mention} rolled a character!",
                embed=embed
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error rolling character: {str(e)}")
    
    @app_commands.command(name="daily", description="Claim your free daily roll!")
    async def daily(self, interaction: discord.Interaction):
        """Claim daily free roll"""
        user_id = interaction.user.id
        
        # Check cooldown
        if not await self.check_daily_cooldown(user_id):
            last_claim = self.user_cooldowns[user_id]
            time_left = timedelta(hours=24) - (datetime.now() - last_claim)
            hours = int(time_left.total_seconds() // 3600)
            minutes = int((time_left.total_seconds() % 3600) // 60)
            
            await interaction.response.send_message(
                f"⏰ You've already claimed your daily roll! Come back in {hours}h {minutes}m",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        try:
            # Get random rarity (slightly better odds for daily)
            rarity = random.choices(
                ['C', 'R', 'SR', 'SSR'],
                weights=[40, 35, 20, 5]
            )[0]
            
            character = await asyncio.to_thread(self.db.get_random_character, rarity)
            
            if not character:
                await interaction.followup.send("❌ No characters available!")
                return
            
            # Update cooldown
            self.user_cooldowns[user_id] = datetime.now()
            
            # Create embed
            embed = await self.create_character_embed(character, rarity)
            embed.title = f"🎁 Daily Roll - {embed.title}"
            
            await interaction.followup.send(
                content=f"🎁 {interaction.user.mention} claimed their daily roll!",
                embed=embed
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @app_commands.command(name="multi", description="Roll 10 characters at once!")
    async def multi(self, interaction: discord.Interaction):
        """Multi-roll (10 characters)"""
        await interaction.response.defer()
        
        try:
            results = []
            
            # Roll 10 times with guaranteed SR or better
            for i in range(10):
                if i == 9:  # Last roll guaranteed SR+
                    rarity = random.choices(['SR', 'SSR'], weights=[80, 20])[0]
                else:
                    rarity = await self.get_random_rarity()
                
                character = await asyncio.to_thread(self.db.get_random_character, rarity)
                if character:
                    results.append((character, rarity))
            
            if not results:
                await interaction.followup.send("❌ No characters available!")
                return
            
            # Create summary embed
            embed = discord.Embed(
                title="🎰 Multi Roll Results (10x)",
                description=f"{interaction.user.mention} rolled 10 characters!",
                color=0xFF6B9D
            )
            
            # Count rarities
            rarity_counts = {'C': 0, 'R': 0, 'SR': 0, 'SSR': 0}
            for _, rarity in results:
                rarity_counts[rarity] += 1
            
            # Add rarity summary
            summary = []
            for rarity, count in rarity_counts.items():
                if count > 0:
                    config = self.RARITY_CONFIG[rarity]
                    summary.append(f"{config['emoji']} {config['name']}: {count}")
            
            embed.add_field(name="Summary", value='\n'.join(summary), inline=False)
            
            # Add character list
            char_list = []
            for char, rarity in results[:5]:  # Show first 5
                config = self.RARITY_CONFIG[rarity]
                char_list.append(f"{config['emoji']} {char['name']} ({char['series']})")
            
            if len(results) > 5:
                char_list.append(f"... and {len(results) - 5} more!")
            
            embed.add_field(name="Characters", value='\n'.join(char_list), inline=False)
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")
    
    @app_commands.command(name="dex", description="View character information")
    @app_commands.describe(character_name="Name of the character to look up")
    async def dex(self, interaction: discord.Interaction, character_name: str):
        """Look up character in dex"""
        await interaction.response.defer()
        
        try:
            # Search for character
            characters = await asyncio.to_thread(
                self.db.search_characters,
                character_name,
                {'limit': 1}
            )
            
            if not characters:
                await interaction.followup.send(f"❌ Character '{character_name}' not found!")
                return
            
            character = characters[0]
            
            # Create detailed embed
            embed = discord.Embed(
                title=f"📚 {character['name']}",
                description=character.get('description', ''),
                color=self.RARITY_CONFIG[character['rarity']]['color']
            )
            
            # Add image
            if character.get('images'):
                embed.set_image(url=character['images'][0])
            
            # Add fields
            embed.add_field(name="Series", value=character['series'], inline=True)
            embed.add_field(
                name="Rarity",
                value=f"{self.RARITY_CONFIG[character['rarity']]['emoji']} {self.RARITY_CONFIG[character['rarity']]['name']}",
                inline=True
            )
            embed.add_field(name="Total Images", value=str(character.get('imageCount', 0)), inline=True)
            
            # Add aliases
            if character.get('aliases'):
                embed.add_field(
                    name="Aliases",
                    value=', '.join(character['aliases'][:5]),
                    inline=False
                )
            
            # Add tags
            if character.get('tags'):
                embed.add_field(
                    name="Tags",
                    value=', '.join(character['tags'][:10]),
                    inline=False
                )
            
            # Add website link
            website_url = f"https://your-firebase-site.web.app/#dex?character={character['id']}"
            embed.add_field(
                name="View More",
                value=f"[View on Website]({website_url})",
                inline=False
            )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}")

async def setup(bot):
    """Setup function for cog"""
    await bot.add_cog(GachaCog(bot))
