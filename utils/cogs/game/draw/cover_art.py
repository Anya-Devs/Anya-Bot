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

logger = logging.getLogger(__name__)

class CoverArtSystem:
    """Cover art system using Danbooru and Safebooru APIs"""
    
    def __init__(self, quest_data):
        self.quest_data = quest_data
        self.session = None
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={'User-Agent': 'Anya-Bot-CoverArt/1.0'}
            )
        return self.session
    
    async def search_cover_art(self, character_name: str, series_name: str = None, page: int = 1, limit: int = 30) -> Tuple[List[Dict], int]:
        """Search for cover art using Danbooru and Safebooru with unlimited pagination"""
        session = await self.get_session()
        all_images = []
        
        # Format character name for Danbooru/Safebooru (underscores for spaces)
        formatted_character = character_name.replace(' ', '_').lower()
        
        # Build search terms in proper Danbooru format
        search_terms = [formatted_character]
        
        # Add series in parentheses if provided
        if series_name:
            # Clean and format series name
            cleaned_series = self._clean_series_name(series_name)
            if cleaned_series:
                search_terms[0] = f"{formatted_character}_({cleaned_series})"
        
        # Add safety filters
        search_terms.extend(["rating:safe", "-ai_generated"])
        
        search_query = " ".join(search_terms)
        
        # Try to get total count first for max page detection
        max_pages = 100  # Default high value
        try:
            # Quick count query to determine actual max pages
            count_params = {
                'tags': search_query,
                'limit': 1,
                'page': 1,
                'format': 'json'
            }
            
            async with session.get('https://danbooru.donmai.us/posts.json', params=count_params) as resp:
                if resp.status == 200:
                    # Check if there are more pages by trying page 1000
                    test_params = count_params.copy()
                    test_params['page'] = 1000
                    
                    async with session.get('https://danbooru.donmai.us/posts.json', params=test_params) as test_resp:
                        if test_resp.status == 200:
                            test_data = await test_resp.json()
                            if not test_data:  # No results on page 1000, so max is less
                                # Binary search for actual max page
                                max_pages = await self._find_max_pages(session, search_query, 1000)
                        else:
                            max_pages = await self._find_max_pages(session, search_query, 1000)
        except Exception as e:
            logger.debug(f"Error detecting max pages: {e}")
        
        # Fetch images with organized traffic management
        try:
            danbooru_images = await self._search_danbooru_fast(search_query, page, limit)
            all_images.extend(danbooru_images)
        except Exception as e:
            logger.error(f"Danbooru search error: {e}")
        
        # Try Safebooru as backup
        if len(all_images) < limit:
            try:
                safebooru_images = await self._search_safebooru_fast(search_query, page, limit - len(all_images))
                all_images.extend(safebooru_images)
            except Exception as e:
                logger.error(f"Safebooru search error: {e}")
        
        return all_images[:limit], max_pages
    
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
     total_pages: int = 1 ) -> List[discord.Embed]:

      try:
        char_name = character.get("name", "Unknown")
        rarity = character.get("rarity", "common")
        uid = character.get("uid", "UNKNOWN")

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

        for i, img in enumerate(images[:3], start=1):
            embed = discord.Embed(color=rarity_data["color"])

            if img.get("preview_url"):
                embed.set_image(url=img["preview_url"])

            # Footer with buy info and score (different for search vs gallery)
            if uid == "SEARCH":
                # Search mode - show ID and score, but can't buy directly
                footer_text = f"ID: {img['id']} • Score: {img['score']} • Use .cover gallery <UID> to purchase"
            else:
                # Gallery mode - show actual buy command
                footer_text = f"ID: {img['id']} • Score: {img['score']} • Buy: .cover buy {uid} {img['id']}"
            
            embed.set_footer(text=footer_text)

            embeds.append(embed)

        return embeds

      except Exception as e:
        print(f"Error creating cover art embeds: {e}")
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
        """Get character from user's inventory"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
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
                child.label = f"< {self.current_page}/{self.total_pages} >"
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
                        child.label = f"< {self.current_page}/{self.total_pages} >"
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
                        child.label = f"< {self.current_page}/{self.total_pages} >"
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
    
    @discord.ui.button(label="< page/max >", style=discord.ButtonStyle.secondary, custom_id="jump_page")
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
                    button.label = f"< {self.current_page}/{self.total_pages} >"
                    
                    await interaction.message.edit(embeds=embeds, view=self)
                    await interaction.followup.send(f"Jumped to page {target_page}!", ephemeral=True)
                else:
                    await interaction.followup.send("No images available on that page!", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error jumping to page: {e}")
                await interaction.followup.send("Error jumping to page!", ephemeral=True)
    
    @discord.ui.button(label="🔀 Randomize", style=discord.ButtonStyle.blurple, custom_id="randomize")
    async def randomize_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Randomize the order of current images"""
        import random
        
        # Disable button temporarily
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            # Randomize current images order
            random.shuffle(self.current_images)
            self.randomized = not self.randomized  # Toggle state
            
            # Update embeds with randomized images
            embeds = await self.cover_system.create_cover_art_embeds(
                self.character, self.current_images, self.current_page, self.total_pages
            )
            
            # Update button label to reflect state
            button.label = "🔀 Unshuffle" if self.randomized else "🔀 Randomize"
            
            await interaction.message.edit(embeds=embeds, view=self)
            await interaction.followup.send(f"{'🔀 Images randomized!' if self.randomized else '🔀 Images restored to original order!'}", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error randomizing images: {e}")
            await interaction.followup.send("Error randomizing images!", ephemeral=True)
        finally:
            button.disabled = False
            await interaction.message.edit(view=self)
    
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
    
    @discord.ui.button(label="🛍️ Buy Option 1", style=discord.ButtonStyle.green, custom_id="buy_1")
    async def buy_option_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Purchase first cover art option"""
        await self._purchase_option(interaction, 0)
    
    @discord.ui.button(label="🛍️ Buy Option 2", style=discord.ButtonStyle.green, custom_id="buy_2")
    async def buy_option_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Purchase second cover art option"""
        await self._purchase_option(interaction, 1)
    
    @discord.ui.button(label="🛍️ Buy Option 3", style=discord.ButtonStyle.green, custom_id="buy_3")
    async def buy_option_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Purchase third cover art option"""
        await self._purchase_option(interaction, 2)


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
        self.randomized = False  # Track if current order is randomized
        
        # Set the jump button label dynamically
        for child in self.children:
            if child.custom_id == "jump_page":
                child.label = f"< {self.current_page}/{self.total_pages} >"
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
                
                # Add search-specific footer to each embed
                for embed in embeds:
                    embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • Browse only • Use .cover gallery <UID> to purchase!")
                
                # Update jump button label
                for child in self.children:
                    if child.custom_id == "jump_page":
                        child.label = f"< {self.current_page}/{self.total_pages} >"
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
                
                # Add search-specific footer to each embed
                for embed in embeds:
                    embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • Browse only • Use .cover gallery <UID> to purchase!")
                
                # Update jump button label
                for child in self.children:
                    if child.custom_id == "jump_page":
                        child.label = f"< {self.current_page}/{self.total_pages} >"
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
    
    @discord.ui.button(label="< page/max >", style=discord.ButtonStyle.secondary, custom_id="jump_page")
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
                    
                    # Add search-specific footer to each embed
                    for embed in embeds:
                        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • Browse only • Use .cover gallery <UID> to purchase!")
                    
                    # Update jump button label
                    button.label = f"< {self.current_page}/{self.total_pages} >"
                    
                    await interaction.message.edit(embeds=embeds, view=self)
                    await interaction.followup.send(f"Jumped to page {target_page}!", ephemeral=True)
                else:
                    await interaction.followup.send("No images available on that page!", ephemeral=True)
                    
            except Exception as e:
                logger.error(f"Error jumping to page: {e}")
                await interaction.followup.send("Error jumping to page!", ephemeral=True)
    
    @discord.ui.button(label="🔀 Randomize", style=discord.ButtonStyle.blurple, custom_id="randomize")
    async def randomize_order(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Randomize the order of current images"""
        import random
        
        # Disable button temporarily
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            # Randomize current images order
            random.shuffle(self.current_images)
            self.randomized = not self.randomized  # Toggle state
            
            # Update embeds with randomized images
            embeds = await self.cover_system.create_cover_art_embeds(
                self.character, self.current_images, self.current_page, self.total_pages
            )
            
            # Add search-specific footer to each embed
            for embed in embeds:
                embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • Browse only • Use .cover gallery <UID> to purchase!")
            
            # Update button label to reflect state
            button.label = "🔀 Unshuffle" if self.randomized else "🔀 Randomize"
            
            await interaction.message.edit(embeds=embeds, view=self)
            await interaction.followup.send(f"{'🔀 Images randomized!' if self.randomized else '🔀 Images restored to original order!'}", ephemeral=True)
            
        except Exception as e:
            logger.error(f"Error randomizing images: {e}")
            await interaction.followup.send("Error randomizing images!", ephemeral=True)
        finally:
            button.disabled = False
            await interaction.message.edit(view=self)
    
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
