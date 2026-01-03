"""
Multi-Source Image Search System
Searches Google Safe Search, DuckDuckGo, Bing, Danbooru, and Safebooru
with deduplication and safe content filtering
"""

import aiohttp
import asyncio
import hashlib
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urljoin
import logging

logger = logging.getLogger(__name__)

# Character name to booru tag mappings
# Format: "common name": "booru_tag" or "booru_tag_(series)"
CHARACTER_TAG_MAPPINGS = {
    # Spy x Family
    "yor forger": "yor_briar",
    "yor briar": "yor_briar",
    "anya forger": "anya_(spy_x_family)",
    "loid forger": "loid_forger",
    "twilight": "loid_forger",
    
    # Re:Zero
    "emilia": "emilia_(re:zero)",
    "rem": "rem_(re:zero)",
    "ram": "ram_(re:zero)",
    "beatrice": "beatrice_(re:zero)",
    "echidna": "echidna_(re:zero)",
    
    # Konosuba
    "megumin": "megumin",
    "aqua": "aqua_(konosuba)",
    "darkness": "darkness_(konosuba)",
    "kazuma": "satou_kazuma",
    
    # Demon Slayer
    "nezuko": "kamado_nezuko",
    "nezuko kamado": "kamado_nezuko",
    "tanjiro": "kamado_tanjirou",
    "zenitsu": "agatsuma_zenitsu",
    "inosuke": "hashibira_inosuke",
    "shinobu": "kochou_shinobu",
    "mitsuri": "kanroji_mitsuri",
    
    # Jujutsu Kaisen
    "gojo": "gojou_satoru",
    "gojo satoru": "gojou_satoru",
    "itadori": "itadori_yuuji",
    "megumi": "fushiguro_megumi",
    "nobara": "kugisaki_nobara",
    
    # Tokyo Ghoul
    "ken kaneki": "kaneki_ken",
    "kaneki": "kaneki_ken",
    "touka": "kirishima_touka",
    "touka kirishima": "kirishima_touka",
    
    # Classroom of the Elite
    "kiyotaka ayanokouji": "ayanokouji_kiyotaka",
    "ayanokouji": "ayanokouji_kiyotaka",
    "kiyotaka": "ayanokouji_kiyotaka",
    "horikita": "horikita_suzune",
    
    # My Hero Academia
    "deku": "midoriya_izuku",
    "izuku": "midoriya_izuku",
    "bakugo": "bakugou_katsuki",
    "todoroki": "todoroki_shouto",
    "uraraka": "uraraka_ochako",
    
    # Attack on Titan
    "eren": "eren_yeager",
    "mikasa": "mikasa_ackerman",
    "levi": "levi_(shingeki_no_kyojin)",
    "armin": "armin_arlert",
    
    # Chainsaw Man
    "power": "power_(chainsaw_man)",
    "makima": "makima_(chainsaw_man)",
    "denji": "denji_(chainsaw_man)",
    "aki": "aki_hayakawa",
    
    # Darling in the FranXX
    "zero two": "zero_two_(darling_in_the_franxx)",
    "02": "zero_two_(darling_in_the_franxx)",
    "ichigo": "ichigo_(darling_in_the_franxx)",
    
    # Genshin Impact
    "hu tao": "hu_tao_(genshin_impact)",
    "raiden": "raiden_shogun",
    "ayaka": "kamisato_ayaka",
    "ganyu": "ganyu_(genshin_impact)",
    "keqing": "keqing_(genshin_impact)",
    "mona": "mona_(genshin_impact)",
    "fischl": "fischl_(genshin_impact)",
    
    # Fate Series
    "saber": "saber_(fate)",
    "artoria": "artoria_pendragon_(fate)",
    "rin": "tohsaka_rin",
    "sakura": "matou_sakura",
    "jeanne": "jeanne_d'arc_(fate)",
    
    # Hololive
    "gawr gura": "gawr_gura",
    "gura": "gawr_gura",
    "mori calliope": "mori_calliope",
    "amelia watson": "watson_amelia",
    "pekora": "usada_pekora",
    "marine": "houshou_marine",
    
    # Bocchi the Rock
    "bocchi": "gotou_hitori",
    "hitori": "gotou_hitori",
    "nijika": "ijichi_nijika",
    "ryo": "yamada_ryo_(bocchi_the_rock!)",
    "kita": "kita_ikuyo",
    
    # Oshi no Ko
    "ai": "ai_(oshi_no_ko)",
    "ruby": "ruby_(oshi_no_ko)",
    "kana": "arima_kana",
    "akane": "kurokawa_akane",
    
    # Frieren
    "frieren": "frieren",
    "fern": "fern_(sousou_no_frieren)",
    
    # Blue Lock
    "isagi": "isagi_yoichi",
    "bachira": "bachira_meguru",
    
    # Violet Evergarden
    "violet": "violet_evergarden",
    "violet evergarden": "violet_evergarden",
}

