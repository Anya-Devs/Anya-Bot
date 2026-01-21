"""
Cover Art System for Gacha Characters
Uses Node.js Image API for ultra-fast searching with fallback to direct search
"""

import discord
import aiohttp
import random
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
import asyncio
import logging
from .api_client import get_api_client
from .multisearch import MultiSourceImageSearch

logger = logging.getLogger(__name__)

class CoverArtSystem:
    """Cover art system using Node.js Image API with fallback"""
    
    def __init__(self, quest_data):
        self.quest_data = quest_data
        self.session = None
        self.api_client = get_api_client()
        self.multi_search = MultiSourceImageSearch()  # Fallback
        self.image_cache = {}  # Cache: {character_uid: {sequential_id: image_data}}
        self.character_image_map = {}  # Map: {character_uid: {sequential_id: source_image_data}}
        self.use_api = True  # Use Node.js API by default
        
    async def get_session(self):
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10),
                headers={'User-Agent': 'Anya-Bot-CoverArt/1.0'}
            )
        return self.session
    
    async def search_cover_art(self, character_name: str, series_name: str = None, page: int = 1, limit: int = 100, character_uid: str = None, owned_hashes: set = None) -> Tuple[List[Dict], int]:
        """Search for cover art using Node.js API with fallback to direct search
        
        The API handles:
        - Tag discovery (finds correct tags for each source)
        - Parallel fetching from all sources
        - Rate limiting and deduplication
        - Caching for instant repeat searches
        
        Args:
            character_name: Character name to search for
            series_name: Series/anime name for disambiguation
            page: Page number (1-indexed)
            limit: Images per page (default 100 for better pagination)
            character_uid: Character UID for caching sequential IDs
        
        Returns:
            Tuple of (images list, max_pages)
        """
        logger.info(f"[Cover Art] Searching: '{character_name}' from '{series_name}' (page {page}, limit {limit})")
        
        try:
            # Try Node.js API first - it handles EVERYTHING (tags, fetching, caching)
            if self.use_api:
                api_healthy = await self.api_client.health_check()
                if api_healthy:
                    logger.info("[Cover Art] Using Node.js Image API (handles tag discovery + fetching)")
                    images, max_pages = await self.api_client.search(
                        character_name, series_name, page, limit
                    )
                    if images:
                        logger.info(f"[Cover Art] API returned {len(images)} images, {max_pages} pages")
                    else:
                        logger.warning("[Cover Art] API returned no results, falling back to direct search")
                        images, max_pages = await self.multi_search.search_all_sources(
                            character_name, series_name, page, limit
                        )
                else:
                    logger.warning("[Cover Art] API not available, using direct search with local tag discovery")
                    images, max_pages = await self.multi_search.search_all_sources(
                        character_name, series_name, page, limit
                    )
            else:
                # Fallback to direct multi-source search with local tag discovery
                images, max_pages = await self.multi_search.search_all_sources(
                    character_name, series_name, page, limit
                )
            
            logger.info(f"[Cover Art] Result: {len(images)} images, max_pages={max_pages}")
            
            # Log API URL being used
            if self.use_api:
                api_url = os.getenv('IMAGE_API_URL', 'http://localhost:3456')
                print(f"[Cover Art] API URL: {api_url}")
                logger.info(f"[Cover Art] API URL: {api_url}")
            
            # Log image URLs for debugging
            if images:
                image_urls = [img.get('url', img.get('preview_url', 'NO_URL')) for img in images[:10]]
                logger.info(f"[Cover Art] embeds {image_urls}")
                print(f"[Cover Art] total images: {len(images)}")
            
            # Filter out owned images (deduplication)
            if owned_hashes and images:
                logger.info(f"[Cover Art] Filtering {len(owned_hashes)} owned hashes from results")
                images = [img for img in images if img.get('hash', '') not in owned_hashes]
                logger.info(f"[Cover Art] {len(images)} images remaining after deduplication")

                logger.info(f"[Cover Art] {len(images)} images remaining after deduplication")
            
            # Filter out wide images (keep only Portrait/Square-ish)
            # Threshold: Aspect Ratio (Width/Height) <= 1.2
            # This allows Portrait (AR < 1), Square (AR = 1), and slightly wide images
            initial_count = len(images)
            images = [
                img for img in images 
                if not (img.get('width') and img.get('height') and img['width'] > img['height'] * 1.2)
            ]
            if len(images) < initial_count:
                logger.info(f"[Cover Art] Filtered {initial_count - len(images)} landscape/wide images")

            # Create character-specific sequential IDs on FIRST page only
            if character_uid and images:
                # Check if we need to build the complete image map (first time or new character)
                if character_uid not in self.character_image_map or page == 1:
                    # Get ALL images for this character to assign persistent IDs
                    cache_key = f"{character_name.lower()}_{series_name.lower() if series_name else 'none'}"
                    if hasattr(self.multi_search, '_search_cache') and cache_key in self.multi_search._search_cache:
                        all_character_images = self.multi_search._search_cache[cache_key]
                        
                        # Initialize map for this character
                        self.character_image_map[character_uid] = {}
                        
                        # Assign sequential IDs to ALL images (1, 2, 3, ..., total)
                        for idx, img in enumerate(all_character_images, start=1):
                            self.character_image_map[character_uid][idx] = {
                                'source_id': img['id'],
                                'source': img['source'],
                                'url': img.get('url', ''),
                                'preview_url': img.get('preview_url', ''),
                                'file_url': img.get('file_url', ''),
                                'score': img.get('score', 0),
                                'width': img.get('width', 0),
                                'height': img.get('height', 0),
                                'width': img.get('width', 0),
                                'height': img.get('height', 0),
                                'tags': img.get('tags', []),
                                'hash': img.get('hash', '')
                            }
                        
                        logger.info(f"[Cover Art] Built complete image map with {len(all_character_images)} images for character {character_uid}")
                
                # Add sequential IDs to the current page's images based on their position
                start_idx = (page - 1) * limit
                for idx, img in enumerate(images, start=start_idx + 1):
                    img['sequential_id'] = idx
                
                logger.info(f"[Cover Art] Page {page}: Assigned sequential IDs {start_idx + 1}-{start_idx + len(images)} for character {character_uid}")
            
            logger.info(f"[Cover Art] Found {len(images)} images on page {page}/{max_pages}")
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

            for i, img in enumerate(images[:10], start=1):
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

                # No footer needed - users can use the buy buttons (1, 2, 3)
                embeds.append(embed)


            return embeds

        except Exception as e:
            logger.error(f"Error creating cover art embeds: {e}")
            return []

    def _generate_unique_id(self) -> str:
        """Generate a random 16-digit hexadecimal ID"""
        import secrets
        return secrets.token_hex(8).upper()

    async def purchase_cover_art(self, user_id: str, guild_id: str, character_uid: str, image_id: int, custom_name: str = None) -> Tuple[bool, str]:
        """Purchase cover art for a character and store in database"""
        
        # Check if user owns the character
        char = await self._get_character(user_id, guild_id, character_uid)
        if not char:
            return False, "You don't own this character!"
        
        # Get the image URL for this image_id from cache
        image_url = await self._get_image_url_by_id(image_id, character_uid)
        
        # Check if user already owns this image (duplicate prevention)
        owned_arts = await self._get_user_cover_arts_for_character(user_id, guild_id, character_uid)
        for owned_art in owned_arts:
            # Check by image_id
            if owned_art.get('image_id') == image_id:
                return False, "❌ You already own this cover art!"
            # Check by URL
            if image_url and owned_art.get('image_url') == image_url:
                return False, "❌ You already own this cover art!"
        
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
        unique_id = await self._unlock_cover_art(user_id, guild_id, character_uid, image_id, custom_name)
        
        return True, f"Successfully purchased cover art `{unique_id}` ('{custom_name}') for **{cost}** stella points!"
    
    async def _get_user_cover_arts_for_character(self, user_id: str, guild_id: str, character_uid: str) -> List[Dict]:
        """Get all cover arts owned by a user for a specific character"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            char_uid_lower = character_uid.lower()
            
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.characters.{char_uid_lower}": 1}
            )
            
            if result:
                char_data = result.get("members", {}).get(user_id, {}).get("characters", {}).get(char_uid_lower, {})
                
                cover_arts = []
                
                # Get from cover_collection (new format)
                if 'cover_collection' in char_data and isinstance(char_data['cover_collection'], list):
                    cover_arts.extend(char_data['cover_collection'])
                
                # Get from cover_art (legacy format)
                if char_data.get('cover_art'):
                    cover_arts.append(char_data['cover_art'])
                
                return cover_arts
        except Exception as e:
            logger.error(f"Error getting cover arts for character: {e}")
        
        return []
    
    async def _unlock_cover_art(self, user_id: str, guild_id: str, character_uid: str, image_id: int, custom_name: str) -> str:
        """Unlock cover art for a character and store in database"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # Search for the image URL from the multi-source search (check cache first)
            image_url = await self._get_image_url_by_id(image_id, character_uid)
            
            # Get the cost for this rarity (for refund calculation later)
            from ..const import GACHA_RARITY_TIERS
            char = await self._get_character(user_id, guild_id, character_uid)
            rarity = char.get('rarity', 'common') if char else 'common'
            costs = {'common': 100, 'uncommon': 200, 'rare': 500, 'epic': 1000, 'legendary': 2000}
            cost = costs.get(rarity, 100)
            
            # Generate unique 16-digit hex ID
            unique_id = self._generate_unique_id()
            
            # Get hash, width, height from cache if available
            image_hash = ""
            image_width = 0
            image_height = 0
            if character_uid and character_uid in self.character_image_map:
                if image_id in self.character_image_map[character_uid]:
                    cached = self.character_image_map[character_uid][image_id]
                    image_hash = cached.get('hash', '')
                    image_width = cached.get('width', 0)
                    image_height = cached.get('height', 0)
            
            # Create cover art data structure
            cover_art_data = {
                'id': unique_id,
                'image_id': image_id,
                'custom_name': custom_name,
                'image_url': image_url,
                'image_hash': image_hash,
                'width': image_width,
                'height': image_height,
                'cost': cost,
                'unlocked_at': datetime.now(timezone.utc).isoformat(),
            }
            
            # Push to cover_collection array and set cover_unlocked to true
            await server_col.update_one(
                {"guild_id": guild_id},
                {
                    "$set": {
                        f"members.{user_id}.characters.{character_uid.lower()}.cover_unlocked": True
                    },
                    "$push": {
                        f"members.{user_id}.characters.{character_uid.lower()}.cover_collection": cover_art_data
                    }
                }
            )
            logger.info(f"[Cover Art] Unlocked cover art '{custom_name}' (ID: {unique_id}) for character {character_uid}")
            return unique_id
        except Exception as e:
            logger.error(f"Error unlocking cover art: {e}", exc_info=True)
            return "UNKNOWN_ID"
    
    async def set_selected_cover_art(self, user_id: str, guild_id: str, character_uid: str, cover_art_id: str) -> Tuple[bool, str]:
        """Set a specific cover art (by Unique Hex ID) as the selected image for a character"""
        
        # Check if user owns the character
        char = await self._get_character(user_id, guild_id, character_uid)
        if not char:
            logger.warning(f"[Cover Art Set] User {user_id} doesn't own character {character_uid}")
            return False, "You don't own this character!"
        
        # Get user's cover art collection
        cover_arts = await self._get_user_cover_arts(user_id, guild_id)
        
        # Find the specific cover art by ID
        target_art = None
        for art in cover_arts:
            # Check for ID match or custom_name match (for legacy)
            if str(art.get('id', '')) == str(cover_art_id) or str(art.get('custom_name', '')) == str(cover_art_id):
                target_art = art
                break
        
        if not target_art:
            logger.warning(f"[Cover Art Set] Cover art ID '{cover_art_id}' not found for character {character_uid}")
            return False, "Cover art not found!"
        
        # Update the selected cover art
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            image_url = target_art.get('image_url', '')
            logger.info(f"[Cover Art Set] Setting cover art {cover_art_id} for character {character_uid}")
            
            # Base update for gacha_inventory (always needed for display)
            update_data = {
                f"members.{user_id}.gacha_inventory.$[elem].active_cover_url": image_url,
                f"members.{user_id}.gacha_inventory.$[elem].active_cover_id": target_art.get('image_id'),
                f"members.{user_id}.gacha_inventory.$[elem].active_cover_unique_id": cover_art_id
            }
            
            filters = [{"elem.uid": character_uid.upper()}]
            
            # Handle Legacy vs Collection updates
            if target_art.get('_is_legacy'):
                # Legacy: Update the single cover_art object
                update_data[f"members.{user_id}.characters.{character_uid.lower()}.cover_art.selected"] = True
                update_data[f"members.{user_id}.characters.{character_uid.lower()}.cover_art.selected_at"] = datetime.now(timezone.utc).isoformat()
                # Persist the ID to upgrade the legacy item!
                update_data[f"members.{user_id}.characters.{character_uid.lower()}.cover_art.id"] = cover_art_id
            else:
                # New: Update the specific item in cover_collection list
                update_data[f"members.{user_id}.characters.{character_uid.lower()}.cover_collection.$[cover].selected"] = True
                update_data[f"members.{user_id}.characters.{character_uid.lower()}.cover_collection.$[cover].selected_at"] = datetime.now(timezone.utc).isoformat()
                # Add filter to find this specific cover art in the array
                filters.append({"cover.id": cover_art_id})
            
            # Perform update
            await server_col.update_one(
                {"guild_id": guild_id},
                {"$set": update_data},
                array_filters=filters
            )
            
            return True, "Successfully set as the active cover art!"
            
        except Exception as e:
            logger.error(f"Error setting selected cover art: {e}", exc_info=True)
            return False, "Error setting selected cover art!"
    
    async def _get_user_cover_arts(self, user_id: str, guild_id: str) -> List[Dict]:
        """Get all cover arts owned by a user for a specific character (migrating old data if needed)"""
        # This method is designed to return ALL cover arts for ALL characters, but usually we iterate over characters
        # But wait, looking at the previous implementation, it iterates over all characters.
        # However, for set_selected_cover_art we usually care about a specific character. 
        # But let's keep the signature similar or adapt it.
        # Actually set_selected_cover_art calls this to find the art.
        
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.characters": 1}
            )
            
            cover_arts = []
            
            if result:
                characters = result.get("members", {}).get(user_id, {}).get("characters", {})
                
                for char_uid, char_data in characters.items():
                    # Handle new list format
                    if 'cover_collection' in char_data and isinstance(char_data['cover_collection'], list):
                        for art in char_data['cover_collection']:
                            art_copy = art.copy()
                            art_copy['character_uid'] = char_uid
                            art_copy['character_name'] = char_data.get('name', 'Unknown')
                            cover_arts.append(art_copy)
                    
                    # Handle old single object format (migration or compatibility)
                    if char_data.get('cover_unlocked') and char_data.get('cover_art'):
                        # Check if this art is already in the collection list (deduplication)
                        is_duplicate = False
                        if 'cover_collection' in char_data:
                            legacy_name = char_data['cover_art'].get('custom_name')
                            for col_art in char_data['cover_collection']:
                                if col_art.get('custom_name') == legacy_name:
                                    is_duplicate = True
                                    break
                        
                        if not is_duplicate:
                            art = char_data['cover_art'].copy()
                        art['character_uid'] = char_uid
                        art['character_name'] = char_data.get('name', 'Unknown')
                        art['_is_legacy'] = True # Mark as legacy for lazy migration
                        # Assign stable pseudo-ID if missing (hash of custom_name)
                        if 'id' not in art:
                            import hashlib
                            cname = art.get('custom_name', 'LEGACY')
                            # Create stable 16 char hex from name
                            art['id'] = hashlib.md5(cname.encode()).hexdigest()[:16].upper()
                        cover_arts.append(art)
                
                return cover_arts


            
        except Exception as e:
            logger.error(f"Error getting user cover arts: {e}")
        
        return []
    
    async def set_active_cover_art(self, user_id: str, guild_id: str, character_uid: str, image_id: int) -> bool:
        """Deprecated: Use set_selected_cover_art with unique ID. This is kept for compatibility but needs update to find the latest purchased art."""
        # Find the most recently purchased art with this image_id and set it
        try:
            cover_arts = await self._get_user_cover_arts(user_id, guild_id)
            # Filter for this character and image_id
            matching_arts = [
                a for a in cover_arts 
                if a.get('character_uid') == character_uid.lower() and a.get('image_id') == image_id
            ]
            
            # Sort by unlocked_at desc (newest first)
            # matching_arts.sort(key=lambda x: x.get('unlocked_at', ''), reverse=True)
            
            if matching_arts:
                # Use the newest one
                await self.set_selected_cover_art(user_id, guild_id, character_uid, matching_arts[-1]['id'])
                return True
            return False
        except Exception as e:
             logger.error(f"Error in legacy set_active_cover_art: {e}")
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
                        active_url = char.get('active_cover_url')
                        if active_url:
                            logger.info(f"[Cover Art] Found active cover URL for character {character_uid}: {active_url[:50]}...")
                        else:
                            logger.debug(f"[Cover Art] No active cover URL set for character {character_uid}")
                        return active_url
            
            logger.debug(f"[Cover Art] Character {character_uid} not found in inventory for user {user_id}")
        except Exception as e:
            logger.error(f"Error getting active cover art URL: {e}", exc_info=True)
        
        return None
    
    async def delete_cover_art(self, user_id: str, guild_id: str, cover_id: str) -> bool:
        """Delete a cover art and return success status"""
        try:
            db = self.quest_data.mongoConnect[self.quest_data.DB_NAME]
            server_col = db["Servers"]
            
            # Find which character this cover art belongs to
            result = await server_col.find_one(
                {"guild_id": guild_id},
                {f"members.{user_id}.characters": 1}
            )
            
            if result:
                characters = result.get("members", {}).get(user_id, {}).get("characters", {})
                
                for char_uid, char_data in characters.items():
                    if char_data.get('cover_art', {}).get('custom_name') == cover_id:
                        # Delete the cover art
                        await server_col.update_one(
                            {"guild_id": guild_id},
                            {
                                "$unset": {
                                    f"members.{user_id}.characters.{char_uid}.cover_art": "",
                                    f"members.{user_id}.characters.{char_uid}.cover_unlocked": ""
                                }
                            }
                        )
                        return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error deleting cover art: {e}")
            return False
    
    async def _get_image_url_by_id(self, image_id: int, character_uid: str = None) -> str:
        """Get image URL using character-specific sequential ID"""
        try:
            # Check character-specific image map first
            if character_uid and character_uid in self.character_image_map:
                if image_id in self.character_image_map[character_uid]:
                    img_data = self.character_image_map[character_uid][image_id]
                    # Get the actual URL from the mapped image
                    image_url = img_data.get('url') or img_data.get('file_url') or img_data.get('preview_url', '')
                    source = img_data.get('source', 'Unknown')
                    source_id = img_data.get('source_id', 'N/A')
                    logger.info(f"[Cover Art] Found sequential ID {image_id} for character {character_uid}")
                    logger.info(f"[Cover Art] Source: {source} (ID: {source_id})")
                    logger.info(f"[Cover Art] Using URL: {image_url[:80]}...")
                    return image_url
            
            # Not found in character map
            logger.error(f"[Cover Art] Sequential ID {image_id} not found for character {character_uid}")
            logger.error(f"[Cover Art] User must view gallery first with .cover gallery {character_uid}")
            return ''
        except Exception as e:
            logger.error(f"Error getting image URL by sequential ID: {e}", exc_info=True)
            return ''
    
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
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page - 1, 3)
            
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
            new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, self.current_page + 1, 3)
            
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
                new_images, _ = await self.cover_system.search_cover_art(char_name, series_name, target_page, 3)
                
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
