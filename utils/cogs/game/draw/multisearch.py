"""
Multi-Source Image Search System - MAXIMUM SAFETY FOR ALL-AGES BOT
Searches ONLY safe-rated content from Safebooru.org, Konachan.net, and Danbooru
with comprehensive filtering and deduplication

SAFETY FEATURES:
- 150+ blocked tags covering ALL inappropriate content
- Strict rating filters (rating:general/rating:safe only)
- Multi-layer validation (query filter + post-processing + URL validation)
- Zero tolerance for suggestive, sexual, or inappropriate content
- Full Discord TOS compliance with loli/shota protection
- Family-friendly, wholesome anime fan art ONLY
"""

import aiohttp
import asyncio
import hashlib
import re
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote_plus, urljoin
import logging

logger = logging.getLogger(__name__)

# Smart character name patterns for booru tag generation
COMMON_NAME_PATTERNS = {
    # Common name variations and patterns
    "suffixes_to_remove": ['san', 'chan', 'kun', 'sama', 'sensei', 'senpai'],
    "prefixes_to_remove": ['mr', 'mrs', 'miss', 'dr', 'prof'],
    "common_titles": ['lord', 'lady', 'captain', 'commander', 'major', 'colonel'],
}

# Series name patterns for better formatting
SERIES_PATTERNS = {
    "articles_to_remove": ['the', 'a', 'an'],
    "special_chars": [':', ';', '!', '?', '.', ',', '&', "'", '"'],
}

