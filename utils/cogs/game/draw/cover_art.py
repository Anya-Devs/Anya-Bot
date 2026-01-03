"""
Cover Art System for Gacha Characters
Uses Danbooru and Safebooru for high-quality anime images
"""

import discord
import aiohttp
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
import asyncio
import logging
from .multisearch import MultiSourceImageSearch

logger = logging.getLogger(__name__)

class CoverArtSystem:
    """Cover art system using Danbooru and Safebooru APIs"""
    
    def __init__(self, quest_data):
        self.quest_data = quest_data
        self.session = None
        self.multi_search = MultiSourceImageSearch()
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={'User-Agent': 'Anya-Bot-CoverArt/1.0'}
            )
        return self.session
    
    async def search_cover_art(self, character_name: str, series_name: str = None, page: int = 1, limit: int = 30) -> Tuple[List[Dict], int]:
        """Search for cover art using multiple sources with deduplication"""
        logger.info(f"[Cover Art] Searching: '{character_name}' from '{series_name}' (page {page})")
        
        try:
            # Use multi-source search with deduplication
            images, max_pages = await self.multi_search.search_all_sources(
                character_name, series_name, page, limit
            )
            
            logger.info(f"[Cover Art] Found {len(images)} unique images from multiple sources")
            return images, max_pages
            
        except Exception as e:
            logger.error(f"[Cover Art] Multi-source search error: {e}", exc_info=True)
            return [], 1
    
    def _clean_series_name(self, series_name: str) -> str:
        """Clean and format series name for Danbooru search"""
        import re
        
        # Remove common suffixes and excess
        suffixes_to_remove = [
            r'\s*-\s*.*$',  # Anything after dash
            r'\s*\(\d+\)\s*$',  # Years in parentheses
            r'\s*\([^)]*\)\s*$',  # Anything in parentheses
            r'\s*\[[^\]]*\]\s*$',  # Anything in brackets
            r'\s*Season\s*\d+\s*$',  # Season numbers
            r'\s*Part\s*\d+\s*$',  # Part numbers
            r'\s*Vol\.\s*\d+\s*$',  # Volume numbers
            r'\s*\d+\s*$',  # Standalone numbers
            r'\s*The\s+',  # Remove "The" prefix
            r'\s*A\s+',  # Remove "A" prefix
        ]
        
        cleaned = series_name
        for suffix in suffixes_to_remove:
            cleaned = re.sub(suffix, '', cleaned, flags=re.IGNORECASE)
        
        # Handle specific series name mappings
        series_mappings = {
            'Re:Zero kara Hajimeru Isekai Seikatsu': 're:zero',
            'Re:Zero Starting Life in Another World': 're:zero',
            'Spy x Family': 'spy_x_family',
            'Dr. Stone': 'dr.stone',
            'My Hero Academia': 'boku_no_hero_academia',
            'Attack on Titan': 'shingeki_no_kyojin',
            'Demon Slayer': 'kimetsu_no_yaiba',
            'Sword Art Online': 'sword_art_online',
            'One Piece': 'one_piece',
            'Naruto': 'naruto',
            'Bleach': 'bleach',
            'Death Note': 'death_note',
            'Fullmetal Alchemist': 'fullmetal_alchemist',
            'Steins;Gate': 'steins_gate',
            'Fate/Stay Night': 'fate_stay_night',
            'Puella Magi Madoka Magica': 'puella_magi_madoka_magica',
            'Neon Genesis Evangelion': 'neon_genesis_evangelion',
            'Cowboy Bebop': 'cowboy_bebop',
            'Trigun': 'trigun',
            'Yu-Gi-Oh!': 'yu-gi-oh',
            'Pokémon': 'pokemon',
            'Dragon Ball Z': 'dragon_ball',
            'Sailor Moon': 'sailor_moon',
            'Cardcaptor Sakura': 'cardcaptor_sakura',
            'Inuyasha': 'inuyasha',
            'Berserk': 'berserk',
            'Vinland Saga': 'vinland_saga',
            'Jujutsu Kaisen': 'jujutsu_kaisen',
            'Chainsaw Man': 'chainsaw_man',
            'Tokyo Revengers': 'tokyo_revengers',
            'Black Clover': 'black_clover',
            'Hunter x Hunter': 'hunter_x_hunter',
            'One-Punch Man': 'one_punch_man',
            'Mob Psycho 100': 'mob_psycho_100',
            'The Promised Neverland': 'promised_neverland',
            'Fire Force': 'fire_force',
            'Food Wars!': 'food_wars',
            'Haikyuu!!': 'haikyuu',
            'Kuroko\'s Basketball': 'kuroko_no_basuke',
            'Free!': 'free',
            'Yuri!!! on Ice': 'yuri_on_ice',
            'Banana Fish': 'banana_fish',
            'Given': 'given',
            'SK8 the Infinity': 'sk8_the_infinity',
            'Horimiya': 'horimiya',
            'Kaguya-sama: Love Is War': 'kaguya_sama_love_is_war',
            'The Quintessential Quintuplets': 'gotoubun_no_hanayome',
            'We Never Learn': 'bokutachi_wa_benkyou_shinainai',
            'Rent-a-Girlfriend': 'kanojo_okarishimasu',
            'To Love Ru': 'to_love_ru',
            'High School DxD': 'high_school_dxd',
            'Monster Musume': 'monster_musume',
            'Miss Kobayashi\'s Dragon Maid': 'kobayashi_san_chi_no_maid_dragon',
            'Nichijou': 'nichijou',
            'Azumanga Daioh': 'azumanga_daioh',
            'Lucky Star': 'lucky_star',
            'The Melancholy of Haruhi Suzumiya': 'haruhi_suzumiya',
            'K-On!': 'k_on',
            'Hidamari Sketch': 'hidamari_sketch',
            'Yuru Yuri': 'yuru_yuri',
            'Kin-iro Mosaic': 'kiniro_mosaic',
            'Is the Order a Rabbit?': 'gochuumon_wa_usagi_desu_ka',
            'New Game!': 'new_game',
            'Comic Girls': 'comic_girls',
            'Hanasaku Iroha': 'hanasaku_iroha',
            'Sora no Woto': 'sora_no_woto',
            'Kantai Collection': 'kantai_collection',
            'Girls und Panzer': 'girls_und_panzer',
            'Strike Witches': 'strike_witches',
            'Violet Evergarden': 'violet_evergarden',
            'A Place Further Than the Universe': 'uchuu_yori_mo_tooi_basho',
            'Yuki Yuna is a Hero': 'yuki_yuna_wa_yuusha_de_aru',
            'Made in Abyss': 'made_in_abyss',
            'Land of the Lustrous': 'houseki_no_kuni',
            'Keep Your Hands Off Eizouken!': 'eizouken_ni_wa_te_o_dasu_na',
            'Science Fell in Love, So I Tried to Prove It': 'rikei_ga_koi_ni_ochita_no_de_shoumei_shitemita',
        }
        
        # Check for exact matches first
        for full_name, short_name in series_mappings.items():
            if cleaned.lower() == full_name.lower():
                return short_name
        
        # Check for partial matches
        for full_name, short_name in series_mappings.items():
            if full_name.lower() in cleaned.lower() or cleaned.lower() in full_name.lower():
                return short_name
        
        # Default cleaning: spaces to underscores, lowercase, remove special chars
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', cleaned)  # Remove special chars except spaces
        cleaned = re.sub(r'\s+', '_', cleaned.strip())  # Replace spaces with underscores
        cleaned = cleaned.lower()
        
        return cleaned if cleaned else series_name.lower().replace(' ', '_')
    
    async def _find_max_pages(self, session, search_query: str, max_test: int) -> int:
        """Binary search to find actual maximum pages"""
        low, high = 1, max_test
        result = 1
        
        while low <= high:
            mid = (low + high) // 2
            try:
                params = {
                    'tags': search_query,
                    'limit': 1,
                    'page': mid,
                    'format': 'json'
                }
                
                async with session.get('https://danbooru.donmai.us/posts.json', params=params, timeout=aiohttp.ClientTimeout(total=2)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data:  # Found results
                            result = mid
                            low = mid + 1
                        else:
                            high = mid - 1
                    else:
                        high = mid - 1
            except:
                high = mid - 1
        
        return result
    
    async def _search_danbooru_fast(self, query: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Fast Danbooru search with timeout optimization"""
        session = await self.get_session()
        
        params = {
            'tags': query,
            'limit': limit,
            'page': page,
            'format': 'json'
        }
        
        try:
            async with session.get('https://danbooru.donmai.us/posts.json', params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._process_danbooru_results(data)
                else:
                    return []
        except asyncio.TimeoutError:
            logger.warning(f"Danbooru timeout for page {page}")
            return []
        except Exception as e:
            logger.error(f"Danbooru search error: {e}")
            return []
    
    async def _search_safebooru_fast(self, query: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Fast Safebooru search with timeout optimization"""
        session = await self.get_session()
        
        params = {
            'tags': query,
            'limit': limit,
            'pid': page - 1,  # Safebooru uses 0-based page indexing
            'format': 'json'
        }
        
        try:
            async with session.get('https://safebooru.donmai.us/posts.json', params=params, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return self._process_safebooru_results(data)
                else:
                    return []
        except asyncio.TimeoutError:
            logger.warning(f"Safebooru timeout for page {page}")
            return []
        except Exception as e:
            logger.error(f"Safebooru search error: {e}")
            return []
    
    async def _search_danbooru(self, query: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Search Danbooru for images"""
        session = await self.get_session()
        
        params = {
            'tags': query,
            'limit': limit,
            'page': page,
            'format': 'json'
        }
        
        async with session.get('https://danbooru.donmai.us/posts.json', params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return self._process_danbooru_results(data)
            else:
                return []
    
    async def _search_safebooru(self, query: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Search Safebooru for images"""
        session = await self.get_session()
        
        params = {
            'tags': query,
            'limit': limit,
            'pid': page - 1,  # Safebooru uses 0-based page indexing
            'format': 'json'
        }
        
        async with session.get('https://safebooru.donmai.us/posts.json', params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                return self._process_safebooru_results(data)
            else:
                return []
    
    def _process_danbooru_results(self, data: List[Dict]) -> List[Dict]:
        """Process Danbooru API results"""
        processed = []
        
        for post in data:
            if not post.get('file_url') or post.get('rating') != 's':
                continue
            
            # Use large_file_url as preview if available, otherwise preview_file_url, otherwise file_url
            preview_url = post.get('large_file_url') or post.get('preview_file_url') or post.get('file_url')
                
            processed.append({
                'id': post.get('id'),
                'url': post.get('file_url'),
                'preview_url': preview_url,
                'source': 'Danbooru',
                'tags': post.get('tag_string', '').split(),
                'score': post.get('score', 0),
                'width': post.get('image_width', 0),
                'height': post.get('image_height', 0),
                'created_at': post.get('created_at')
            })
        
        return processed
    
    def _process_safebooru_results(self, data: List[Dict]) -> List[Dict]:
        """Process Safebooru API results"""
        processed = []
        
        for post in data:
            if not post.get('file_url') or post.get('rating') != 's':
                continue
                
            processed.append({
                'id': post.get('id'),
                'url': post.get('file_url'),
                'preview_url': post.get('preview_url'),
                'source': 'Safebooru',
                'tags': post.get('tags', '').split(),
                'score': post.get('score', 0),
                'width': post.get('width', 0),
                'height': post.get('height', 0),
                'created_at': post.get('created_at')
            })
        
        return processed
    
    async def create_cover_art_embeds(
        self,
        character: Dict,
        images: List[Dict],
        page: int = 1,
        total_pages: int = 1
    ) -> List[discord.Embed]:
        """Create embeds for cover art display with clear UID and character info"""
        try:
            char_name = character.get("name", "Unknown")
            rarity = character.get("rarity", "common")
            uid = character.get("uid", "UNKNOWN")
            series = character.get("anime", "Unknown")

            from ..const import GACHA_RARITY_TIERS
            rarity_data = GACHA_RARITY_TIERS.get(rarity, GACHA_RARITY_TIERS["common"])

            costs = {
                "common": 100,
                "uncommon": 200,
                "rare": 500,
                "epic": 1000,
                "legendary": 2000,
            }
            cost = costs.get(rarity, 100)

            embeds: List[discord.Embed] = []
            is_search_mode = uid == "SEARCH"

            for i, img in enumerate(images[:3], start=1):
                # Create embed with character info in title
                if is_search_mode:
                    title = f"🔍 {char_name} - Option {i}"
                    description = f"*{series}*\n**Preview Only** - Own this character to purchase"
                else:
                    title = f"🎨 {char_name} [`{uid.upper()}`] - Option {i}"
                    description = f"*{series}* • {rarity_data['emoji']} {rarity.title()} • Cost: **{cost}** pts"
                
                embed = discord.Embed(
                    title=title,
                    description=description,
                    color=rarity_data["color"]
                )

                if img.get("preview_url"):
                    embed.set_image(url=img["preview_url"])

                # Footer with buy info and score
                if is_search_mode:
                    footer_text = f"Page {page}/{total_pages} • ID: {img['id']} • Score: {img['score']}"
                else:
                    footer_text = f"Page {page}/{total_pages} • Buy: .cover buy {uid.upper()} {img['id']}"
                
                embed.set_footer(text=footer_text)
                embeds.append(embed)

            return embeds

        except Exception as e:
            logger.error(f"Error creating cover art embeds: {e}")
            return []

    async def purchase_cover_art(self, user_id: str, guild_id: str, character_uid: str, image_id: int, custom_name: str = None) -> Tuple[bool, str]:
        """Purchase cover art for a character and store in database"""
        
        # Check if user owns the character
        char = await self._get_character(user_id, guild_id, character_uid)
        if not char:
            return False, "You don't own this character!"
        
        # Check if cover art is already unlocked
        if char.get('cover_unlocked', False):
            return False, "Cover art is already unlocked for this character!"
        
        # Calculate cost (based on character rarity)
        from ..const import GACHA_RARITY_TIERS
        rarity = char.get('rarity', 'common')
        rarity_data = GACHA_RARITY_TIERS.get(rarity, GACHA_RARITY_TIERS['common'])
        
        costs = {
            'common': 100,
            'uncommon': 200,
            'rare': 500,
            'epic': 1000,
            'legendary': 2000
        }
        cost = costs.get(rarity, 100)
        
        # Check user balance
        balance = await self.quest_data.get_balance(user_id, guild_id)
        if balance < cost:
            return False, f"You need **{cost}** stella points but only have **{balance:,}**!"
        
        # Generate custom name if not provided
        if not custom_name:
            custom_name = f"{char.get('name', 'Art')}_{image_id}"
        
        # Deduct cost and unlock cover art
        await self.quest_data.add_balance(user_id, guild_id, -cost)
        await self._unlock_cover_art(user_id, guild_id, character_uid, image_id, custom_name)
        
        return True, f"Successfully purchased cover art '{custom_name}' for **{cost}** stella points!"
    
    async def _unlock_cover_art(self, user_id: str, guild_id: str, character_uid: str, image_id: int, custom_name: str):
        """Unlock cover art for a character and store in database"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # Create cover art data structure
            cover_art_data = {
                'image_id': image_id,
                'custom_name': custom_name,
                'unlocked_at': datetime.now(timezone.utc).isoformat(),
                'selected': False  # Not selected by default
            }
            
            await server_col.update_one(
                {"guild_id": guild_id},
                {
                    "$set": {
                        f"members.{user_id}.characters.{character_uid.lower()}.cover_unlocked": True,
                        f"members.{user_id}.characters.{character_uid.lower()}.cover_art": cover_art_data
                    }
                }
            )
        except Exception as e:
            logger.error(f"Error unlocking cover art: {e}")
    
    async def set_selected_cover_art(self, user_id: str, guild_id: str, character_uid: str, cover_art_name: str) -> Tuple[bool, str]:
        """Set a specific cover art as the selected image for a character"""
        
        # Check if user owns the character
        char = await self._get_character(user_id, guild_id, character_uid)
        if not char:
            return False, "You don't own this character!"
        
        # Get user's cover art collection
        cover_arts = await self._get_user_cover_arts(user_id, guild_id)
        
        # Find the specific cover art by name
        target_art = None
        for art in cover_arts:
            if art.get('custom_name') == cover_art_name and art.get('character_uid') == character_uid.lower():
                target_art = art
                break
        
        if not target_art:
            return False, f"Cover art '{cover_art_name}' not found for this character!"
        
        # Update the selected cover art
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": {
                    f"members.{user_id}.characters.{character_uid.lower()}.cover_art.selected": True,
                    f"members.{user_id}.characters.{character_uid.lower()}.cover_art.selected_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            return True, f"Successfully set '{cover_art_name}' as the selected cover art!"
            
        except Exception as e:
            logger.error(f"Error setting selected cover art: {e}")
            return False, "Error setting selected cover art!"
    
    async def _get_user_cover_arts(self, user_id: str, guild_id: str) -> List[Dict]:
        """Get all cover arts owned by a user"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.characters": 1}
            )
            
            if result:
                characters = result.get("members", {}).get(user_id, {}).get("characters", {})
                cover_arts = []
                
                for char_uid, char_data in characters.items():
                    if char_data.get('cover_unlocked') and char_data.get('cover_art'):
                        art = char_data['cover_art'].copy()
                        art['character_uid'] = char_uid
                        art['character_name'] = char_data.get('name', 'Unknown')
                        cover_arts.append(art)
                
                return cover_arts
            
        except Exception as e:
            logger.error(f"Error getting user cover arts: {e}")
        
        return []
    
    async def set_active_cover_art(self, user_id: str, guild_id: str, character_uid: str, image_id: int) -> bool:
        """Set cover art as active for a character"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # Get the character to find the cover art URL
            char = await self._get_character(user_id, guild_id, character_uid)
            if not char or not char.get('cover_art'):
                return False
            
            # Mark as active
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": {
                    f"members.{user_id}.gacha_inventory.$[elem].active_cover_id": image_id,
                    f"members.{user_id}.gacha_inventory.$[elem].active_cover_url": char['cover_art'].get('image_url', '')
                }},
                array_filters=[{"elem.uid": character_uid.upper()}]
            )
            
            return True
        except Exception as e:
            logger.error(f"Error setting active cover art: {e}", exc_info=True)
            return False
    
    async def get_active_cover_art_url(self, user_id: str, guild_id: str, character_uid: str) -> Optional[str]:
        """Get the active cover art URL for a character from gacha_inventory"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.gacha_inventory": 1}
            )
            
            if result:
                inventory = result.get("members", {}).get(user_id, {}).get("gacha_inventory", [])
                for char in inventory:
                    if char.get("uid", "").upper() == character_uid.upper():
                        return char.get('active_cover_url')
        except Exception as e:
            logger.error(f"Error getting active cover art URL: {e}")
        
        return None
    
    async def get_selected_cover_art(self, user_id: str, guild_id: str, character_uid: str) -> Optional[Dict]:
        """Get the selected cover art for a character"""
        try:
            char = await self._get_character(user_id, guild_id, character_uid)
            if char and char.get('cover_unlocked') and char.get('cover_art'):
                cover_art = char['cover_art']
                if cover_art.get('selected', False):
                    return cover_art
        except Exception as e:
            logger.error(f"Error getting selected cover art: {e}")
        
        return None
    
    async def _get_character(self, user_id: str, guild_id: str, uid: str) -> Optional[Dict]:
        """Get character from user's inventory - checks both gacha_inventory and characters"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # First check gacha_inventory (primary storage)
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.gacha_inventory": 1}
            )
            
            if result:
                inventory = result.get("members", {}).get(user_id, {}).get("gacha_inventory", [])
                for char in inventory:
                    if char.get("uid", "").upper() == uid.upper():
                        return char
            
            # Fallback: check characters collection
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.characters.{uid.lower()}": 1}
            )
            
            if result:
                characters = result.get("members", {}).get(user_id, {}).get("characters", {})
                return characters.get(uid.lower())
        except Exception as e:
            logger.error(f"Error getting character: {e}")
        
        return None
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()


class CoverArtView(discord.ui.View):
    """View for browsing cover art with pagination"""
    
    def __init__(self, cover_system: CoverArtSystem, character: Dict, user_id: str, guild_id: str, initial_images: List[Dict], current_page: int = 1, total_pages: int = 1):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.cover_system = cover_system
        self.character = character
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_images = initial_images
        self.current_page = current_page
        self.total_pages = total_pages
        self.message = None
        self.randomized = False  # Track if current order is randomized
        
        # Set the jump button label dynamically
        for child in self.children:
            if child.custom_id == "jump_page":
                child.label = f"{self.current_page}/{self.total_pages}"
                break
    
    async def on_timeout(self):
        """Disable buttons when view times out"""
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.grey, custom_id="prev_page")
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.current_page <= 1:
            await interaction.response.send_message("You're already on the first page!", ephemeral=True)
            return
        
        # Disable button temporarily
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            # Fetch previous page with fast loading
            char_name = self.character.get('name', '')
            series_name = self.character.get('anime', '')
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page - 1, 30)
            
            if new_images:
                self.current_page -= 1
                self.current_images = new_images
                
                # Update embeds
                embeds = await self.cover_system.create_cover_art_embeds(
                    self.character, new_images, self.current_page, self.total_pages
                )
                
                # Update jump button label
                for child in self.children:
                    if child.custom_id == "jump_page":
                        child.label = f"{self.current_page}/{self.total_pages}"
                        break
                
                await interaction.message.edit(embeds=embeds, view=self)
            else:
                await interaction.followup.send("No more images available!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error loading previous page: {e}")
            await interaction.followup.send("Error loading previous page!", ephemeral=True)
        finally:
            button.disabled = False
            await interaction.message.edit(view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.grey, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if self.current_page >= self.total_pages:
            await interaction.response.send_message("You're already on the last page!", ephemeral=True)
            return
        
        # Disable button temporarily
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            # Fetch next page with fast loading
            char_name = self.character.get('name', '')
            series_name = self.character.get('anime', '')
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page + 1, 30)
            
            if new_images:
                self.current_page += 1
                self.current_images = new_images
                
                # Update embeds
                embeds = await self.cover_system.create_cover_art_embeds(
                    self.character, new_images, self.current_page, self.total_pages
                )
                
                # Update jump button label
                for child in self.children:
                    if child.custom_id == "jump_page":
                        child.label = f"{self.current_page}/{self.total_pages}"
                        break
                
                await interaction.message.edit(embeds=embeds, view=self)
            else:
                await interaction.followup.send("No more images available!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error loading next page: {e}")
            await interaction.followup.send("Error loading next page!", ephemeral=True)
        finally:
            button.disabled = False
            await interaction.message.edit(view=self)
    
    @discord.ui.button(label="page/max", style=discord.ButtonStyle.secondary, custom_id="jump_page")
    async def jump_to_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Jump to a specific page"""
        # Create a modal for page input
        modal = JumpToPageModal(self.current_page, self.total_pages)
        await interaction.response.send_modal(modal)
        
        # Wait for modal submission
        await modal.wait()
        
        if modal.page_number is not None:
            target_page = modal.page_number
            
            if target_page < 1 or target_page > self.total_pages:
                await interaction.followup.send(f"Page must be between 1 and {self.total_pages}!", ephemeral=True)
                return
            
            if target_page == self.current_page:
                await interaction.followup.send("You're already on that page!", ephemeral=True)
                return
            
            try:
                # Fetch target page with fast loading
                char_name = self.character.get('name', '')
                series_name = self.character.get('anime', '')
                new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, target_page, 30)
                
                if new_images:
                    self.current_page = target_page
                    self.current_images = new_images
                    
                    # Update embeds
                    embeds = await self.cover_system.create_cover_art_embeds(
                        self.character, new_images, self.current_page, self.total_pages
                    )
                    
                    # Update jump button label
                    button.label = f"{self.current_page}/{self.total_pages}"
                    
                    await interaction.message.edit(embeds=embeds, view=self)
                    await interaction.followup.send(f"Jumped to page {target_page}!", ephemeral=True)
                else:
                    await interaction.followup.send("No images available on that page!", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error jumping to page: {e}")
                await interaction.followup.send("Error jumping to page!", ephemeral=True)
    
    
    @discord.ui.button(label="🔍 View Details", style=discord.ButtonStyle.green, custom_id="view_details")
    async def view_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View detailed information about current images"""
        details_embed = discord.Embed(
            title="📊 Image Details",
            description=f"Page {self.current_page}/{self.total_pages} • {'Randomized' if self.randomized else 'Original Order'}",
            color=discord.Color.blue()
        )
        
        for i, img in enumerate(self.current_images[:3], 1):
            details_embed.add_field(
                name=f"🖼️ Option {i}",
                value=f"**ID:** {img['id']}\n"
                      f"**Source:** {img['source']}\n"
                      f"**Score:** {img['score']}\n"
                      f"**Size:** {img['width']}×{img['height']}\n"
                      f"**Tags:** {', '.join(img['tags'][:5])}",
                inline=True
            )
        
        await interaction.response.send_message(embed=details_embed, ephemeral=True)
    


class CoverArtSearchView(discord.ui.View):
    """View for browsing cover art with pagination (no purchase buttons)"""
    
    def __init__(self, cover_system: CoverArtSystem, character: Dict, user_id: str, guild_id: str, initial_images: List[Dict], current_page: int = 1, total_pages: int = 1):
        super().__init__(timeout=180)  # 3 minutes timeout
        self.cover_system = cover_system
        self.character = character
        self.user_id = user_id
        self.guild_id = guild_id
        self.current_images = initial_images
        self.current_page = current_page
        self.total_pages = total_pages
        self.message = None
        self.current_display_index = 0  # Which image is currently displayed
        
        # Update page button label
        self._update_page_label()
    
    def _update_page_label(self):
        """Update the page button label"""
        for child in self.children:
            if child.custom_id == "page_info":
                child.label = f"Page {self.current_page}/{self.total_pages}"
                break
    
    def _create_embed(self) -> discord.Embed:
        """Create single clean embed for current images"""
        char_name = self.character.get('name', 'Unknown')
        series_name = self.character.get('anime', 'Unknown')
        
        embed = discord.Embed(
            title=f"🔍 {char_name}",
            description=f"*{series_name}* • Page {self.current_page}/{self.total_pages}\n"
                        f"Found **{len(self.current_images)}** images",
            color=discord.Color.purple()
        )
        
        # Show first 3 images as options
        for i, img in enumerate(self.current_images[:3], 1):
            embed.add_field(
                name=f"🖼️ Option {i}",
                value=f"**ID:** `{img['id']}`\n"
                      f"**Source:** {img['source']}\n"
                      f"**Score:** {img['score']} • {img['width']}x{img['height']}",
                inline=True
            )
        
        # Set currently displayed image
        if self.current_images and self.current_display_index < len(self.current_images):
            img = self.current_images[self.current_display_index]
            if img.get('preview_url'):
                embed.set_image(url=img['preview_url'])
        
        embed.set_footer(text="Use .cover gallery <UID> to purchase for your character")
        return embed
    
    async def on_timeout(self):
        """Disable buttons when view times out"""
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except:
                pass
    
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.grey, custom_id="prev_page", row=0)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page"""
        if self.current_page <= 1:
            await interaction.response.send_message("You're already on the first page!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            char_name = self.character.get('name', '')
            series_name = self.character.get('anime', '')
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page - 1, 9)
            
            if new_images:
                self.current_page -= 1
                self.current_images = new_images
                self.current_display_index = 0
                self._update_page_label()
                await interaction.message.edit(embed=self._create_embed(), view=self)
            else:
                await interaction.followup.send("No more images available!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error loading previous page: {e}")
            await interaction.followup.send("Error loading page!", ephemeral=True)
    
    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, custom_id="page_info", row=0, disabled=True)
    async def page_info(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Display current page (non-interactive)"""
        pass
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.grey, custom_id="next_page", row=0)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page"""
        if self.current_page >= self.total_pages:
            await interaction.response.send_message("You're already on the last page!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        try:
            char_name = self.character.get('name', '')
            series_name = self.character.get('anime', '')
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page + 1, 9)
            
            if new_images:
                self.current_page += 1
                self.current_images = new_images
                self.current_display_index = 0
                self._update_page_label()
                await interaction.message.edit(embed=self._create_embed(), view=self)
            else:
                await interaction.followup.send("No more images available!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error loading next page: {e}")
            await interaction.followup.send("Error loading page!", ephemeral=True)
    
    @discord.ui.button(label="1️⃣", style=discord.ButtonStyle.blurple, custom_id="show_1", row=1)
    async def show_image_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show image 1"""
        if len(self.current_images) >= 1:
            self.current_display_index = 0
            await interaction.response.edit_message(embed=self._create_embed(), view=self)
        else:
            await interaction.response.send_message("No image available!", ephemeral=True)
    
    @discord.ui.button(label="2️⃣", style=discord.ButtonStyle.blurple, custom_id="show_2", row=1)
    async def show_image_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show image 2"""
        if len(self.current_images) >= 2:
            self.current_display_index = 1
            await interaction.response.edit_message(embed=self._create_embed(), view=self)
        else:
            await interaction.response.send_message("No image available!", ephemeral=True)
    
    @discord.ui.button(label="3️⃣", style=discord.ButtonStyle.blurple, custom_id="show_3", row=1)
    async def show_image_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show image 3"""
        if len(self.current_images) >= 3:
            self.current_display_index = 2
            await interaction.response.edit_message(embed=self._create_embed(), view=self)
        else:
            await interaction.response.send_message("No image available!", ephemeral=True)
    
    @discord.ui.button(label="🔀 Shuffle", style=discord.ButtonStyle.grey, custom_id="shuffle", row=1)
    async def shuffle_images(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Shuffle the current images"""
        if len(self.current_images) > 1:
            random.shuffle(self.current_images)
            self.current_display_index = 0
            await interaction.response.edit_message(embed=self._create_embed(), view=self)
        else:
            await interaction.response.send_message("Not enough images to shuffle!", ephemeral=True)


class JumpToPageModal(discord.ui.Modal):
    """Modal for jumping to a specific page"""
    
    def __init__(self, current_page: int, max_pages: int):
        super().__init__(title=f"Jump to Page (1-{max_pages})")
        self.current_page = current_page
        self.max_pages = max_pages
        self.page_number = None
        
        self.page_input = discord.ui.TextInput(
            label="Page Number",
            placeholder=f"Enter page number (1-{max_pages})",
            required=True,
            style=discord.TextStyle.short,
            max_length=4
        )
        self.add_item(self.page_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission"""
        try:
            page_num = int(self.page_input.value)
            self.page_number = page_num
            await interaction.response.send_message("Jumping to page...", ephemeral=True)
        except ValueError:
            self.page_number = None
            await interaction.response.send_message("Please enter a valid number!", ephemeral=True)
    
    async def on_error(self, interaction: discord.Interaction, error: Exception):
        """Handle modal errors"""
        self.page_number = None
        await interaction.response.send_message("An error occurred. Please try again.", ephemeral=True)
