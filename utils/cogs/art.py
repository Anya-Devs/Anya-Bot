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
    "sankaku_safe": {"name": "Sankaku Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Huge anime database - Tag searchable SFW"},
    "xbooru_safe": {"name": "XBooru Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime imageboard - Tag searchable SFW"},
    "rule34_safe": {"name": "Rule34 Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Large database - SFW filtered tags"},
    "hypnohub_safe": {"name": "Hypnohub Safe", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime art - Tag searchable SFW"},
    "booru_allthefallen": {"name": "ATF Booru", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime database - Tag searchable SFW"},
    # === Mixed Content Sources (Require NSFW channel) - Best for character searches ===
    "danbooru": {"name": "Danbooru", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Best anime art database - Tag searchable"},
    "gelbooru": {"name": "Gelbooru", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Huge anime database - Tag searchable"},
    "yandere": {"name": "Yande.re", "nsfw_only": False, "requires_nsfw_channel": True, "description": "High quality anime art - Tag searchable"},
    "konachan": {"name": "Konachan", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime wallpapers - Tag searchable"},
    "zerochan": {"name": "Zerochan", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime images - Character searchable"},
    "anime_pictures": {"name": "Anime-Pictures", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime artwork - Tag searchable"},
    "sankaku": {"name": "Sankaku", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Massive anime database - Tag searchable"},
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
            
            art_logger.debug(f"Danbooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=self.headers) as resp:
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
    """Zerochan API - Anime images"""
    BASE_URL = "https://www.zerochan.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            # Zerochan uses search terms in URL path
            search_term = query.replace(" ", "+")
            
            params = {
                "json": "",
                "l": min(limit, 50),
                "p": page + 1,
                "s": "id",
                "t": "1"
            }
            
            art_logger.debug(f"Zerochan: Searching '{search_term}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/{search_term}", params=params, headers=self.headers) as resp:
                art_logger.debug(f"Zerochan: Response status {resp.status}")
                if resp.status == 200:
                    try:
                        data = await resp.json()
                    except:
                        art_logger.debug("Zerochan: Response is not JSON")
                        return []
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
                    art_logger.debug(f"Zerochan: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"Zerochan error: {e}")
            return []
        return []


class AnimePictures(ArtSource):
    """Anime-Pictures.net API"""
    BASE_URL = "https://anime-pictures.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "+")
            erotic_filter = "" if nsfw else "&erotic=0"
            url = f"{self.BASE_URL}/api/v3/posts?search_tag={tags}&page={page}&lim={min(limit, 80)}{erotic_filter}"
            
            art_logger.debug(f"AnimePictures: Searching '{tags}' page {page}")
            async with self.session.get(url, headers=self.headers) as resp:
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


class WaifuIm(ArtSource):
    """Waifu.im API - Waifu images"""
    BASE_URL = "https://api.waifu.im"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            # Map common queries to waifu.im tags
            tag_map = {
                "waifu": "waifu", "maid": "maid", "marin": "marin-kitagawa",
                "mori": "mori-calliope", "raiden": "raiden-shogun", "oppai": "oppai",
                "selfies": "selfies", "uniform": "uniform", "ero": "ero"
            }
            
            tag = None
            query_lower = query.lower()
            for key, value in tag_map.items():
                if key in query_lower:
                    tag = value
                    break
            
            params = {"many": "true", "is_nsfw": str(nsfw).lower()}
            if tag:
                params["included_tags"] = tag
            
            async with self.session.get(f"{self.BASE_URL}/search", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    images = data.get("images", [])
                    for img in images[:limit]:
                        results.append({
                            "source": "Waifu.im",
                            "url": img.get("url"),
                            "preview_url": img.get("preview_url") or img.get("url"),
                            "page_url": img.get("source") or img.get("url"),
                            "artist": img.get("artist", {}).get("name") if img.get("artist") else "Unknown",
                            "tags": [t.get("name") for t in img.get("tags", [])][:10],
                            "rating": "e" if img.get("is_nsfw") else "s",
                            "score": img.get("favorites") or 0,
                            "id": img.get("image_id") or img.get("signature"),
                            "width": img.get("width"),
                            "height": img.get("height")
                        })
                    return results
        except Exception:
            return []
        return []


class NekosBest(ArtSource):
    """Nekos.best API - Neko/anime images"""
    BASE_URL = "https://nekos.best/api/v2"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            # Map queries to nekos.best endpoints
            endpoint_map = {
                "neko": "neko", "kitsune": "kitsune", "waifu": "waifu",
                "husbando": "husbando", "hug": "hug", "pat": "pat",
                "kiss": "kiss", "cry": "cry", "smile": "smile",
                "wave": "wave", "thumbsup": "thumbsup", "stare": "stare",
                "highfive": "highfive", "handhold": "handhold", "nom": "nom",
                "bite": "bite", "slap": "slap", "happy": "happy",
                "wink": "wink", "poke": "poke", "dance": "dance",
                "cringe": "cringe", "blush": "blush", "bored": "bored",
                "facepalm": "facepalm", "feed": "feed", "kick": "kick",
                "laugh": "laugh", "lurk": "lurk", "nod": "nod",
                "nope": "nope", "panic": "panic", "pout": "pout",
                "punch": "punch", "shoot": "shoot", "shrug": "shrug",
                "sleep": "sleep", "smug": "smug", "think": "think",
                "yawn": "yawn", "yeet": "yeet"
            }
            
            endpoint = "neko"  # default
            query_lower = query.lower()
            for key, value in endpoint_map.items():
                if key in query_lower:
                    endpoint = value
                    break
            
            async with self.session.get(f"{self.BASE_URL}/{endpoint}?amount={min(limit, 20)}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for img in data.get("results", []):
                        results.append({
                            "source": "Nekos.best",
                            "url": img.get("url"),
                            "preview_url": img.get("url"),
                            "page_url": img.get("source_url") or img.get("url"),
                            "artist": img.get("artist_name") or "Unknown",
                            "tags": [endpoint],
                            "rating": "s",
                            "score": 0,
                            "id": img.get("url", "").split("/")[-1].split(".")[0],
                            "width": None,
                            "height": None
                        })
                    return results
        except Exception:
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


class WaifuPics(ArtSource):
    """Waifu.pics API - High quality waifu images"""
    BASE_URL = "https://api.waifu.pics"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            # Map queries to waifu.pics categories
            sfw_categories = ["waifu", "neko", "shinobu", "megumin", "bully", "cuddle", "cry", "hug", 
                            "awoo", "kiss", "lick", "pat", "smug", "bonk", "yeet", "blush", "smile",
                            "wave", "highfive", "handhold", "nom", "bite", "glomp", "slap", "kill",
                            "kick", "happy", "wink", "poke", "dance", "cringe"]
            
            category = "waifu"
            query_lower = query.lower()
            for cat in sfw_categories:
                if cat in query_lower:
                    category = cat
                    break
            
            results = []
            for _ in range(min(limit, 30)):
                async with self.session.get(f"{self.BASE_URL}/sfw/{category}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Waifu.pics",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [category],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class NekosFun(ArtSource):
    """Nekos.fun API - Neko and anime images"""
    BASE_URL = "https://nekos.fun/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["neko", "kiss", "hug", "pat", "cuddle", "tickle", "feed", "slap", "poke", "cry", "anime"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("image"):
                            results.append({
                                "source": "Nekos.fun",
                                "url": data.get("image"),
                                "preview_url": data.get("image"),
                                "page_url": data.get("image"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("image", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class WaifuIt(ArtSource):
    """Waifu.it API - Anime character images"""
    BASE_URL = "https://waifu.it/api/v4"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["waifu", "husbando", "neko", "kitsune", "pat", "hug", "kiss", "slap", "wink", "poke", "kill", "cuddle", "punch", "happy", "blush", "smile"]
            
            endpoint = "waifu"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            headers = {"Authorization": ""}  # Public API
            
            for _ in range(min(limit, 15)):
                async with self.session.get(f"{self.BASE_URL}/{endpoint}", headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Waifu.it",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": str(data.get("id", random.randint(1000, 9999))),
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class PicRe(ArtSource):
    """pic.re API - Anime artwork collection"""
    BASE_URL = "https://pic.re"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/image.json") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("file_url"):
                            results.append({
                                "source": "pic.re",
                                "url": data.get("file_url"),
                                "preview_url": data.get("file_url"),
                                "page_url": data.get("source") or data.get("file_url"),
                                "artist": data.get("author") or "Unknown",
                                "tags": data.get("tags", [])[:10] if isinstance(data.get("tags"), list) else [],
                                "rating": "s",
                                "score": 0,
                                "id": str(data.get("id", random.randint(1000, 9999))),
                                "width": data.get("width"),
                                "height": data.get("height")
                            })
            return results
        except Exception:
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


class Catboys(ArtSource):
    """Catboys API - Anime catboy images"""
    BASE_URL = "https://api.catboys.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/img") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Catboys",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": data.get("artist") or "Unknown",
                                "tags": ["catboy"],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class Purr(ArtSource):
    """Purr API - Anime images and GIFs"""
    BASE_URL = "https://purrbot.site/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            img_endpoints = ["neko", "kitsune", "hug", "pat", "kiss", "slap", "cuddle", "holo", "icon", "okami", "senko", "shiro"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in img_endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/img/sfw/{endpoint}/img") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("link"):
                            results.append({
                                "source": "Purr",
                                "url": data.get("link"),
                                "preview_url": data.get("link"),
                                "page_url": data.get("link"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("link", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class NekoLove(ArtSource):
    """Neko-Love API - Neko anime images"""
    BASE_URL = "https://neko-love.xyz/api/v1"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["neko", "kitsune", "pat", "hug", "slap", "kiss", "cry", "smug", "punch", "waifu"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Neko-Love",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class AnimeMoe(ArtSource):
    """Anime-Moe API - Cute anime art"""
    BASE_URL = "https://anime-moe.vercel.app/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            categories = ["waifu", "neko", "shinobu", "megumin", "cuddle", "cry", "hug", "kiss", "pat", "smug", "bonk", "blush", "smile", "wave", "happy", "dance"]
            
            category = "waifu"
            query_lower = query.lower()
            for cat in categories:
                if cat in query_lower:
                    category = cat
                    break
            
            results = []
            for _ in range(min(limit, 15)):
                async with self.session.get(f"{self.BASE_URL}/{category}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Anime-Moe",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [category],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class Kyoko(ArtSource):
    """Kyoko API - Anime images"""
    BASE_URL = "https://kyoko.rei.my.id/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["waifu", "neko", "husbando", "kitsune", "anime", "hug", "pat", "kiss", "slap", "punch"]
            
            endpoint = "waifu"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 15)):
                async with self.session.get(f"{self.BASE_URL}/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Kyoko",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class HmtaiSfw(ArtSource):
    """Hmtai SFW API - Anime images"""
    BASE_URL = "https://hmtai.hatsunia.cfd/sfw"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["wave", "wink", "tea", "bonk", "punch", "poke", "bully", "pat", "kiss", "kick", "blush", "feed", "smug", "hug", "cuddle", "cry", "cringe", "slap", "five", "glomp", "happy", "hold", "nom", "smile", "throw", "lick", "bite", "anime", "neko", "wallpaper"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Hmtai SFW",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class KawaiiRed(ArtSource):
    """Kawaii.red API - Kawaii anime images"""
    BASE_URL = "https://kawaii.red/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["neko", "hug", "pat", "kiss", "slap", "poke", "wave", "wink", "smile", "cry"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 15)):
                async with self.session.get(f"{self.BASE_URL}/gif/{endpoint}/token=<API_KEY>/") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("response"):
                            results.append({
                                "source": "Kawaii",
                                "url": data.get("response"),
                                "preview_url": data.get("response"),
                                "page_url": data.get("response"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("response", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class PurrBot(ArtSource):
    """PurrBot API - Anime/neko images"""
    BASE_URL = "https://purrbot.site/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["background", "bite", "blush", "comfy", "cry", "cuddle", "dance", "eevee", "feed", "fluff", "holo", "hug", "icon", "kiss", "kitsune", "lay", "lick", "neko", "okami", "pat", "poke", "pout", "senko", "shiro", "slap", "smile", "tail", "tickle"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/img/sfw/{endpoint}/img") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("link"):
                            results.append({
                                "source": "PurrBot",
                                "url": data.get("link"),
                                "preview_url": data.get("link"),
                                "page_url": data.get("link"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("link", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class NekosLife(ArtSource):
    """Nekos.life API - Classic neko images"""
    BASE_URL = "https://nekos.life/api/v2"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["neko", "waifu", "pat", "hug", "kiss", "slap", "cuddle", "smug", "baka", "tickle", "poke", "feed", "gecg", "fox_girl", "lizard", "goose", "woof", "meow", "avatar"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 20)):
                async with self.session.get(f"{self.BASE_URL}/img/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Nekos.life",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class Shiro(ArtSource):
    """Shiro API - Anime images"""
    BASE_URL = "https://shiro.gg"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["hug", "kiss", "pat", "slap", "neko", "waifu", "punch", "bite", "cry", "cuddle"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 15)):
                async with self.session.get(f"{self.BASE_URL}/api/images/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Shiro",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
            return []


class Asuna(ArtSource):
    """Asuna API - SAO-style anime images"""
    BASE_URL = "https://asuna.ga/api"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            endpoints = ["neko", "hug", "kiss", "pat", "slap", "cuddle", "cry", "smile", "wink", "wave"]
            
            endpoint = "neko"
            query_lower = query.lower()
            for ep in endpoints:
                if ep in query_lower:
                    endpoint = ep
                    break
            
            results = []
            for _ in range(min(limit, 15)):
                async with self.session.get(f"{self.BASE_URL}/{endpoint}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("url"):
                            results.append({
                                "source": "Asuna",
                                "url": data.get("url"),
                                "preview_url": data.get("url"),
                                "page_url": data.get("url"),
                                "artist": "Unknown",
                                "tags": [endpoint],
                                "rating": "s",
                                "score": 0,
                                "id": data.get("url", "").split("/")[-1].split(".")[0],
                                "width": None,
                                "height": None
                            })
            return results
        except Exception:
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
            
            art_logger.debug(f"AIBooru: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=self.headers) as resp:
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
    """TBIB (The Big ImageBoard) API - SFW mode"""
    BASE_URL = "https://tbib.org"
    
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
            
            art_logger.debug(f"TBIB: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params, headers=self.headers) as resp:
                art_logger.debug(f"TBIB: Response status {resp.status}")
                if resp.status == 200:
                    content_type = resp.headers.get('content-type', '').lower()
                    if 'application/json' not in content_type:
                        art_logger.debug(f"TBIB: Invalid content-type {content_type}, skipping")
                        return []
                    data = await resp.json()
                    results = []
                    posts = data if isinstance(data, list) else data.get("post", []) if isinstance(data, dict) else []
                    for post in posts:
                        # TBIB uses 'image' and 'directory' fields to construct URL
                        image = post.get("image", "")
                        directory = post.get("directory")
                        if image and directory is not None:
                            file_url = f"https://tbib.org/images/{directory}/{image}"
                            preview = f"https://tbib.org/thumbnails/{directory}/thumbnail_{post.get('hash', '')}.jpg"
                            if post.get("sample"):
                                preview = f"https://tbib.org/samples/{directory}/sample_{post.get('hash', '')}.jpg"
                            results.append({
                                "source": "TBIB",
                                "url": file_url,
                                "preview_url": preview,
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10] if isinstance(post.get("tags"), str) else [],
                                "rating": post.get("rating", "s"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    art_logger.debug(f"TBIB: Found {len(results)} results")
                    return results
        except Exception as e:
            art_logger.error(f"TBIB error: {e}")
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
            
            art_logger.debug(f"SankakuSafe: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts", params=params, headers=self.headers) as resp:
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
            
            art_logger.debug(f"Sankaku: Searching '{tags}' page {page}")
            async with self.session.get(f"{self.BASE_URL}/posts", params=params, headers=self.headers) as resp:
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
    """Aggregates results from multiple art sources"""
    
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
            "sankaku_safe": SankakuSafe(session),
            "xbooru_safe": XBooruSafe(session),
            "rule34_safe": Rule34Safe(session),
            "hypnohub_safe": HypnohubSafe(session),
            "booru_allthefallen": BooruAllthefallen(session),
            # === Mixed Content Sources (NSFW channel) ===
            "danbooru": Danbooru(session),
            "gelbooru": Gelbooru(session),
            "yandere": Yandere(session),
            "konachan": Konachan(session),
            "zerochan": Zerochan(session),
            "anime_pictures": AnimePictures(session),
            "sankaku": Sankaku(session),
            # === NSFW Only Sources ===
            "rule34": Rule34(session),
            "e621": E621(session),
            "realbooru": Realbooru(session),
        }
    
    def get_available_sources(self, nsfw: bool = False) -> Dict[str, dict]:
        """Get available sources based on NSFW setting"""
        available = {}
        for key, meta in ART_SOURCES.items():
            if meta["nsfw_only"] and not nsfw:
                continue
            available[key] = meta
        return available
    
    async def search_all(
        self, 
        query: str, 
        limit: int = 50, 
        nsfw: bool = False,
        selected_sources: Set[str] = None,
        page: int = 0,
        aggressive_load: bool = True,
        max_pages_per_source: int = 10
    ) -> List[Dict]:
        """Search selected sources and aggregate results
        
        Args:
            query: Search query
            limit: Maximum results to return (not enforced if aggressive_load=True)
            nsfw: Whether NSFW content is allowed
            selected_sources: Set of source keys to search
            page: Starting page number
            aggressive_load: If True, fetch multiple pages from all sources simultaneously
            max_pages_per_source: Maximum pages to fetch per source when aggressive_load=True
        """
        results = []
        
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
        
        # Aggressive loading: fetch multiple pages from all sources at once
        if aggressive_load:
            tasks = []
            per_source_limit = 50  # Fetch 50 results per page per source
            
            # Create tasks for multiple pages from each source
            for name in active_sources:
                source = self.sources.get(name)
                if source:
                    # Fetch multiple pages simultaneously
                    for page_num in range(page, page + max_pages_per_source):
                        tasks.append(source.search(query, limit=per_source_limit, nsfw=nsfw, page=page_num))
            
            # Execute all tasks concurrently
            source_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect all results
            for res in source_results:
                if isinstance(res, list):
                    results.extend(res)
        else:
            # Standard loading: one page per source
            tasks = []
            per_source_limit = max(10, limit // len(active_sources)) if active_sources else 10
            
            for name in active_sources:
                source = self.sources.get(name)
                if source:
                    tasks.append(source.search(query, limit=per_source_limit, nsfw=nsfw, page=page))
            
            source_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for res in source_results:
                if isinstance(res, list):
                    results.extend(res)
        
        # Remove duplicates based on source + id
        seen = set()
        unique_results = []
        for r in results:
            key = (r.get("source"), r.get("id"))
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
        
        # Sort by score (handle None values)
        unique_results.sort(key=lambda x: x.get("score") or 0, reverse=True)
        
        return unique_results
    
    async def search_source(
        self, 
        source_name: str, 
        query: str, 
        limit: int = 50, 
        nsfw: bool = False,
        page: int = 0
    ) -> List[Dict]:
        """Search a specific source"""
        source = self.sources.get(source_name.lower())
        if not source:
            return []
        return await source.search(query, limit=limit, nsfw=nsfw, page=page)