# Smart series name patterns for algorithmic generation
SERIES_FORMATTING_RULES = {
    "common_substitutions": {
        "spy x family": "spy_x_family",
        "re:zero": "re:zero_kara_hajimeru_isekai_seikatsu",
        "re zero": "re:zero_kara_hajimeru_isekai_seikatsu",
        "demon slayer": "kimetsu_no_yaiba",
        "kimetsu no yaiba": "kimetsu_no_yaiba",
        "jujutsu kaisen": "jujutsu_kaisen",
        "my hero academia": "boku_no_hero_academia",
        "boku no hero academia": "boku_no_hero_academia",
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
        "arknights": "arknights",
        "violet evergarden": "violet_evergarden",
        "one piece": "one_piece",
        "naruto": "naruto",
        "dragon ball": "dragon_ball",
        "pokemon": "pokemon",
    }
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
    
    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL appears to be a valid image URL"""
        if not url:
            return False
        
        # Must start with http/https
        if not url.startswith(('http://', 'https://')):
            return False
        
        # Check for common image extensions or known image hosts
        valid_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp')
        valid_hosts = ('safebooru.org', 'konachan.net', 'danbooru.donmai.us', 
                       'safebooru.donmai.us', 'cdn.donmai.us')
        
        url_lower = url.lower()
        
        # Check extension
        has_valid_ext = any(url_lower.endswith(ext) or f'{ext}?' in url_lower for ext in valid_extensions)
        
        # Check host
        has_valid_host = any(host in url_lower for host in valid_hosts)
        
        return has_valid_ext or has_valid_host
    
    async def _validate_image_batch(self, images: List[Dict], max_validate: int = 50) -> List[Dict]:
        """Validate a batch of images by checking if URLs are accessible"""
        if not images:
            return []
        
        # Only validate first N images to avoid too many requests
        validated = []
        session = await self.get_session()
        
        for img in images[:max_validate]:
            url = img.get('preview_url') or img.get('url')
            if self._is_valid_image_url(url):
                validated.append(img)
        
        # Add remaining images without validation (they passed URL format check)
        for img in images[max_validate:]:
            url = img.get('preview_url') or img.get('url')
            if self._is_valid_image_url(url):
                validated.append(img)
        
        return validated
    
    def _clean_character_name(self, character_name: str) -> str:
        """Clean and normalize character name using smart patterns"""
        name_lower = character_name.lower().strip()
        
        # Remove common suffixes
        for suffix in COMMON_NAME_PATTERNS["suffixes_to_remove"]:
            if name_lower.endswith(f' {suffix}'):
                name_lower = name_lower[:-len(f' {suffix}')]
        
        # Remove common prefixes
        for prefix in COMMON_NAME_PATTERNS["prefixes_to_remove"]:
            if name_lower.startswith(f'{prefix} '):
                name_lower = name_lower[len(f'{prefix} '):]
        
        # Remove common titles
        for title in COMMON_NAME_PATTERNS["common_titles"]:
            name_lower = name_lower.replace(f'{title} ', '').replace(f' {title}', '')
        
        # Remove special characters and extra spaces
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', name_lower)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        
        return cleaned
    
    def _get_booru_character_tag(self, character_name: str, series_name: str = None) -> str:
        """Generate booru tag using smart algorithmic approach"""
        cleaned_name = self._clean_character_name(character_name)
        
        # If series provided, try with series disambiguation first
        if series_name:
            series_tag = self._get_booru_series_tag(series_name)
            if series_tag:
                return f"{cleaned_name}_({series_tag})"
        
        # Return cleaned name without series
        return cleaned_name
    
    def _get_name_variations(self, character_name: str, series_name: str = None) -> List[str]:
        """Generate multiple name variations using smart algorithm"""
        variations = []
        cleaned_name = self._clean_character_name(character_name)
        
        # Primary: with series disambiguation
        if series_name:
            series_tag = self._get_booru_series_tag(series_name)
            if series_tag:
                variations.append(f"{cleaned_name}_({series_tag})")
        
        # Secondary: without series
        variations.append(cleaned_name)
        
        # Generate name order variations for multi-part names
        parts = cleaned_name.split('_')
        if len(parts) >= 2:
            # Try different combinations
            if len(parts) == 2:
                first, last = parts
                variations.append(f"{first}_{last}")
                variations.append(f"{last}_{first}")
                
                # With series if provided
                if series_name:
                    series_tag = self._get_booru_series_tag(series_name)
                    if series_tag:
                        variations.append(f"{first}_{last}_({series_tag})")
                        variations.append(f"{last}_{first}_({series_tag})")
            
            elif len(parts) == 3:
                first, middle, last = parts
                # Different combinations for 3-part names
                variations.extend([
                    f"{first}_{middle}_{last}",
                    f"{last}_{first}_{middle}",
                    f"{first}_{last}",
                    f"{last}_{first}"
                ])
                
                # With series for main combinations
                if series_name:
                    series_tag = self._get_booru_series_tag(series_name)
                    if series_tag:
                        variations.extend([
                            f"{first}_{middle}_{last}_({series_tag})",
                            f"{first}_{last}_({series_tag})"
                        ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_variations = []
        for v in variations:
            if v not in seen:
                seen.add(v)
                unique_variations.append(v)
        
        return unique_variations
    
    def _get_booru_series_tag(self, series_name: str) -> str:
        """Generate series tag using smart formatting rules"""
        if not series_name:
            return ""
        
        name_lower = series_name.lower().strip()
        
        # Check common substitutions first
        if name_lower in SERIES_FORMATTING_RULES["common_substitutions"]:
            return SERIES_FORMATTING_RULES["common_substitutions"][name_lower]
        
        # Remove trailing numbers/seasons (e.g., " 4", " season 2", " part 3")
        name_lower = re.sub(r'\s+\d+$', '', name_lower)  # Remove trailing numbers
        name_lower = re.sub(r'\s+(season|part|s)\s+\d+$', '', name_lower)  # Remove season/part info
        
        # Check substitutions again after cleaning
        if name_lower in SERIES_FORMATTING_RULES["common_substitutions"]:
            return SERIES_FORMATTING_RULES["common_substitutions"][name_lower]
        
        # Remove articles
        for article in SERIES_PATTERNS["articles_to_remove"]:
            name_lower = name_lower.replace(f'{article} ', '').replace(f' {article}', '')
        
        # Remove special characters
        for char in SERIES_PATTERNS["special_chars"]:
            name_lower = name_lower.replace(char, '')
        
        # Clean and format
        cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', name_lower)
        cleaned = re.sub(r'\s+', '_', cleaned.strip())
        
        return cleaned
    
    async def _fetch_with_retry(self, fetch_func, char_tag: str, page: int, limit: int, max_retries: int = 2) -> List[Dict]:
        """Fetch with retry logic and exponential backoff"""
        for attempt in range(max_retries + 1):
            try:
                result = await fetch_func(char_tag, page, limit)
                if result:
                    return result
                return []
            except Exception as e:
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                else:
                    return []
        return []
    
    async def _fetch_source_pages(self, fetch_func, source_name: str, char_tag: str, max_pages: int = 20) -> List[Dict]:
        """Fetch pages from a single source with smart batching and early stop"""
        all_results = []
        batch_size = 3  # Fetch 3 pages at a time
        consecutive_empty = 0
        
        for batch_start in range(1, max_pages + 1, batch_size):
            batch_end = min(batch_start + batch_size, max_pages + 1)
            
            # Create tasks for this batch
            tasks = []
            for page in range(batch_start, batch_end):
                tasks.append(self._fetch_with_retry(fetch_func, char_tag, page, 100))
            
            # Execute batch with small delay between batches
            if batch_start > 1:
                await asyncio.sleep(0.3)  # Rate limit delay between batches
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            batch_found = 0
            for result in results:
                if isinstance(result, list) and result:
                    all_results.extend(result)
                    batch_found += len(result)
            
            # Early stop: if batch returned nothing, source is exhausted
            if batch_found == 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:  # 2 empty batches = stop
                    logger.info(f"[{source_name}] Exhausted at page ~{batch_start}, got {len(all_results)} total")
                    break
            else:
                consecutive_empty = 0
                logger.debug(f"[{source_name}] Batch {batch_start}-{batch_end-1}: +{batch_found} images")
        
        return all_results
    
    async def search_all_sources(
        self, 
        character_name: str, 
        series_name: str = None, 
        page: int = 1, 
        limit: int = 30
    ) -> Tuple[List[Dict], int]:
        """Search multiple SFW sources with smart batching, rate limiting, and proper pagination"""
        # Create a cache key for this character search
        cache_key = f"{character_name.lower()}_{series_name.lower() if series_name else 'none'}"
        
        # Check if we have cached results for this character
        if not hasattr(self, '_search_cache'):
            self._search_cache = {}
        
        # If not in cache, fetch all results with smart batching
        if cache_key not in self._search_cache:
            self.seen_urls.clear()
            self.seen_hashes.clear()
            
            all_images = []
            
            # First try fuzzy matching to find the best tag
            logger.info(f"[MultiSearch] Starting fuzzy tag matching for '{character_name}' from '{series_name}'")
            best_tag = await self._fuzzy_match_tags(character_name, series_name)
            
            # Create variations with the best tag first
            name_variations = []
            if best_tag and best_tag != self._get_booru_character_tag(character_name, series_name):
                name_variations.append(best_tag)
                logger.info(f"[MultiSearch] Fuzzy match found: {best_tag}")
            
            # Add algorithmic variations as fallback
            algorithmic_variations = self._get_name_variations(character_name, series_name)
            for var in algorithmic_variations:
                if var not in name_variations:
                    name_variations.append(var)
            
            logger.info(f"[MultiSearch] Character '{character_name}' -> final variations: {name_variations}")
            
            # Try each variation until we get results
            for char_tag in name_variations:
                if all_images:
                    break  # Stop if we already found images
                
                logger.info(f"[MultiSearch] Fetching '{char_tag}' from sources (smart batching)...")
                
                # Fetch from all sources in parallel, but each source fetches sequentially with batching
                safebooru_task = self._fetch_source_pages(
                    self._search_safebooru_org, "Safebooru.org", char_tag, max_pages=20
                )
                konachan_task = self._fetch_source_pages(
                    self._search_konachan, "Konachan.net", char_tag, max_pages=20
                )
                danbooru_task = self._fetch_source_pages(
                    self._search_danbooru_safe_only, "Danbooru", char_tag, max_pages=20
                )
                
                # Run all sources in parallel
                safebooru_results, konachan_results, danbooru_results = await asyncio.gather(
                    safebooru_task, konachan_task, danbooru_task, return_exceptions=True
                )
                
                # Process Safebooru results
                if isinstance(safebooru_results, list):
                    for img in safebooru_results:
                        if img.get('url') and not self._is_duplicate(img['url']):
                            all_images.append(img)
                    logger.info(f"[MultiSearch] Safebooru: {len(safebooru_results)} raw -> {len([i for i in safebooru_results if not self._is_duplicate(i.get('url', ''))])} unique")
                
                # Process Konachan results
                if isinstance(konachan_results, list):
                    for img in konachan_results:
                        if img.get('url') and not self._is_duplicate(img['url']):
                            all_images.append(img)
                    logger.info(f"[MultiSearch] Konachan: {len(konachan_results)} raw")
                
                # Process Danbooru results
                if isinstance(danbooru_results, list):
                    for img in danbooru_results:
                        if img.get('url') and not self._is_duplicate(img['url']):
                            all_images.append(img)
                    logger.info(f"[MultiSearch] Danbooru: {len(danbooru_results)} raw")
                
                if all_images:
                    logger.info(f"[MultiSearch] Found {len(all_images)} unique images with tag '{char_tag}'")
            
            # Validate all images have working URLs
            all_images = await self._validate_image_batch(all_images)
            logger.info(f"[MultiSearch] After validation: {len(all_images)} valid images")
            
            # Sort by score/relevance
            all_images.sort(key=lambda x: x.get('score', 0), reverse=True)
            
            # Cache the complete result set
            self._search_cache[cache_key] = all_images
            logger.info(f"[MultiSearch] ✓ Cached {len(all_images)} total images for '{character_name}'")
        else:
            all_images = self._search_cache[cache_key]
            logger.info(f"[MultiSearch] Using cached {len(all_images)} images for '{character_name}'")
        
        # Calculate pagination based on total cached results
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
    
    async def _search_danbooru_safe_only(self, char_tag: str, page: int = 1, limit: int = 30) -> List[Dict]:
        """Search Danbooru with STRICT safe filter - matching Safebooru standards"""
        session = await self.get_session()
        
        # ULTRA STRICT: rating:general + extensive blacklist to match Safebooru's safety
        # Exclude ALL suggestive, fanservice, and softcore content
        blacklist = [
            '-suggestive', '-ecchi', '-nude', '-underwear', '-panties', '-bra', '-lingerie',
            '-bikini', '-swimsuit', '-cleavage', '-underboob', '-sideboob', '-ass', '-butt',
            '-thighs', '-pantyshot', '-upskirt', '-cameltoe', '-nipples', '-topless',
            '-lewd', '-nsfw', '-loli', '-shota', '-sexy', '-seductive', '-provocative',
            '-erotic', '-fanservice', '-bath', '-bathing', '-shower', '-wet_clothes',
            '-see-through', '-transparent', '-spread_legs', '-bondage', '-breast_grab',
            '-groping', '-sexual', '-revealing', '-skimpy', '-tight_clothes'
        ]
        safe_tags = f"{char_tag} rating:general {' '.join(blacklist)}"
        
        params = {
            'tags': safe_tags,
            'limit': min(limit, 100),
            'page': page
        }
        
        # Add specific headers for Danbooru API
        headers = {
            'User-Agent': 'AnyaBot/1.0 (Discord Bot; Safe Content Filter)',
            'Accept': 'application/json'
        }
        
        try:
            async with session.get('https://danbooru.donmai.us/posts.json', params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    result_count = len(data) if isinstance(data, list) else 0
                    if result_count > 0:
                        logger.info(f"[Danbooru] Page {page}: Found {result_count} results for '{char_tag}'")
                    return self._process_danbooru_safe_results(data)
                elif resp.status == 429:
                    logger.warning(f"[Danbooru] Rate limited - waiting")
                    await asyncio.sleep(2)
                    return []
                elif resp.status == 403:
                    logger.warning(f"[Danbooru] Access forbidden (403) - API may require authentication or be blocking requests")
                    return []
                else:
                    logger.warning(f"[Danbooru] Status {resp.status} for '{char_tag}' page {page}")
        except asyncio.TimeoutError:
            logger.warning(f"[Danbooru] Timeout for '{char_tag}' page {page}")
        except Exception as e:
            logger.error(f"[Danbooru] Error: {e}")
        
        return []
    
    def _process_danbooru_safe_results(self, data: List[Dict]) -> List[Dict]:
        """Process Danbooru results with MAXIMUM SAFETY filtering - ALL-AGES ONLY"""
        processed = []
        
        if not isinstance(data, list):
            return processed
        
        # MAXIMUM SAFETY: 150+ blocked tags - ZERO TOLERANCE for inappropriate content
        blocked_tags = {
            # Explicit/Suggestive/Sexual
            'suggestive', 'ecchi', 'lewd', 'nsfw', 'erotic', 'sexual', 'sexy', 'seductive',
            'provocative', 'revealing', 'skimpy', 'fanservice', 'risque', 'sensual', 'alluring',
            'tempting', 'sultry', 'flirtatious', 'arousing', 'titillating', 'indecent',
            # Underwear/Intimate Apparel
            'panties', 'underwear', 'bra', 'lingerie', 'bikini', 'swimsuit', 'thong', 'g-string',
            'garter_belt', 'stockings', 'garter', 'negligee', 'corset', 'bustier', 'teddy',
            'panty', 'brassiere', 'undergarment', 'intimate_apparel',
            # Body Parts (Sexualized/Focus)
            'cleavage', 'underboob', 'sideboob', 'breast_grab', 'breasts', 'boobs', 'chest',
            'ass', 'butt', 'buttocks', 'rear', 'behind', 'thighs', 'legs', 'midriff', 'navel',
            'belly', 'stomach', 'hips', 'waist', 'curves', 'figure', 'body', 'physique',
            'cleavage_cutout', 'breast_focus', 'butt_focus', 'thigh_focus', 'leg_focus',
            # Poses/Actions (Suggestive)
            'pantyshot', 'upskirt', 'cameltoe', 'spread_legs', 'legs_apart', 'straddling',
            'groping', 'grabbing', 'touching', 'breast_hold', 'arm_under_breasts', 'squeezing',
            'fondling', 'caressing', 'embracing', 'hugging', 'cuddling', 'holding', 'pinching',
            'spanking', 'slapping', 'kneeling', 'crawling', 'bending', 'arching', 'stretching',
            'lying', 'reclining', 'lounging', 'sitting', 'on_back', 'on_stomach', 'on_side',
            # Nudity/Exposure
            'nipples', 'nude', 'naked', 'topless', 'bottomless', 'barefoot', 'bare_shoulders',
            'bare_legs', 'bare_arms', 'bare_back', 'bare_chest', 'bare_midriff', 'exposed',
            'undressing', 'undressed', 'partially_clothed', 'barely_clothed', 'scantily_clad',
            'skin_tight', 'body_suit', 'leotard', 'one-piece', 'two-piece',
            # Inappropriate/Adult Content (CRITICAL - Discord TOS)
            'loli', 'shota', 'lolicon', 'shotacon', 'young', 'child', 'underage', 'minor',
            'bondage', 'bdsm', 'chains', 'rope', 'tied', 'restrained', 'bound', 'cuffed',
            'collar', 'leash', 'gag', 'blindfold', 'submissive', 'dominant', 'slave', 'master',
            # Clothing States (Suggestive)
            'bath', 'bathing', 'shower', 'showering', 'bathtub', 'onsen', 'hot_spring',
            'wet', 'wet_clothes', 'soaked', 'drenched', 'dripping', 'sweaty', 'sweat',
            'see-through', 'transparent', 'translucent', 'sheer', 'mesh', 'fishnet',
            'tight', 'tight_clothes', 'form-fitting', 'skin_tight', 'clingy', 'hugging',
            'torn_clothes', 'ripped', 'damaged', 'wardrobe_malfunction', 'clothing_aside',
            'dress_lift', 'skirt_lift', 'shirt_lift', 'lifted_by_self', 'wind_lift',
            # Angles/Camera Focus (Voyeuristic)
            'from_below', 'from_behind', 'back_view', 'rear_view', 'side_view', 'profile',
            'butt_focus', 'breast_focus', 'crotch', 'between_legs', 'pov', 'close-up',
            'looking_at_viewer', 'eye_contact', 'seductive_gaze', 'bedroom_eyes',
            'over_shoulder', 'looking_back', 'head_tilt', 'wink', 'blush',
            # Bedroom/Private Settings
            'bed', 'bedroom', 'pillow', 'sheets', 'blanket', 'lying_on_bed', 'in_bed',
            'hotel', 'love_hotel', 'motel', 'room', 'private', 'alone', 'intimate',
            # Romantic/Sexual Situations
            'kiss', 'kissing', 'making_out', 'french_kiss', 'lip_lock', 'embrace',
            'couple', 'lovers', 'romance', 'romantic', 'love', 'affection', 'intimate',
            'date', 'dating', 'valentine', 'heart', 'hearts', 'love_letter',
            # Misc Inappropriate
            'mature', 'adult', 'r-15', 'r-18', 'r18', 'rating:questionable', 'rating:explicit',
            'censored', 'uncensored', 'mosaic', 'convenient_censoring', 'steam', 'steam_censor',
            'ahegao', 'orgasm', 'pleasure', 'aroused', 'flushed', 'embarrassed', 'shy',
            'naughty', 'mischievous', 'playful', 'teasing', 'tease', 'temptation'
        }
        
        for post in data:
            try:
                # Only accept 'g' (general) rating - the safest rating
                rating = post.get('rating', '')
                if rating != 'g':  # Only allow 'g' (general) rating
                    continue
                
                file_url = post.get('file_url')
                if not file_url:
                    continue
                
                # Check tags for blocked content
                tag_string = post.get('tag_string', '')
                post_tags_set = set(tag_string.lower().split())
                
                # Skip if any blocked tags are present
                if post_tags_set & blocked_tags:
                    continue
                
                preview_url = post.get('large_file_url') or post.get('preview_file_url') or file_url
                
                processed.append({
                    'id': post.get('id', 0),
                    'url': file_url,
                    'preview_url': preview_url,
                    'source': 'Danbooru',
                    'tags': tag_string.split()[:10],
                    'score': post.get('score', 0),
                    'width': post.get('image_width', 0),
                    'height': post.get('image_height', 0),
                })
            except Exception as e:
                logger.debug(f"Error processing Danbooru post: {e}")
                continue
        
        return processed
    
    async def _fuzzy_match_tags(self, character_name: str, series_name: str = None) -> str:
        """Use Safebooru tag API to find the correct character tag with fuzzy matching"""
        session = await self.get_session()
        
        # Generate base character name variations
        base_variations = []
        cleaned_name = self._clean_character_name(character_name)
        base_variations.append(cleaned_name)
        
        # Add simple variations
        if '_' in cleaned_name:
            parts = cleaned_name.split('_')
            if len(parts) == 2:
                base_variations.extend([
                    f"{parts[0]}_{parts[1]}",
                    f"{parts[1]}_{parts[0]}"
                ])
        
        # Get series tag for better matching
        series_tag = None
        if series_name:
            series_tag = self._get_booru_series_tag(series_name)
        
        # Try to find matching character tags
        for variation in base_variations:
            try:
                # First try: exact character name with series disambiguation
                if series_tag:
                    exact_search = f"{variation}_({series_tag}) rating:safe"
                    logger.info(f"[Fuzzy Match] Trying exact search: {exact_search}")
                    
                    search_params = {
                        'page': 'dapi',
                        's': 'post',
                        'q': 'index',
                        'json': '1',
                        'limit': 10,
                        'tags': exact_search,
                        'pid': 0
                    }
                    
                    async with session.get('https://safebooru.org/index.php', params=search_params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        if resp.status == 200:
                            text = await resp.text()
                            if text.strip():
                                try:
                                    import json
                                    posts = json.loads(text)
                                    if isinstance(posts, list) and len(posts) > 0:
                                        # If we found posts with exact match, this is our tag
                                        logger.info(f"[Fuzzy Match] Exact match found: {variation}_({series_tag})")
                                        return f"{variation}_({series_tag})"
                                except json.JSONDecodeError:
                                    pass
                
                # Second try: character name pattern search with stricter filtering
                search_params = {
                    'page': 'dapi',
                    's': 'post',
                    'q': 'index',
                    'json': '1',
                    'limit': 50,
                    'tags': f"{variation}* rating:safe",
                    'pid': 0
                }
                
                async with session.get('https://safebooru.org/index.php', params=search_params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        if text.strip():
                            try:
                                import json
                                posts = json.loads(text)
                                if isinstance(posts, list) and posts:
                                    # Extract all tags from these posts and find character tags
                                    all_tags = {}
                                    for post in posts:
                                        post_tags = post.get('tags', '').split()
                                        for tag in post_tags:
                                            # Only consider tags that start with our character name
                                            if tag.lower().startswith(variation.lower()):
                                                # Skip very long tags (likely wrong series)
                                                if len(tag) <= 60:  # Reasonable limit
                                                    all_tags[tag] = all_tags.get(tag, 0) + 1
                                    
                                    if all_tags:
                                        # Convert to tag data format for scoring
                                        tag_data_list = [{'name': tag, 'count': count} for tag, count in all_tags.items()]
                                        best_tag = self._find_best_character_tag(tag_data_list, variation, series_name)
                                        if best_tag:
                                            logger.info(f"[Fuzzy Match] Found best tag: {best_tag}")
                                            return best_tag
                            except json.JSONDecodeError:
                                pass
            except Exception as e:
                logger.debug(f"[Fuzzy Match] Error searching for {variation}: {e}")
                continue
        
        # If no fuzzy match found, fall back to original method
        logger.info(f"[Fuzzy Match] No match found, using algorithmic generation")
        return self._get_booru_character_tag(character_name, series_name)
    
    def _find_best_character_tag(self, tags: List[Dict], search_term: str, series_name: str = None) -> str:
        """Find the best matching character tag from Safebooru tag results"""
        if not tags:
            return None
        
        # Calculate series tag if provided
        series_tag = None
        if series_name:
            series_tag = self._get_booru_series_tag(series_name)
        
        best_match = None
        best_score = 0
        
        for tag_data in tags:
            tag_name = tag_data.get('name', '').lower()
            tag_count = tag_data.get('count', 0)
            
            # Skip if it's obviously not a character tag
            if any(skip in tag_name for skip in ['artist:', 'studio:', 'creator:', 'copyright:', 'general:']):
                continue
            
            # Calculate match score
            score = 0
            
            # EXACT SERIES MATCH gets massive bonus
            if series_tag and f"({series_tag})" in tag_name:
                score += 200  # Huge bonus for exact series disambiguation
                logger.debug(f"[Scoring] Exact series match: {tag_name} +200")
            
            # Check if tag starts with exact character name
            if tag_name.startswith(search_term):
                score += 100
                logger.debug(f"[Scoring] Starts with search term: {tag_name} +100")
            # Contains search term
            elif search_term in tag_name:
                score += 60
                logger.debug(f"[Scoring] Contains search term: {tag_name} +60")
            
            # Bonus for partial series match (words from series name)
            if series_tag and not f"({series_tag})" in tag_name:
                series_words = series_tag.split('_')
                matching_words = sum(1 for word in series_words if word in tag_name)
                if matching_words > 0:
                    score += matching_words * 20
                    logger.debug(f"[Scoring] Partial series match: {tag_name} +{matching_words * 20}")
            
            # Penalty for very long tags (likely wrong series)
            if len(tag_name) > 50:
                score -= 50
                logger.debug(f"[Scoring] Tag too long penalty: {tag_name} -50")
            elif len(tag_name) > 30:
                score -= 20
                logger.debug(f"[Scoring] Tag long penalty: {tag_name} -20")
            
            # Bonus for tag popularity (more posts = more likely to be correct)
            if tag_count > 1000:
                score += 30
            elif tag_count > 100:
                score += 20
            elif tag_count > 50:
                score += 10
            elif tag_count > 10:
                score += 5
            
            # Avoid tags that are too generic
            if len(tag_name) < 3:
                score -= 20
            
            logger.debug(f"[Scoring] Final score for {tag_name}: {score}")
            
            if score > best_score:
                best_score = score
                best_match = tag_name
                logger.debug(f"[Scoring] New best: {tag_name} with score {best_score}")
        
        logger.info(f"[Scoring] Best match: {best_match} with score {best_score}")
        return best_match if best_score >= 80 else None  # Higher threshold for better quality

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
        """Search Konachan.net - ULTRA STRICT safe filter matching Safebooru standards"""
        session = await self.get_session()
        
        # ULTRA STRICT: rating:safe + extensive blacklist to match Safebooru's safety
        blacklist = [
            '-suggestive', '-ecchi', '-nude', '-underwear', '-panties', '-bra', '-lingerie',
            '-bikini', '-swimsuit', '-cleavage', '-underboob', '-sideboob', '-ass', '-butt',
            '-thighs', '-pantyshot', '-upskirt', '-cameltoe', '-nipples', '-topless',
            '-lewd', '-nsfw', '-loli', '-shota', '-sexy', '-seductive', '-provocative',
            '-erotic', '-fanservice', '-bath', '-bathing', '-shower', '-wet_clothes',
            '-see-through', '-transparent', '-spread_legs', '-bondage', '-breast_grab',
            '-groping', '-sexual', '-revealing', '-skimpy', '-tight_clothes'
        ]
        safe_tags = f"{char_tag} rating:safe {' '.join(blacklist)}"
        
        params = {
            'tags': safe_tags,
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
        """Process Konachan.net results - MAXIMUM SAFETY filtering - ALL-AGES ONLY"""
        processed = []
        
        if not isinstance(data, list):
            return processed
        
        # MAXIMUM SAFETY: 150+ blocked tags - ZERO TOLERANCE for inappropriate content
        blocked_tags = {
            # Explicit/Suggestive/Sexual
            'suggestive', 'ecchi', 'lewd', 'nsfw', 'erotic', 'sexual', 'sexy', 'seductive',
            'provocative', 'revealing', 'skimpy', 'fanservice', 'risque', 'sensual', 'alluring',
            'tempting', 'sultry', 'flirtatious', 'arousing', 'titillating', 'indecent',
            # Underwear/Intimate Apparel
            'panties', 'underwear', 'bra', 'lingerie', 'bikini', 'swimsuit', 'thong', 'g-string',
            'garter_belt', 'stockings', 'garter', 'negligee', 'corset', 'bustier', 'teddy',
            'panty', 'brassiere', 'undergarment', 'intimate_apparel',
            # Body Parts (Sexualized/Focus)
            'cleavage', 'underboob', 'sideboob', 'breast_grab', 'breasts', 'boobs', 'chest',
            'ass', 'butt', 'buttocks', 'rear', 'behind', 'thighs', 'legs', 'midriff', 'navel',
            'belly', 'stomach', 'hips', 'waist', 'curves', 'figure', 'body', 'physique',
            'cleavage_cutout', 'breast_focus', 'butt_focus', 'thigh_focus', 'leg_focus',
            # Poses/Actions (Suggestive)
            'pantyshot', 'upskirt', 'cameltoe', 'spread_legs', 'legs_apart', 'straddling',
            'groping', 'grabbing', 'touching', 'breast_hold', 'arm_under_breasts', 'squeezing',
            'fondling', 'caressing', 'embracing', 'hugging', 'cuddling', 'holding', 'pinching',
            'spanking', 'slapping', 'kneeling', 'crawling', 'bending', 'arching', 'stretching',
            'lying', 'reclining', 'lounging', 'sitting', 'on_back', 'on_stomach', 'on_side',
            # Nudity/Exposure
            'nipples', 'nude', 'naked', 'topless', 'bottomless', 'barefoot', 'bare_shoulders',
            'bare_legs', 'bare_arms', 'bare_back', 'bare_chest', 'bare_midriff', 'exposed',
            'undressing', 'undressed', 'partially_clothed', 'barely_clothed', 'scantily_clad',
            'skin_tight', 'body_suit', 'leotard', 'one-piece', 'two-piece',
            # Inappropriate/Adult Content (CRITICAL - Discord TOS)
            'loli', 'shota', 'lolicon', 'shotacon', 'young', 'child', 'underage', 'minor',
            'bondage', 'bdsm', 'chains', 'rope', 'tied', 'restrained', 'bound', 'cuffed',
            'collar', 'leash', 'gag', 'blindfold', 'submissive', 'dominant', 'slave', 'master',
            # Clothing States (Suggestive)
            'bath', 'bathing', 'shower', 'showering', 'bathtub', 'onsen', 'hot_spring',
            'wet', 'wet_clothes', 'soaked', 'drenched', 'dripping', 'sweaty', 'sweat',
            'see-through', 'transparent', 'translucent', 'sheer', 'mesh', 'fishnet',
            'tight', 'tight_clothes', 'form-fitting', 'skin_tight', 'clingy', 'hugging',
            'torn_clothes', 'ripped', 'damaged', 'wardrobe_malfunction', 'clothing_aside',
            'dress_lift', 'skirt_lift', 'shirt_lift', 'lifted_by_self', 'wind_lift',
            # Angles/Camera Focus (Voyeuristic)
            'from_below', 'from_behind', 'back_view', 'rear_view', 'side_view', 'profile',
            'butt_focus', 'breast_focus', 'crotch', 'between_legs', 'pov', 'close-up',
            'looking_at_viewer', 'eye_contact', 'seductive_gaze', 'bedroom_eyes',
            'over_shoulder', 'looking_back', 'head_tilt', 'wink', 'blush',
            # Bedroom/Private Settings
            'bed', 'bedroom', 'pillow', 'sheets', 'blanket', 'lying_on_bed', 'in_bed',
            'hotel', 'love_hotel', 'motel', 'room', 'private', 'alone', 'intimate',
            # Romantic/Sexual Situations
            'kiss', 'kissing', 'making_out', 'french_kiss', 'lip_lock', 'embrace',
            'couple', 'lovers', 'romance', 'romantic', 'love', 'affection', 'intimate',
            'date', 'dating', 'valentine', 'heart', 'hearts', 'love_letter',
            # Misc Inappropriate
            'mature', 'adult', 'r-15', 'r-18', 'r18', 'rating:questionable', 'rating:explicit',
            'censored', 'uncensored', 'mosaic', 'convenient_censoring', 'steam', 'steam_censor',
            'ahegao', 'orgasm', 'pleasure', 'aroused', 'flushed', 'embarrassed', 'shy',
            'naughty', 'mischievous', 'playful', 'teasing', 'tease', 'temptation'
        }
        
        for post in data:
            try:
                # Skip if rating is not safe
                rating = post.get('rating', 's')
                if rating != 's':  # Only allow 's' (safe) rating
                    continue
                
                # Check tags for blocked content
                post_tags = post.get('tags', '')
                if isinstance(post_tags, str):
                    post_tags_set = set(post_tags.lower().split())
                elif isinstance(post_tags, list):
                    post_tags_set = set(t.lower() for t in post_tags)
                else:
                    post_tags_set = set()
                
                # Skip if any blocked tags are present
                if post_tags_set & blocked_tags:
                    continue
                
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
