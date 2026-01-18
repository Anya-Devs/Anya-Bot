import aiohttp
import discord
import asyncio
from typing import Optional, List, Dict, Set
import random
import logging

# Setup logging for art sources
art_logger = logging.getLogger('art_sources')
art_logger.setLevel(logging.DEBUG)
if not art_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    art_logger.addHandler(handler)

# All available art sources with metadata
# nsfw_only: True = NSFW-only source, False = can contain mixed content
# requires_nsfw_channel: True = must be used in NSFW channel, False = safe for all channels
ART_SOURCES = {
    # === SFW Tag-Searchable Sources (Safe for all channels) - Search characters like "anya_forger" ===
    "safebooru": {"name": "Safebooru", "nsfw_only": False, "requires_nsfw_channel": False, "description": "SFW anime art - Tag searchable (anya_forger, naruto, etc)"},
    "tbib": {"name": "TBIB", "nsfw_only": False, "requires_nsfw_channel": False, "description": "The Big ImageBoard - Tag searchable SFW"},
    "aibooru": {"name": "AIBooru", "nsfw_only": False, "requires_nsfw_channel": False, "description": "AI-generated anime art - Tag searchable"},
    "e926": {"name": "e926", "nsfw_only": False, "requires_nsfw_channel": False, "description": "SFW art database - Tag searchable"},
    "konachan_safe": {"name": "Konachan Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime wallpapers - Tag searchable SFW"},
    "wallhaven": {"name": "Wallhaven", "nsfw_only": False, "requires_nsfw_channel": False, "description": "HD wallpapers - Search anime characters"},
    # "sankaku_safe": {"name": "Sankaku Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Huge anime database - Tag searchable SFW"},  # Disabled: Requires auth token
    "xbooru_safe": {"name": "XBooru Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime imageboard - Tag searchable SFW"},
    "rule34_safe": {"name": "Rule34 Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Large database - SFW filtered tags"},
    "hypnohub_safe": {"name": "Hypnohub Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime art - Tag searchable SFW"},
    "booru_allthefallen": {"name": "ATF Booru", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime database - Tag searchable SFW"},
    # === Mixed Content Sources (Require NSFW channel) - Best for character searches ===
    "danbooru": {"name": "Danbooru", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Best anime art database - Tag searchable"},
    "gelbooru": {"name": "Gelbooru", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Huge anime database - Tag searchable"},
    "yandere": {"name": "Yande.re", "nsfw_only": False, "requires_nsfw_channel": True, "description": "High quality anime art - Tag searchable"},
    "konachan": {"name": "Konachan", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime wallpapers - Tag searchable"},
    # "zerochan": {"name": "Zerochan", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime images - Character searchable"},  # Disabled: Cloudflare protection blocks automated requests
    # "anime_pictures": {"name": "Anime-Pictures", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime artwork - Tag searchable"},  # Disabled: Requires auth
    # "sankaku": {"name": "Sankaku", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Massive anime database - Tag searchable"},  # Disabled: Requires auth token
    # === NSFW Only Sources ===
    "rule34": {"name": "Rule34", "nsfw_only": True, "requires_nsfw_channel": True, "description": "Adult content - Tag searchable NSFW"},
    "e621": {"name": "e621", "nsfw_only": True, "requires_nsfw_channel": True, "description": "Furry art - Tag searchable NSFW"},
    "realbooru": {"name": "Realbooru", "nsfw_only": True, "requires_nsfw_channel": True, "description": "Real photos - NSFW only"},
}


# Default headers for API requests
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9"
}

class ArtSource:
    """Base class for art sources"""
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.headers = DEFAULT_HEADERS.copy()
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        raise NotImplementedError


class Danbooru(ArtSource):
    """Danbooru API - Anime art"""
    BASE_URL = "https://danbooru.donmai.us"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:general"
            
            params = {
                "tags": tags,
                "limit": min(limit, 100),
                "page": page + 1
            }
            
            # Danbooru requires proper User-Agent
            headers = {
                "User-Agent": "AnyaBot/1.0 (Discord Bot)",
                "Accept": "application/json"
            }
            
            art_logger.debug(f"Danbooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=headers) as resp:
                art_logger.debug(f"Danbooru: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        if post.get("file_url"):
                            results.append({
                                "source": "Danbooru",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_file_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                                "artist": post.get("tag_string_artist") or "Unknown",
                                "tags": post.get("tag_string_general", "").split()[:10],
                                "rating": post.get("rating", "g"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("image_width"),
                                "height": post.get("image_height")
                            })
                    art_logger.debug(f"Danbooru: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Danbooru error: {e}")
            return []
        return []


class Gelbooru(ArtSource):
    """Gelbooru API - Anime/manga art"""
    BASE_URL = "https://gelbooru.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:general"
            
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "tags": tags,
                "limit": min(limit, 100),
                "pid": page,
                "api_key": "eecaf15a3ac2d96eb0413f8dd0f7ee7fe5250d77b5dad9fe0b6b4cd5eca760afca46fd2e227b910a626db625a2c3687939c99963c9c7662a7d9306ea52762af8",
                "user_id": "1880459"
            }
            
            art_logger.debug(f"Gelbooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Gelbooru: Response status {resp.status}")
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        art_logger.debug(f"Gelbooru: Invalid content-type {content_type}, skipping")
                        return []
                    data = await resp.json()
                    results = []
                    # Handle different response formats
                    posts = []
                    if isinstance(data, dict):
                        # Check for both 'post' and 'posts' keys
                        posts = data.get("post", []) or data.get("posts", [])
                        # Also check if data itself contains post data
                        if not posts and "file_url" in data:
                            posts = [data]
                    elif isinstance(data, list):
                        posts = data
                    
                    for post in posts:
                        # More flexible URL checking
                        file_url = post.get("file_url") or post.get("image") or post.get("url")
                        if file_url:
                            # Ensure URL is complete
                            if file_url.startswith("//"):
                                file_url = "https:" + file_url
                            elif file_url.startswith("/"):
                                file_url = self.BASE_URL + file_url
                            
                            preview_url = (post.get("preview_url") or 
                                         post.get("sample_url") or 
                                         post.get("thumbnail_url") or 
                                         file_url)
                            
                            results.append({
                                "source": "Gelbooru",
                                "url": file_url,
                                "preview_url": preview_url,
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or post.get("creator") or "Unknown",
                                "tags": str(post.get("tags", "")).split()[:10] if post.get("tags") else [],
                                "rating": post.get("rating", "s"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width") or post.get("image_width"),
                                "height": post.get("height") or post.get("image_height")
                            })
                    art_logger.debug(f"Gelbooru: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Gelbooru error: {e}")
            return []
        return []


class Safebooru(ArtSource):
    """Safebooru API - SFW anime art only"""
    BASE_URL = "https://safebooru.org"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "tags": tags,
                "limit": min(limit, 100),
                "pid": page
            }
            
            art_logger.debug(f"Safebooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Safebooru: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        file_url = post.get("file_url", "")
                        if file_url:
                            if file_url.startswith('//'):
                                file_url = f"https:{file_url}"
                            preview = post.get("sample_url") or post.get("preview_url") or file_url
                            if isinstance(preview, str) and preview.startswith('//'):
                                preview = f"https:{preview}"
                            results.append({
                                "source": "Safebooru",
                                "url": file_url,
                                "preview_url": preview,
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10] if isinstance(post.get("tags"), str) else [],
                                "rating": "s",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"Safebooru: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Safebooru error: {e}")
            return []
        return []


class Konachan(ArtSource):
    """Konachan API - High quality anime wallpapers"""
    BASE_URL = "https://konachan.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:safe"
            
            params = {
                "tags": tags,
                "limit": min(limit, 100),
                "page": page + 1
            }
            
            art_logger.debug(f"Konachan: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Konachan: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        if post.get("file_url"):
                            results.append({
                                "source": "Konachan",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/post/show/{post.get('id')}",
                                "artist": post.get("author") or "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": post.get("rating", "s"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"Konachan: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Konachan error: {e}")
            return []
        return []


class Yandere(ArtSource):
    """Yande.re API - High quality anime art"""
    BASE_URL = "https://yande.re"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:safe"
            
            params = {
                "tags": tags,
                "limit": min(limit, 100),
                "page": page + 1
            }
            
            art_logger.debug(f"Yandere: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Yandere: Response status {resp.status}")
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        art_logger.debug(f"Yandere: Invalid content-type {content_type}, skipping")
                        return []
                    data = await resp.json()
                    results = []
                    for post in data:
                        if post.get("file_url"):
                            results.append({
                                "source": "Yande.re",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/post?page={page + 1}&tags={tags}",
                                "artist": post.get("author") or "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": post.get("rating", "s"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"Yandere: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Yandere error: {e}")
            return []
        return []


class Rule34(ArtSource):
    """Rule34 API - Adult content (NSFW only) - XML scraping mode"""
    BASE_URL = "https://api.rule34.xxx"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        if not nsfw:
            return []
        
        try:
            import re
            tags = query.replace(" ", "_")
            
            # Use XML endpoint - no auth required for XML format
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "tags": tags,
                "limit": min(limit, 100),
                "pid": page
            }
            
            art_logger.debug(f"Rule34: Searching '{tags}' page {page} (XML mode)")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Rule34: Response status {resp.status}")
                if resp.status == 200:
                    text = await resp.text()
                    results = []
                    
                    # Parse XML response using regex
                    post_pattern = r'<post\s+([^>]+)/>'
                    posts = re.findall(post_pattern, text)
                    
                    for post_attrs in posts:
                        # Extract attributes
                        def get_attr(name):
                            match = re.search(rf'{name}="([^"]*)"', post_attrs)
                            return match.group(1) if match else ""
                        
                        file_url = get_attr("file_url")
                        if file_url:
                            results.append({
                                "source": "Rule34",
                                "url": file_url,
                                "preview_url": get_attr("preview_url") or get_attr("sample_url") or file_url,
                                "page_url": f"https://rule34.xxx/index.php?page=post&s=view&id={get_attr('id')}",
                                "artist": get_attr("owner") or "Unknown",
                                "tags": get_attr("tags").split()[:10],
                                "rating": "e",
                                "score": int(get_attr("score") or 0),
                                "id": get_attr("id"),
                                "width": int(get_attr("width") or 0),
                                "height": int(get_attr("height") or 0)
                            })
                    
                    art_logger.debug(f"Rule34: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Rule34 error: {e}")
            return []
        return []


class Zerochan(ArtSource):
    """Zerochan API - Anime images with enhanced browser simulation"""
    BASE_URL = "https://www.zerochan.net"
    _failure_count = 0
    _max_failures = 3
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        # Skip if too many consecutive failures
        if self._failure_count >= self._max_failures:
            return []
        
        try:
            import re
            # Zerochan uses search terms in URL path
            search_term = query.replace(" ", "+").replace("_", "+")
            
            # Enhanced headers to mimic real browser
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
            }
            
            # Try JSON API first
            params = {
                "json": "",
                "l": min(limit, 50),
                "p": page + 1,
                "s": "id",
                "t": "1"
            }
            
            art_logger.debug(f"Zerochan: Searching '{search_term}' page {page}")
            
            timeout = aiohttp.ClientTimeout(total=15, connect=8)
            
            async with self.session.get(
                f"{self.BASE_URL}/{search_term}", 
                params=params, 
                headers=headers,
                timeout=timeout,
                allow_redirects=True
            ) as resp:
                art_logger.debug(f"Zerochan: Response status {resp.status}")
                
                if resp.status == 503:
                    # Service unavailable - site is blocking, try HTML scraping
                    art_logger.debug("Zerochan: 503 received, trying HTML scrape fallback")
                    return await self._scrape_html(search_term, limit, page, headers, timeout)
                
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        try:
                            data = await resp.json()
                            results = []
                            items = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                            for post in items:
                                if isinstance(post, dict):
                                    img_url = post.get("full") or post.get("large") or post.get("medium")
                                    if img_url:
                                        results.append({
                                            "source": "Zerochan",
                                            "url": img_url,
                                            "preview_url": post.get("thumbnail") or post.get("medium") or img_url,
                                            "page_url": f"{self.BASE_URL}/{post.get('id')}",
                                            "artist": post.get("source") or "Unknown",
                                            "tags": post.get("tags", [])[:10] if isinstance(post.get("tags"), list) else [],
                                            "rating": "s",
                                            "score": post.get("fav") or 0,
                                            "id": post.get("id"),
                                            "width": post.get("width"),
                                            "height": post.get("height")
                                        })
                            if results:
                                self._failure_count = 0  # Reset on success
                            art_logger.debug(f"Zerochan: Found {len(results)} results")
                            return results
                        except Exception:
                            pass
                    
                    # Try HTML scraping as fallback
                    return await self._scrape_html(search_term, limit, page, headers, timeout)
                
                # Non-200 status
                self._failure_count += 1
                return []
                
        except (aiohttp.ClientConnectorError, aiohttp.ClientSSLError, asyncio.TimeoutError) as e:
            self._failure_count += 1
            if self._failure_count >= self._max_failures:
                art_logger.warning(f"Zerochan: Too many failures, temporarily disabling")
            return []
        except Exception as e:
            art_logger.debug(f"Zerochan error: {e}")
            self._failure_count += 1
            return []
    
    async def _scrape_html(self, search_term: str, limit: int, page: int, headers: dict, timeout) -> List[Dict]:
        """Fallback HTML scraping when JSON API fails"""
        import re
        try:
            # Try direct HTML page without JSON param
            url = f"{self.BASE_URL}/{search_term}?p={page + 1}"
            
            async with self.session.get(url, headers=headers, timeout=timeout, allow_redirects=True) as resp:
                if resp.status != 200:
                    return []
                
                html = await resp.text()
                results = []
                
                # Parse image entries from HTML - look for image links
                # Pattern: <a href="/12345" ...><img src="..." ...></a>
                img_pattern = r'<a[^>]*href="/(\d+)"[^>]*>.*?<img[^>]*src="([^"]+)"[^>]*>.*?</a>'
                matches = re.findall(img_pattern, html, re.DOTALL)[:limit]
                
                for post_id, thumb_url in matches:
                    # Construct full image URL from thumbnail
                    # Zerochan thumbnails: s3.zerochan.net/240/xx/xx/xxxxx.jpg
                    # Full images: static.zerochan.net/xxx.full.xxxxx.jpg
                    if thumb_url:
                        results.append({
                            "source": "Zerochan",
                            "url": thumb_url.replace("/240/", "/full/").replace(".240.", ".full."),
                            "preview_url": thumb_url,
                            "page_url": f"{self.BASE_URL}/{post_id}",
                            "artist": "Unknown",
                            "tags": [],
                            "rating": "s",
                            "score": 0,
                            "id": post_id,
                            "width": None,
                            "height": None
                        })
                
                if results:
                    self._failure_count = 0
                    art_logger.debug(f"Zerochan HTML scrape: Found {len(results)} results")
                return results
                
        except Exception as e:
            art_logger.debug(f"Zerochan HTML scrape error: {e}")
            return []


class AnimePictures(ArtSource):
    """Anime-Pictures.net API"""
    BASE_URL = "https://anime-pictures.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "+")
            erotic_filter = "" if nsfw else "&erotic=0"
            url = f"{self.BASE_URL}/api/v3/posts?search_tag={tags}&page={page}&lim={min(limit, 80)}{erotic_filter}"
            
            # AnimePictures requires proper headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://anime-pictures.net/"
            }
            
            art_logger.debug(f"AnimePictures: Searching '{tags}' page {page}")
            async with self.session.get(url, headers=headers) as resp:
                art_logger.debug(f"AnimePictures: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data.get("posts", []) if isinstance(data, dict) else []
                    for post in posts:
                        md5 = post.get('md5', '')
                        preview = f"{self.BASE_URL}/previews/{md5[:2]}/{md5}_sp.jpg" if md5 else None
                        results.append({
                            "source": "Anime-Pictures",
                            "url": f"{self.BASE_URL}/pictures/download_image/{post.get('id')}",
                            "preview_url": preview,
                            "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                            "artist": "Unknown",
                            "tags": [],
                            "rating": "q" if post.get("erotics") else "s",
                            "score": post.get("score_number") or 0,
                            "id": post.get("id"),
                            "width": post.get("width"),
                            "height": post.get("height")
                        })
                    art_logger.debug(f"AnimePictures: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"AnimePictures error: {e}")
            return []
        return []




class E621(ArtSource):
    """e621 API - Furry art (NSFW)"""
    BASE_URL = "https://e621.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        if not nsfw:
            return []
        
        try:
            tags = query.replace(" ", "_")
            # e621 requires a proper User-Agent
            headers = {
                "User-Agent": "AnyaBot/1.0 (Discord Bot by Anya-Devs)"
            }
            
            params = {
                "tags": tags,
                "limit": min(limit, 75),
                "page": page + 1
            }
            
            art_logger.debug(f"E621: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=headers) as resp:
                art_logger.debug(f"E621: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data.get("posts", []):
                        file_data = post.get("file", {})
                        preview = post.get("preview", {})
                        if file_data.get("url"):
                            results.append({
                                "source": "e621",
                                "url": file_data.get("url"),
                                "preview_url": preview.get("url") or file_data.get("url"),
                                "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                                "artist": ", ".join(post.get("tags", {}).get("artist", []))[:50] or "Unknown",
                                "tags": post.get("tags", {}).get("general", [])[:10],
                                "rating": post.get("rating", "e"),
                                "score": post.get("score", {}).get("total") or 0,
                                "id": post.get("id"),
                                "width": file_data.get("width"),
                                "height": file_data.get("height")
                            })
                    art_logger.debug(f"E621: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"E621 error: {e}")
            return []
        return []


class Realbooru(ArtSource):
    """Realbooru API - Real photos (NSFW)"""
    BASE_URL = "https://realbooru.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        if not nsfw:
            return []
        
        try:
            tags = query.replace(" ", "_")
            
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "tags": tags,
                "limit": min(limit, 100),
                "pid": page
            }
            
            art_logger.debug(f"Realbooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Realbooru: Response status {resp.status}")
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        art_logger.debug(f"Realbooru: Invalid content-type {content_type}, skipping")
                        return []
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else data.get("post", []) if isinstance(data, dict) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "Realbooru",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": "e",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"Realbooru: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Realbooru error: {e}")
            return []
        return []


class E926(ArtSource):
    """e926 API - SFW furry/anime art"""
    BASE_URL = "https://e926.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            headers = {"User-Agent": "AnyaBot/1.0 (Discord Bot by Anya-Devs)"}
            
            params = {
                "tags": tags,
                "limit": min(limit, 75),
                "page": page + 1
            }
            
            art_logger.debug(f"E926: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=headers) as resp:
                art_logger.debug(f"E926: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data.get("posts", []):
                        file_data = post.get("file", {})
                        preview = post.get("preview", {})
                        if file_data.get("url"):
                            results.append({
                                "source": "e926",
                                "url": file_data.get("url"),
                                "preview_url": preview.get("url") or file_data.get("url"),
                                "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                                "artist": ", ".join(post.get("tags", {}).get("artist", []))[:50] or "Unknown",
                                "tags": post.get("tags", {}).get("general", [])[:10],
                                "rating": "s",
                                "score": post.get("score", {}).get("total") or 0,
                                "id": post.get("id"),
                                "width": file_data.get("width"),
                                "height": file_data.get("height")
                            })
                    art_logger.debug(f"E926: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"E926 error: {e}")
            return []
        return []


class Wallhaven(ArtSource):
    """Wallhaven API - High quality wallpapers"""
    BASE_URL = "https://wallhaven.cc/api/v1"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            params = {
                "q": query,
                "categories": "010",  # Anime category
                "purity": "100",  # SFW only
                "page": page + 1
            }
            
            async with self.session.get(f"{self.BASE_URL}/search", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for wall in data.get("data", [])[:limit]:
                        results.append({
                            "source": "Wallhaven",
                            "url": wall.get("path"),
                            "preview_url": wall.get("thumbs", {}).get("large") or wall.get("path"),
                            "page_url": wall.get("url"),
                            "artist": wall.get("uploader", {}).get("username") or "Unknown",
                            "tags": [t.get("name") for t in wall.get("tags", [])][:10],
                            "rating": "s",
                            "score": wall.get("favorites") or 0,
                            "id": wall.get("id"),
                            "width": wall.get("dimension_x"),
                            "height": wall.get("dimension_y")
                        })
                    return results
        except Exception:
            return []
        return []


class ArtStation(ArtSource):
    """ArtStation-like search via RSS"""
    BASE_URL = "https://www.artstation.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            params = {"q": query, "page": page + 1}
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            
            async with self.session.get(f"{self.BASE_URL}/api/v2/search/projects.json", params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for project in data.get("data", [])[:limit]:
                        if project.get("cover", {}).get("medium_image_url"):
                            results.append({
                                "source": "ArtStation",
                                "url": project.get("cover", {}).get("medium_image_url"),
                                "preview_url": project.get("cover", {}).get("small_image_url") or project.get("cover", {}).get("medium_image_url"),
                                "page_url": project.get("permalink"),
                                "artist": project.get("user", {}).get("username") or "Unknown",
                                "tags": [],
                                "rating": "s",
                                "score": project.get("likes_count") or 0,
                                "id": project.get("id"),
                                "width": None,
                                "height": None
                            })
                    return results
        except Exception:
            return []
        return []


class AIBooru(ArtSource):
    """AIBooru API - AI-generated anime art"""
    BASE_URL = "https://aibooru.online"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_") + " rating:general"
            
            params = {
                "tags": tags,
                "limit": min(limit, 100),
                "page": page + 1
            }
            
            # AIBooru requires proper User-Agent
            headers = {
                "User-Agent": "AnyaBot/1.0 (Discord Bot)",
                "Accept": "application/json"
            }
            
            art_logger.debug(f"AIBooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=headers) as resp:
                art_logger.debug(f"AIBooru: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "AIBooru",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_file_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                                "artist": post.get("tag_string_artist") or "AI Generated",
                                "tags": post.get("tag_string_general", "").split()[:10],
                                "rating": post.get("rating", "g"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("image_width"),
                                "height": post.get("image_height")
                            })
                    art_logger.debug(f"AIBooru: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"AIBooru error: {e}")
            return []
        return []


class TBIB(ArtSource):
    """TBIB (The Big ImageBoard) API - SFW mode with XML fallback"""
    BASE_URL = "https://tbib.org"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        import re
        try:
            tags = query.replace(" ", "_")
            
            # Try XML format first (more reliable)
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "tags": tags,
                "limit": min(limit, 100),
                "pid": page
            }
            
            art_logger.debug(f"TBIB: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"TBIB: Response status {resp.status}")
                if resp.status == 200:
                    text = await resp.text()
                    results = []
                    
                    # Parse XML response
                    post_pattern = r'<post\s+([^>]+)/>'
                    posts = re.findall(post_pattern, text)
                    
                    for post_attrs in posts[:limit]:
                        def get_attr(name):
                            match = re.search(rf'{name}="([^"]*)"', post_attrs)
                            return match.group(1) if match else ""
                        
                        file_url = get_attr("file_url")
                        if file_url:
                            results.append({
                                "source": "TBIB",
                                "url": file_url,
                                "preview_url": get_attr("preview_url") or get_attr("sample_url") or file_url,
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={get_attr('id')}",
                                "artist": get_attr("owner") or "Unknown",
                                "tags": get_attr("tags").split()[:10],
                                "rating": get_attr("rating") or "s",
                                "score": int(get_attr("score") or 0),
                                "id": get_attr("id"),
                                "width": int(get_attr("width") or 0),
                                "height": int(get_attr("height") or 0)
                            })
                    
                    art_logger.debug(f"TBIB: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.debug(f"TBIB error: {e}")
            return []
        return []


class KonachanSafe(ArtSource):
    """Konachan Safe API - SFW anime wallpapers with tag search"""
    BASE_URL = "https://konachan.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_") + " rating:safe"
            params = {"tags": tags, "limit": min(limit, 100), "page": page + 1}
            
            art_logger.debug(f"KonachanSafe: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params, headers=self.headers) as resp:
                art_logger.debug(f"KonachanSafe: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "Konachan Safe",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/post/show/{post.get('id')}",
                                "artist": post.get("author") or "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": "s",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"KonachanSafe: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"KonachanSafe error: {e}")
            return []
        return []


class SankakuSafe(ArtSource):
    """Sankaku Channel Safe API - Huge anime database with SFW filter"""
    BASE_URL = "https://capi-v2.sankakucomplex.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_") + " rating:safe"
            params = {"tags": tags, "limit": min(limit, 40), "page": page + 1}
            
            # Sankaku requires specific headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Origin": "https://chan.sankakucomplex.com",
                "Referer": "https://chan.sankakucomplex.com/"
            }
            
            art_logger.debug(f"SankakuSafe: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts", params=params, headers=headers) as resp:
                art_logger.debug(f"SankakuSafe: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "Sankaku Safe",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"https://chan.sankakucomplex.com/post/show/{post.get('id')}",
                                "artist": post.get("author", {}).get("name") if isinstance(post.get("author"), dict) else "Unknown",
                                "tags": [t.get("name") for t in post.get("tags", []) if isinstance(t, dict)][:10],
                                "rating": "s",
                                "score": post.get("total_score") or post.get("fav_count") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"SankakuSafe: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"SankakuSafe error: {e}")
            return []
        return []


class Sankaku(ArtSource):
    """Sankaku Channel API - Massive anime database"""
    BASE_URL = "https://capi-v2.sankakucomplex.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:safe"
            params = {"tags": tags, "limit": min(limit, 40), "page": page + 1}
            
            # Sankaku requires specific headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Origin": "https://chan.sankakucomplex.com",
                "Referer": "https://chan.sankakucomplex.com/"
            }
            
            art_logger.debug(f"Sankaku: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts", params=params, headers=headers) as resp:
                art_logger.debug(f"Sankaku: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "Sankaku",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"https://chan.sankakucomplex.com/post/show/{post.get('id')}",
                                "artist": post.get("author", {}).get("name") if isinstance(post.get("author"), dict) else "Unknown",
                                "tags": [t.get("name") for t in post.get("tags", []) if isinstance(t, dict)][:10],
                                "rating": post.get("rating", "s"),
                                "score": post.get("total_score") or post.get("fav_count") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"Sankaku: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Sankaku error: {e}")
            return []
        return[]


class XBooruSafe(ArtSource):
    """XBooru Safe API - Anime imageboard with SFW filter"""
    BASE_URL = "https://xbooru.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            params = {"page": "dapi", "s": "post", "q": "index", "json": 1, "tags": tags, "limit": min(limit, 100), "pid": page}
            
            art_logger.debug(f"XBooruSafe: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"XBooruSafe: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else data.get("post", []) if isinstance(data, dict) else []
                    for post in posts:
                        file_url = post.get("file_url", "")
                        if file_url:
                            if file_url.startswith('//'):
                                file_url = f"https:{file_url}"
                            preview = post.get("sample_url") or post.get("preview_url") or file_url
                            if isinstance(preview, str) and preview.startswith('//'):
                                preview = f"https:{preview}"
                            results.append({
                                "source": "XBooru Safe",
                                "url": file_url,
                                "preview_url": preview,
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10] if isinstance(post.get("tags"), str) else [],
                                "rating": "s",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"XBooruSafe: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"XBooruSafe error: {e}")
            return []
        return []


class Rule34Safe(ArtSource):
    """Rule34 Safe API - Large database with SFW filter"""
    BASE_URL = "https://api.rule34.xxx"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_") + " rating:safe"
            params = {"page": "dapi", "s": "post", "q": "index", "json": 1, "tags": tags, "limit": min(limit, 100), "pid": page}
            
            art_logger.debug(f"Rule34Safe: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Rule34Safe: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "Rule34 Safe",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                "page_url": f"https://rule34.xxx/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10] if isinstance(post.get("tags"), str) else [],
                                "rating": "s",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"Rule34Safe: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Rule34Safe error: {e}")
            return []
        return []


class HypnohubSafe(ArtSource):
    """Hypnohub Safe API - Anime art with SFW filter"""
    BASE_URL = "https://hypnohub.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            params = {"page": "dapi", "s": "post", "q": "index", "json": 1, "tags": tags, "limit": min(limit, 100), "pid": page}
            
            art_logger.debug(f"HypnohubSafe: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"HypnohubSafe: Response status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else data.get("post", []) if isinstance(data, dict) else []
                    for post in posts:
                        file_url = post.get("file_url", "")
                        if file_url:
                            if file_url.startswith('//'):
                                file_url = f"https:{file_url}"
                            preview = post.get("sample_url") or post.get("preview_url") or file_url
                            if isinstance(preview, str) and preview.startswith('//'):
                                preview = f"https:{preview}"
                            results.append({
                                "source": "Hypnohub Safe",
                                "url": file_url,
                                "preview_url": preview,
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10] if isinstance(post.get("tags"), str) else [],
                                "rating": "s",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"HypnohubSafe: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"HypnohubSafe error: {e}")
            return []
        return []


class BooruAllthefallen(ArtSource):
    """ATF Booru API - Anime database with SFW filter"""
    BASE_URL = "https://booru.allthefallen.moe"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_") + " rating:safe"
            params = {"tags": tags, "limit": min(limit, 100), "page": page + 1}
            
            art_logger.debug(f"BooruAllthefallen: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=self.headers) as resp:
                art_logger.debug(f"BooruAllthefallen: Response status {resp.status}")
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        art_logger.debug(f"BooruAllthefallen: Invalid content-type {content_type}, skipping")
                        return []
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else []
                    for post in posts:
                        if post.get("file_url"):
                            results.append({
                                "source": "ATF Booru",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_file_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                                "artist": post.get("tag_string_artist") or "Unknown",
                                "tags": post.get("tag_string_general", "").split()[:10],
                                "rating": "s",
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("image_width"),
                                "height": post.get("image_height")
                            })
                    art_logger.debug(f"BooruAllthefallen: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"BooruAllthefallen error: {e}")
            return []
        return []


class ArtAggregator:
    """SS+ Tier Art Aggregator - Maximum coverage, no missed results"""
    
    # SS+ Configuration
    MAX_CONCURRENT_REQUESTS = 25  # Concurrent requests per batch
    MAX_PAGES_PER_SOURCE = 25     # Pages to scrape per source
    RESULTS_PER_PAGE = 100        # Max results per API call
    RETRY_ATTEMPTS = 3            # Retry failed requests
    RETRY_DELAY = 0.5             # Base delay between retries
    BATCH_DELAY = 0.1             # Small delay between batches to avoid rate limits
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.sources = {
            # === SFW Tag-Searchable Sources (Best for character searches) ===
            "safebooru": Safebooru(session),
            "tbib": TBIB(session),
            "aibooru": AIBooru(session),
            "e926": E926(session),
            "konachan_safe": KonachanSafe(session),
            "wallhaven": Wallhaven(session),
            # "sankaku_safe": SankakuSafe(session),  # Disabled: Requires auth token
            "xbooru_safe": XBooruSafe(session),
            "rule34_safe": Rule34Safe(session),
            "hypnohub_safe": HypnohubSafe(session),
            "booru_allthefallen": BooruAllthefallen(session),
            # === Mixed Content Sources (NSFW channel) ===
            "danbooru": Danbooru(session),
            "gelbooru": Gelbooru(session),
            "yandere": Yandere(session),
            "konachan": Konachan(session),
            # "zerochan": Zerochan(session),  # Disabled: Cloudflare blocks automated requests
            # "anime_pictures": AnimePictures(session),  # Disabled: Requires auth
            # "sankaku": Sankaku(session),  # Disabled: Requires auth token
            # === NSFW Only Sources ===
            "rule34": Rule34(session),
            "e621": E621(session),
            "realbooru": Realbooru(session),
        }
        self._semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)
    
    def get_available_sources(self, nsfw: bool = False) -> Dict[str, dict]:
        """Get available sources based on NSFW setting"""
        available = {}
        for key, meta in ART_SOURCES.items():
            if meta["nsfw_only"] and not nsfw:
                continue
            available[key] = meta
        return available
    
    def _generate_query_variations(self, query: str) -> List[str]:
        """Generate tag variations to maximize search coverage"""
        variations = set()
        original = query.strip()
        
        # Original query
        variations.add(original)
        
        # Underscore version (most boorus use this)
        variations.add(original.replace(" ", "_"))
        
        # Lowercase versions
        variations.add(original.lower())
        variations.add(original.lower().replace(" ", "_"))
        
        # Handle common patterns like "anya forger" -> "anya_forger", "forger_anya"
        parts = original.lower().replace("_", " ").split()
        if len(parts) == 2:
            variations.add(f"{parts[0]}_{parts[1]}")
            variations.add(f"{parts[1]}_{parts[0]}")
        
        return list(variations)[:3]  # Limit to top 3 variations
    
    async def _fetch_with_retry(self, source, query: str, limit: int, nsfw: bool, page: int, source_name: str) -> List[Dict]:
        """Fetch with retry logic and rate limit handling"""
        async with self._semaphore:
            for attempt in range(self.RETRY_ATTEMPTS):
                try:
                    results = await source.search(query, limit=limit, nsfw=nsfw, page=page)
                    if results:
                        art_logger.debug(f"SS+ {source_name} page {page}: Got {len(results)} results")
                    return results
                except Exception as e:
                    if attempt < self.RETRY_ATTEMPTS - 1:
                        delay = self.RETRY_DELAY * (2 ** attempt)  # Exponential backoff
                        art_logger.warning(f"SS+ {source_name} retry {attempt + 1}/{self.RETRY_ATTEMPTS} after {delay}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        art_logger.error(f"SS+ {source_name} failed after {self.RETRY_ATTEMPTS} attempts: {e}")
            return []
    
    async def search_all(
        self, 
        query: str, 
        limit: int = 50, 
        nsfw: bool = False,
        selected_sources: Set[str] = None,
        page: int = 0,
        aggressive_load: bool = True,
        max_pages_per_source: int = None
    ) -> List[Dict]:
        """SS+ Tier Search - Scrapes every source thoroughly
        
        Args:
            query: Search query
            limit: Ignored in SS+ mode - we get EVERYTHING
            nsfw: Whether NSFW content is allowed
            selected_sources: Set of source keys to search
            page: Starting page number
            aggressive_load: If True, enables SS+ mode (always recommended)
            max_pages_per_source: Override default pages per source
        """
        results = []
        
        # SS+ defaults
        pages_to_fetch = max_pages_per_source or self.MAX_PAGES_PER_SOURCE
        per_source_limit = self.RESULTS_PER_PAGE
        
        # Default to all available sources if none selected
        if selected_sources is None:
            selected_sources = set(self.sources.keys())
        
        # Filter out NSFW-only sources if not in NSFW mode
        active_sources = []
        for name in selected_sources:
            if name in self.sources:
                meta = ART_SOURCES.get(name, {})
                if meta.get("nsfw_only") and not nsfw:
                    continue
                if meta.get("requires_nsfw_channel") and not nsfw:
                    continue
                active_sources.append(name)
        
        if not active_sources:
            return []
        
        art_logger.info(f"SS+ Scraping: '{query}' across {len(active_sources)} sources, {pages_to_fetch} pages each")
        
        # Generate query variations for maximum coverage
        query_variations = self._generate_query_variations(query) if aggressive_load else [query]
        
        # SS+ Mode: Aggressive parallel fetching with all variations
        if aggressive_load:
            all_tasks = []
            
            # Create tasks for every source, every page, every query variation
            for source_name in active_sources:
                source = self.sources.get(source_name)
                if source:
                    for q_var in query_variations:
                        for page_num in range(page, page + pages_to_fetch):
                            task = self._fetch_with_retry(
                                source, q_var, per_source_limit, nsfw, page_num, source_name
                            )
                            all_tasks.append(task)
            
            total_tasks = len(all_tasks)
            art_logger.info(f"SS+ Launching {total_tasks} parallel requests...")
            
            # Execute in batches to avoid overwhelming
            batch_size = self.MAX_CONCURRENT_REQUESTS * 2
            for i in range(0, len(all_tasks), batch_size):
                batch = all_tasks[i:i + batch_size]
                batch_results = await asyncio.gather(*batch, return_exceptions=True)
                
                for res in batch_results:
                    if isinstance(res, list):
                        results.extend(res)
                
                # Small delay between batches
                if i + batch_size < len(all_tasks):
                    await asyncio.sleep(self.BATCH_DELAY)
            
            art_logger.info(f"SS+ Raw results: {len(results)}")
        else:
            # Standard loading: one page per source (fallback)
            tasks = []
            for name in active_sources:
                source = self.sources.get(name)
                if source:
                    tasks.append(source.search(query, limit=per_source_limit, nsfw=nsfw, page=page))
            
            source_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in source_results:
                if isinstance(res, list):
                    results.extend(res)
        
        # SS+ Deduplication - by URL hash for true uniqueness
        seen_urls = set()
        seen_ids = set()
        unique_results = []
        
        for r in results:
            url = r.get("url", "")
            source_id = (r.get("source"), r.get("id"))
            
            # Skip if we've seen this exact URL or source+id combo
            if url in seen_urls or source_id in seen_ids:
                continue
            
            seen_urls.add(url)
            seen_ids.add(source_id)
            unique_results.append(r)
        
        # Sort by score (highest quality first)
        unique_results.sort(key=lambda x: x.get("score") or 0, reverse=True)
        
        art_logger.info(f"SS+ Final unique results: {len(unique_results)}")
        
        return unique_results
    
    async def search_source(
        self, 
        source_name: str, 
        query: str, 
        limit: int = 100, 
        nsfw: bool = False,
        page: int = 0
    ) -> List[Dict]:
        """Search a specific source with SS+ settings"""
        source = self.sources.get(source_name.lower())
        if not source:
            return []
        return await self._fetch_with_retry(source, query, limit, nsfw, page, source_name)
    
    async def deep_scrape(
        self,
        query: str,
        nsfw: bool = False,
        selected_sources: Set[str] = None,
        max_results: int = 5000
    ) -> List[Dict]:
        """Ultra deep scrape - keeps fetching until no more results or max reached"""
        all_results = []
        page = 0
        consecutive_empty = 0
        
        art_logger.info(f"SS+ Deep Scrape initiated for: '{query}'")
        
        while len(all_results) < max_results and consecutive_empty < 3:
            batch = await self.search_all(
                query=query,
                nsfw=nsfw,
                selected_sources=selected_sources,
                page=page,
                aggressive_load=True,
                max_pages_per_source=5  # Smaller batches for deep scrape
            )
            
            if not batch:
                consecutive_empty += 1
            else:
                consecutive_empty = 0
                # Deduplicate against existing results
                existing_urls = {r.get("url") for r in all_results}
                new_results = [r for r in batch if r.get("url") not in existing_urls]
                all_results.extend(new_results)
                art_logger.info(f"SS+ Deep Scrape page {page}: +{len(new_results)} new (total: {len(all_results)})")
            
            page += 5  # Jump ahead since we fetched 5 pages
            
            # Safety break
            if page > 100:
                break
        
        art_logger.info(f"SS+ Deep Scrape complete: {len(all_results)} total results")
        return all_results