# Series name to booru tag mappings
SERIES_TAG_MAPPINGS = {
    "spy x family": "spy_x_family",
    "spyxfamily": "spy_x_family",
    "re:zero": "re:zero_kara_hajimeru_isekai_seikatsu",
    "re zero": "re:zero_kara_hajimeru_isekai_seikatsu",
    "konosuba": "kono_subarashii_sekai_ni_shukufuku_wo!",
    "kono subarashii sekai ni shukufuku wo": "kono_subarashii_sekai_ni_shukufuku_wo!",
    "demon slayer": "kimetsu_no_yaiba",
    "kimetsu no yaiba": "kimetsu_no_yaiba",
    "jujutsu kaisen": "jujutsu_kaisen",
    "my hero academia": "boku_no_hero_academia",
    "mha": "boku_no_hero_academia",
    "bnha": "boku_no_hero_academia",
    "attack on titan": "shingeki_no_kyojin",
    "aot": "shingeki_no_kyojin",
    "chainsaw man": "chainsaw_man",
    "darling in the franxx": "darling_in_the_franxx",
    "ditf": "darling_in_the_franxx",
    "genshin impact": "genshin_impact",
    "genshin": "genshin_impact",
    "fate": "fate_(series)",
    "fate stay night": "fate/stay_night",
    "fate grand order": "fate/grand_order",
    "fgo": "fate/grand_order",
    "hololive": "hololive",
    "bocchi the rock": "bocchi_the_rock!",
    "bocchi": "bocchi_the_rock!",
    "oshi no ko": "oshi_no_ko",
    "frieren": "sousou_no_frieren",
    "blue lock": "blue_lock",
    "violet evergarden": "violet_evergarden",
    "one piece": "one_piece",
    "naruto": "naruto",
    "dragon ball": "dragon_ball",
    "pokemon": "pokemon",
}


