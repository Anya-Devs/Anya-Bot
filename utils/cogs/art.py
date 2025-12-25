import aiohttp
import discord
import asyncio
from typing import Optional, List, Dict, Set
import random


# All available art sources with metadata
# nsfw_only: True = NSFW-only source, False = can contain mixed content
# requires_nsfw_channel: True = must be used in NSFW channel, False = safe for all channels
ART_SOURCES = {
    "safebooru": {"name": "Safebooru", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": False, "description": "SFW anime art only - Guaranteed safe"},
    "konachan": {"name": "Konachan", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Anime wallpapers - Mostly safe"},
    "nekos_best": {"name": "Nekos.best", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": False, "description": "Neko/anime images - Mostly safe"},
    "danbooru": {"name": "Danbooru", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime art database - Mixed content (NSFW channel only)"},
    "gelbooru": {"name": "Gelbooru", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime/manga art - Mixed content (NSFW channel only)"},
    "yandere": {"name": "Yande.re", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": True, "description": "High quality anime art - Mixed content (NSFW channel only)"},
    "zerochan": {"name": "Zerochan", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime images - Mixed content (NSFW channel only)"},
    "anime_pictures": {"name": "Anime-Pictures", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Anime artwork - Mixed content (NSFW channel only)"},
    "waifu_im": {"name": "Waifu.im", "emoji": "🎨", "nsfw_only": False, "requires_nsfw_channel": True, "description": "Waifu images - Mixed content (NSFW channel only)"},
    "rule34": {"name": "Rule34", "emoji": "🎨", "nsfw_only": True, "requires_nsfw_channel": True, "description": "Adult content - NSFW only"},
    "e621": {"name": "e621", "emoji": "🎨", "nsfw_only": True, "requires_nsfw_channel": True, "description": "Furry art - NSFW only"},
    "realbooru": {"name": "Realbooru", "emoji": "🎨", "nsfw_only": True, "requires_nsfw_channel": True, "description": "Real photos - NSFW only"},
}


class ArtSource:
    """Base class for art sources"""
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
    
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
            
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params) as resp:
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
                    return results
        except Exception:
            return []
        return []


class Gelbooru(ArtSource):
    """Gelbooru API - Anime/manga art"""
    BASE_URL = "https://gelbooru.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:safe"
            
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "tags": tags,
                "limit": min(limit, 100),
                "pid": page
            }
            
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if isinstance(data, dict) and "post" in data:
                        results = []
                        for post in data["post"]:
                            results.append({
                                "source": "Gelbooru",
                                "url": post.get("file_url"),
                                "preview_url": post.get("preview_url") or post.get("file_url"),
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": post.get("owner") or "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": post.get("rating", "s"),
                                "score": post.get("score") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                        return results
        except Exception:
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
            
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    if isinstance(data, list):
                        for post in data:
                            file_url = post.get("file_url", "")
                            if file_url:
                                if file_url.startswith('//'):
                                    file_url = f"https:{file_url}"
                                preview = post.get("sample_url") or post.get("preview_url") or file_url
                                if preview.startswith('//'):
                                    preview = f"https:{preview}"
                                results.append({
                                    "source": "Safebooru",
                                    "url": file_url,
                                    "preview_url": preview,
                                    "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                    "artist": post.get("owner") or "Unknown",
                                    "tags": post.get("tags", "").split()[:10],
                                    "rating": "s",
                                    "score": post.get("score") or 0,
                                    "id": post.get("id"),
                                    "width": post.get("width"),
                                    "height": post.get("height")
                                })
                    return results
        except Exception:
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
            
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params) as resp:
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
                    return results
        except Exception:
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
            
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        if post.get("file_url"):
                            results.append({
                                "source": "Yande.re",
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
                    return results
        except Exception:
            return []
        return []


class Rule34(ArtSource):
    """Rule34 API - Adult content (NSFW only)"""
    BASE_URL = "https://api.rule34.xxx"
    
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
            
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    if isinstance(data, list):
                        for post in data:
                            if post.get("file_url"):
                                results.append({
                                    "source": "Rule34",
                                    "url": post.get("file_url"),
                                    "preview_url": post.get("preview_url") or post.get("sample_url") or post.get("file_url"),
                                    "page_url": f"https://rule34.xxx/index.php?page=post&s=view&id={post.get('id')}",
                                    "artist": post.get("owner") or "Unknown",
                                    "tags": post.get("tags", "").split()[:10],
                                    "rating": "e",
                                    "score": post.get("score") or 0,
                                    "id": post.get("id"),
                                    "width": post.get("width"),
                                    "height": post.get("height")
                                })
                    return results
        except Exception:
            return []
        return []


class Zerochan(ArtSource):
    """Zerochan API - Anime images"""
    BASE_URL = "https://www.zerochan.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "+")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            params = {
                "json": 1,
                "l": min(limit, 50),
                "p": page + 1
            }
            
            async with self.session.get(f"{self.BASE_URL}/{tags}", params=params, headers=headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    items = data.get("items", []) if isinstance(data, dict) else data
                    for post in items:
                        if isinstance(post, dict):
                            results.append({
                                "source": "Zerochan",
                                "url": post.get("full") or post.get("large") or post.get("medium"),
                                "preview_url": post.get("thumbnail") or post.get("medium"),
                                "page_url": f"{self.BASE_URL}/{post.get('id')}",
                                "artist": post.get("source") or "Unknown",
                                "tags": post.get("tags", [])[:10] if isinstance(post.get("tags"), list) else [],
                                "rating": "s",
                                "score": post.get("fav") or 0,
                                "id": post.get("id"),
                                "width": post.get("width"),
                                "height": post.get("height")
                            })
                    return results
        except Exception:
            return []
        return []


class AnimePictures(ArtSource):
    """Anime-Pictures.net API"""
    BASE_URL = "https://anime-pictures.net"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False, page: int = 0) -> List[Dict]:
        try:
            tags = query.replace(" ", "+")
            erotic_filter = "" if nsfw else "&erotic=0"
            
            async with self.session.get(
                f"{self.BASE_URL}/api/v3/posts?search_tag={tags}&page={page}&lim={min(limit, 80)}{erotic_filter}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    posts = data.get("posts", []) if isinstance(data, dict) else []
                    for post in posts:
                        results.append({
                            "source": "Anime-Pictures",
                            "url": f"{self.BASE_URL}/pictures/download_image/{post.get('id')}",
                            "preview_url": f"{self.BASE_URL}/previews/{post.get('md5')[:2]}/{post.get('md5')}_sp.jpg" if post.get('md5') else None,
                            "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                            "artist": "Unknown",
                            "tags": [],
                            "rating": "q" if post.get("erotics") else "s",
                            "score": post.get("score_number") or 0,
                            "id": post.get("id"),
                            "width": post.get("width"),
                            "height": post.get("height")
                        })
                    return results
        except Exception:
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
            headers = {
                "User-Agent": "AnyaBot/1.0 (Discord Bot)"
            }
            
            params = {
                "tags": tags,
                "limit": min(limit, 75),
                "page": page + 1
            }
            
            async with self.session.get(f"{self.BASE_URL}/posts.json", params=params, headers=headers) as resp:
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
                    return results
        except Exception:
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
            
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    if isinstance(data, list):
                        for post in data:
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
                    return results
        except Exception:
            return []
        return []


class ArtAggregator:
    """Aggregates results from multiple art sources"""
    
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        self.sources = {
            "danbooru": Danbooru(session),
            "gelbooru": Gelbooru(session),
            "safebooru": Safebooru(session),
            "konachan": Konachan(session),
            "yandere": Yandere(session),
            "rule34": Rule34(session),
            "zerochan": Zerochan(session),
            "anime_pictures": AnimePictures(session),
            "waifu_im": WaifuIm(session),
            "nekos_best": NekosBest(session),
            "e621": E621(session),
            "realbooru": Realbooru(session)
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
        max_pages_per_source: int = 5
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