class MultiSourceImageSearch:
    """Search multiple sources for anime character images with deduplication"""
    
    def __init__(self):
        self.session = None
        self.seen_urls = set()
        self.seen_hashes = set()
        
    async def get_session(self):
        """Get or create aiohttp session with proper headers"""
        if self.session is None or self.session.closed:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/html, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://safebooru.donmai.us/',
            }
            self.session = aiohttp.ClientSession(headers=headers)
        return self.session
    
    def _get_url_hash(self, url: str) -> str:
        """Generate hash for URL deduplication"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def _is_duplicate(self, url: str) -> bool:
        """Check if image URL is duplicate"""
        url_hash = self._get_url_hash(url)
        if url_hash in self.seen_hashes or url in self.seen_urls:
            return True
        self.seen_hashes.add(url_hash)
        self.seen_urls.add(url)
        return False
    
    def _get_booru_character_tag(self, character_name: str, series_name: str = None) -> str:
        """Convert character name to proper booru tag format"""
        name_lower = character_name.lower().strip()
        
        # Check direct mapping first
        if name_lower in CHARACTER_TAG_MAPPINGS:
            return CHARACTER_TAG_MAPPINGS[name_lower]
        
        # Try without common suffixes
        for suffix in [' san', ' chan', ' kun', ' sama']:
            if name_lower.endswith(suffix):
                base_name = name_lower[:-len(suffix)]
                if base_name in CHARACTER_TAG_MAPPINGS:
                    return CHARACTER_TAG_MAPPINGS[base_name]
        
        # Format as booru tag: spaces to underscores, lowercase
        formatted = re.sub(r'[^a-zA-Z0-9\s]', '', name_lower)
        formatted = re.sub(r'\s+', '_', formatted.strip())
        
        # If series provided, try to add series suffix
        if series_name:
            series_tag = self._get_booru_series_tag(series_name)
            if series_tag:
                return f"{formatted}_({series_tag})"
        
        return formatted
    
    def _get_name_variations(self, character_name: str, series_name: str = None) -> List[str]:
        """Generate multiple name variations to try (first_last, last_first, etc.)"""
        variations = []
        
        # Get base tag
        base_tag = self._get_booru_character_tag(character_name, series_name)
        variations.append(base_tag)
        
        # If not in mappings, try name variations
        name_lower = character_name.lower().strip()
        if name_lower not in CHARACTER_TAG_MAPPINGS:
            # Clean the name
            cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', name_lower)
            parts = cleaned.split()
            
            if len(parts) == 2:
                # Try both first_last and last_first
                first, last = parts
                variations.append(f"{first}_{last}")
                variations.append(f"{last}_{first}")
                
                # Try with series suffix if provided
                if series_name:
                    series_tag = self._get_booru_series_tag(series_name)
                    if series_tag:
                        variations.append(f"{first}_{last}_({series_tag})")
                        variations.append(f"{last}_{first}_({series_tag})")
            elif len(parts) == 3:
                # Try different combinations for 3-part names
                first, middle, last = parts
                variations.append(f"{first}_{middle}_{last}")
                variations.append(f"{last}_{first}_{middle}")
                variations.append(f"{first}_{last}")
                variations.append(f"{last}_{first}")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)
        
        return unique_variations
    
    def _get_booru_series_tag(self, series_name: str) -> str:
        """Convert series name to proper booru tag format"""
        if not series_name:
            return ""
        
        name_lower = series_name.lower().strip()
        
        # Check direct mapping
        if name_lower in SERIES_TAG_MAPPINGS:
            return SERIES_TAG_MAPPINGS[name_lower]
        
        # Clean and format
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', name_lower)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        return cleaned
    
    async def search_all_sources(
        self, 
        character_name: str, 
        series_name: str = None, 
        page: int = 1, 
        limit: int = 30
    ) -> Tuple[List[Dict], int]:
        """Search multiple SFW sources with deep scraping and proper pagination"""
        self.seen_urls.clear()
        self.seen_hashes.clear()
        
        all_images = []
        
        # Get all name variations to try
        name_variations = self._get_name_variations(character_name, series_name)
        logger.info(f"[MultiSearch] Character '{character_name}' -> variations: {name_variations}")
        
        # Deep scraping: fetch multiple pages from each source
        pages_per_source = 3  # Fetch 3 pages from each source
        
        # Try each variation until we get results
        for char_tag in name_variations:
            if all_images:
                break  # Stop if we already found images
            
            # Search multiple pages from BOTH sources in parallel
            tasks = []
            for source_page in range(1, pages_per_source + 1):
                tasks.append(self._search_safebooru_org(char_tag, source_page, 100))
                tasks.append(self._search_konachan(char_tag, source_page, 100))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Combine and deduplicate results
            for result in results:
                if isinstance(result, list):
                    for img in result:
                        if img.get('url') and not self._is_duplicate(img['url']):
                            all_images.append(img)
            
            if all_images:
                logger.info(f"[MultiSearch] Found {len(all_images)} images with tag '{char_tag}'")
        
        # Sort by score/relevance
        all_images.sort(key=lambda x: x.get('score', 0), reverse=True)
        
        # Calculate pagination
        total_images = len(all_images)
        max_pages = max(1, (total_images + limit - 1) // limit)
        
        # Get the correct page slice
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        page_images = all_images[start_idx:end_idx]
        
        logger.info(f"[MultiSearch] Total: {total_images} unique images | Page {page}/{max_pages} | Showing {len(page_images)} images")
        return page_images, max_pages
    
    async def _search_danbooru_safe(self, char_tag: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Search safebooru.donmai.us (Danbooru's safe version) - no API key needed"""
        session = await self.get_session()
        
        # Use rating:safe instead of rating:general for safebooru
        search_query = f"{char_tag} rating:safe"
        
        params = {
            'tags': search_query,
            'limit': min(limit, 100),
            'page': page
        }
        
        try:
            # Safebooru.donmai.us doesn't require API key
            url = 'https://safebooru.donmai.us/posts.json'
            
            # Create a new session with updated headers specifically for this request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://safebooru.donmai.us/',
                'Origin': 'https://safebooru.donmai.us',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Sec-Fetch-Dest': 'empty',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'same-origin',
            }
            
            async with session.get(url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    logger.info(f"[Danbooru Safe] Page {page}: Found {len(data)} results for '{char_tag}'")
                    return self._process_danbooru_results(data)
                elif resp.status == 403:
                    logger.warning(f"[Danbooru Safe] 403 Forbidden - trying HTML scraping")
                    return await self._scrape_danbooru_html(char_tag, page)
                elif resp.status == 429:
                    logger.warning(f"[Danbooru Safe] Rate limited - waiting and retrying")
                    await asyncio.sleep(2)
                    return []
                else:
                    logger.warning(f"[Danbooru Safe] Status {resp.status} for '{char_tag}' page {page}")
        except asyncio.TimeoutError:
            logger.warning(f"[Danbooru Safe] Timeout for '{char_tag}' page {page}")
        except Exception as e:
            logger.error(f"[Danbooru Safe] Error: {e}")
        
        return []
    
    async def _scrape_danbooru_html(self, char_tag: str, page: int = 1) -> List[Dict]:
        """Scrape Danbooru HTML as fallback for 403 errors"""
        session = await self.get_session()
        
        try:
            # Use the web interface instead of API with proper URL encoding
            from urllib.parse import quote
            encoded_tag = quote(f"{char_tag} rating:general")
            url = f'https://safebooru.donmai.us/posts?tags={encoded_tag}&page={page}'
            
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Try multiple patterns to extract image data
                    results = []
                    
                    # Pattern 1: data-file-url in article tags
                    pattern1 = r'<article[^>]*data-id="(\d+)"[^>]*data-file-url="([^"]+)"'
                    matches1 = re.findall(pattern1, html)
                    
                    # Pattern 2: Look for preview URLs
                    pattern2 = r'data-id="(\d+)"[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>\s*<img[^>]*src="([^"]+)"'
                    matches2 = re.findall(pattern2, html)
                    
                    # Process pattern 1 matches
                    for post_id, file_url in matches1:
                        if file_url.startswith('//'):
                            file_url = 'https:' + file_url
                        elif not file_url.startswith('http'):
                            file_url = 'https://safebooru.donmai.us' + file_url
                        
                        results.append({
                            'id': int(post_id),
                            'url': file_url,
                            'preview_url': file_url,
                            'source': 'Danbooru Safe',
                            'tags': [char_tag],
                            'score': 0,
                            'width': 1000,
                            'height': 1000,
                        })
                    
                    # Process pattern 2 matches if pattern 1 didn't work
                    if not results:
                        for post_id, post_url, preview_url in matches2:
                            if preview_url.startswith('//'):
                                preview_url = 'https:' + preview_url
                            elif not preview_url.startswith('http'):
                                preview_url = 'https://safebooru.donmai.us' + preview_url
                            
                            results.append({
                                'id': int(post_id),
                                'url': preview_url,
                                'preview_url': preview_url,
                                'source': 'Danbooru Safe',
                                'tags': [char_tag],
                                'score': 0,
                                'width': 1000,
                                'height': 1000,
                            })
                    
                    if results:
                        logger.info(f"[Danbooru HTML] Page {page}: Scraped {len(results)} images")
                    else:
                        logger.warning(f"[Danbooru HTML] Page {page}: No images found in HTML")
                    
                    return results[:30]  # Limit to 30 images per page
                else:
                    logger.warning(f"[Danbooru HTML] Status {resp.status} for page {page}")
        except Exception as e:
            logger.error(f"[Danbooru HTML] Scraping error: {e}")
        
        return []
    
    async def _search_safebooru_org(self, char_tag: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Search Safebooru.org - PRIMARY IMAGE SOURCE"""
        session = await self.get_session()
        
        # Safebooru.org uses slightly different tag format
        # Remove parentheses format and use space-separated tags
        search_tag = char_tag
        
        params = {
            'page': 'dapi',
            's': 'post',
            'q': 'index',
            'json': '1',
            'tags': search_tag,
            'limit': min(limit, 100),
            'pid': page - 1  # Safebooru uses 0-indexed pages
        }
        
        try:
            async with session.get('https://safebooru.org/index.php', params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    if text.strip():
                        import json
                        try:
                            data = json.loads(text)
                            result_count = len(data) if isinstance(data, list) else 0
                            if result_count > 0:
                                logger.info(f"[Safebooru.org] Page {page}: Found {result_count} results for '{char_tag}'")
                            return self._process_safebooru_results(data)
                        except json.JSONDecodeError as e:
                            logger.warning(f"[Safebooru.org] Invalid JSON response: {e}")
                else:
                    logger.warning(f"[Safebooru.org] Status {resp.status} for '{char_tag}' page {page}")
        except asyncio.TimeoutError:
            logger.warning(f"[Safebooru.org] Timeout for '{char_tag}' page {page}")
        except Exception as e:
            logger.error(f"[Safebooru.org] Error: {e}")
        
        return []
    
    async def _search_konachan(self, char_tag: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Search Konachan.net - STRICTLY SFW anime image board"""
        session = await self.get_session()
        
        params = {
            'tags': char_tag,
            'limit': min(limit, 100),
            'page': page
        }
        
        try:
            async with session.get('https://konachan.net/post.json', params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result_count = len(data) if isinstance(data, list) else 0
                    if result_count > 0:
                        logger.info(f"[Konachan.net] Page {page}: Found {result_count} results for '{char_tag}'")
                    return self._process_konachan_results(data)
                else:
                    logger.warning(f"[Konachan.net] Status {resp.status} for '{char_tag}' page {page}")
        except asyncio.TimeoutError:
            logger.warning(f"[Konachan.net] Timeout for '{char_tag}' page {page}")
        except Exception as e:
            logger.error(f"[Konachan.net] Error: {e}")
        
        return []
    
    async def _search_duckduckgo(self, query: str, page: int = 1, limit: int = 10) -> List[Dict]:
        """Search DuckDuckGo Images"""
        session = await self.get_session()
        
        try:
            # DuckDuckGo image search endpoint
            search_query = f"{query} anime safe"
            params = {
                'q': search_query,
                'iax': 'images',
                'ia': 'images'
            }
            
            # Note: DDG requires more complex scraping, placeholder for now
            # TODO: Implement DDG image search properly
            return []
        except Exception as e:
            logger.debug(f"DuckDuckGo search error: {e}")
        
        return []
    
    async def _search_bing(self, query: str, page: int = 1, limit: int = 10) -> List[Dict]:
        """Search Bing Images with Safe Search"""
        session = await self.get_session()
        
        try:
            # Bing Image Search API or scraping
            # TODO: Implement Bing image search
            return []
        except Exception as e:
            logger.debug(f"Bing search error: {e}")
        
        return []
    
    def _clean_series_name(self, series_name: str) -> str:
        """Clean and format series name for search"""
        import re
        
        series_mappings = {
            'Re:Zero kara Hajimeru Isekai Seikatsu': 're:zero',
            'Kono Subarashii Sekai ni Shukufuku wo!': 'kono_subarashii_sekai_ni_shukufuku_wo',
            'Spy x Family': 'spy_x_family',
            'Boku no Hero Academia': 'boku_no_hero_academia',
            'Shingeki no Kyojin': 'shingeki_no_kyojin',
            'Kimetsu no Yaiba': 'kimetsu_no_yaiba',
            'Jujutsu Kaisen': 'jujutsu_kaisen',
            'Chainsaw Man': 'chainsaw_man',
            'Tokyo Ghoul': 'tokyo_ghoul',
        }
        
        # Check for exact matches
        for full_name, short_name in series_mappings.items():
            if full_name.lower() in series_name.lower():
                return short_name
        
        # Clean and format
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', series_name)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        return cleaned.lower()
    
    def _process_danbooru_results(self, data: List[Dict]) -> List[Dict]:
        """Process Danbooru results"""
        processed = []
        
        for post in data:
            if not post.get('file_url') or post.get('rating') != 's':
                continue
            
            preview_url = post.get('large_file_url') or post.get('preview_file_url') or post.get('file_url')
            
            processed.append({
                'id': post.get('id'),
                'url': post.get('file_url'),
                'preview_url': preview_url,
                'source': 'Danbooru',
                'tags': post.get('tag_string', '').split()[:10],
                'score': post.get('score', 0),
                'width': post.get('image_width', 0),
                'height': post.get('image_height', 0),
            })
        
        return processed
    
    def _process_safebooru_results(self, data) -> List[Dict]:
        """Process Safebooru results"""
        processed = []
        
        if not isinstance(data, list):
            return processed
        
        for post in data:
            try:
                # Safebooru.org uses different field names
                directory = post.get('directory', '')
                image_name = post.get('image', '')
                
                # Build URLs
                if post.get('file_url'):
                    image_url = post['file_url']
                elif directory and image_name:
                    image_url = f"https://safebooru.org/images/{directory}/{image_name}"
                else:
                    continue
                
                if post.get('sample_url'):
                    preview_url = post['sample_url']
                elif post.get('preview_url'):
                    preview_url = post['preview_url']
                elif directory and image_name:
                    preview_url = f"https://safebooru.org/samples/{directory}/sample_{image_name}"
                else:
                    preview_url = image_url
                
                # Safe conversion of numeric fields
                score = 0
                width = 0
                height = 0
                
                if post.get('score') is not None:
                    try:
                        score = int(post['score'])
                    except (ValueError, TypeError):
                        score = 0
                
                if post.get('width') is not None:
                    try:
                        width = int(post['width'])
                    except (ValueError, TypeError):
                        width = 0
                
                if post.get('height') is not None:
                    try:
                        height = int(post['height'])
                    except (ValueError, TypeError):
                        height = 0
                
                # Safebooru.org is all safe content
                processed.append({
                    'id': post.get('id', 0),
                    'url': image_url,
                    'preview_url': preview_url,
                    'source': 'Safebooru',
                    'tags': (post.get('tags', '') or '').split()[:10],
                    'score': score,
                    'width': width,
                    'height': height,
                })
            except Exception as e:
                logger.debug(f"Error processing safebooru post: {e}")
                continue
        
        return processed
    
    def _process_konachan_results(self, data: List[Dict]) -> List[Dict]:
        """Process Konachan.net results - STRICTLY SFW"""
        processed = []
        
        if not isinstance(data, list):
            return processed
        
        for post in data:
            try:
                # Konachan uses similar structure to other boorus
                file_url = post.get('file_url') or post.get('jpeg_url')
                if not file_url:
                    continue
                
                # Get preview/sample URLs
                preview_url = post.get('sample_url') or post.get('preview_url') or file_url
                
                # Safe conversion of numeric fields
                score = 0
                width = 0
                height = 0
                
                if post.get('score') is not None:
                    try:
                        score = int(post['score'])
                    except (ValueError, TypeError):
                        score = 0
                
                if post.get('width') is not None:
                    try:
                        width = int(post['width'])
                    except (ValueError, TypeError):
                        width = 0
                
                if post.get('height') is not None:
                    try:
                        height = int(post['height'])
                    except (ValueError, TypeError):
                        height = 0
                
                # Extract tags
                tags = []
                if post.get('tags'):
                    if isinstance(post['tags'], str):
                        tags = post['tags'].split()[:10]
                    elif isinstance(post['tags'], list):
                        tags = post['tags'][:10]
                
                processed.append({
                    'id': post.get('id', 0),
                    'url': file_url,
                    'preview_url': preview_url,
                    'source': 'Konachan',
                    'tags': tags,
                    'score': score,
                    'width': width,
                    'height': height,
                })
            except Exception as e:
                logger.debug(f"Error processing Konachan post: {e}")
                continue
        
        return processed
    
    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
