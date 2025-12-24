import aiohttp
import discord
from typing import Optional, List, Dict
import random


class ArtSource:
    """Base class for art sources"""
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
        raise NotImplementedError


class Danbooru(ArtSource):
    """Danbooru API - Anime art"""
    BASE_URL = "https://danbooru.donmai.us"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:general"
            
            params = {
                "tags": tags,
                "limit": min(limit, 20)
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
                                "page_url": f"{self.BASE_URL}/posts/{post.get('id')}",
                                "artist": post.get("tag_string_artist", "Unknown"),
                                "tags": post.get("tag_string_general", "").split()[:10],
                                "rating": post.get("rating", "g"),
                                "score": post.get("score", 0),
                                "id": post.get("id")
                            })
                    return results
        except Exception:
            return []
        return []


class Gelbooru(ArtSource):
    """Gelbooru API - Anime/manga art"""
    BASE_URL = "https://gelbooru.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
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
                "limit": min(limit, 20)
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
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": post.get("rating", "s"),
                                "score": post.get("score", 0),
                                "id": post.get("id")
                            })
                        return results
        except Exception:
            return []
        return []


class Safebooru(ArtSource):
    """Safebooru API - SFW anime art only"""
    BASE_URL = "https://safebooru.org"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            
            params = {
                "page": "dapi",
                "s": "post",
                "q": "index",
                "json": 1,
                "tags": tags,
                "limit": min(limit, 20)
            }
            
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        if post.get("file_url"):
                            results.append({
                                "source": "Safebooru",
                                "url": f"https:{post.get('file_url')}" if post.get('file_url').startswith('//') else post.get('file_url'),
                                "page_url": f"{self.BASE_URL}/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": "s",
                                "score": post.get("score", 0),
                                "id": post.get("id")
                            })
                    return results
        except Exception:
            return []
        return []


class Konachan(ArtSource):
    """Konachan API - High quality anime wallpapers"""
    BASE_URL = "https://konachan.com"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:safe"
            
            params = {
                "tags": tags,
                "limit": min(limit, 20)
            }
            
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        results.append({
                            "source": "Konachan",
                            "url": post.get("file_url"),
                            "page_url": f"{self.BASE_URL}/post/show/{post.get('id')}",
                            "artist": post.get("author", "Unknown"),
                            "tags": post.get("tags", "").split()[:10],
                            "rating": post.get("rating", "s"),
                            "score": post.get("score", 0),
                            "id": post.get("id")
                        })
                    return results
        except Exception:
            return []
        return []


class Yandere(ArtSource):
    """Yande.re API - High quality anime art"""
    BASE_URL = "https://yande.re"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
        try:
            tags = query.replace(" ", "_")
            if not nsfw:
                tags += " rating:safe"
            
            params = {
                "tags": tags,
                "limit": min(limit, 20)
            }
            
            async with self.session.get(f"{self.BASE_URL}/post.json", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        results.append({
                            "source": "Yande.re",
                            "url": post.get("file_url"),
                            "page_url": f"{self.BASE_URL}/post/show/{post.get('id')}",
                            "artist": post.get("author", "Unknown"),
                            "tags": post.get("tags", "").split()[:10],
                            "rating": post.get("rating", "s"),
                            "score": post.get("score", 0),
                            "id": post.get("id")
                        })
                    return results
        except Exception:
            return []
        return []


class Rule34(ArtSource):
    """Rule34 API - Adult content (NSFW only)"""
    BASE_URL = "https://api.rule34.xxx"
    
    async def search(self, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
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
                "limit": min(limit, 20)
            }
            
            async with self.session.get(f"{self.BASE_URL}/index.php", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = []
                    for post in data:
                        if post.get("file_url"):
                            results.append({
                                "source": "Rule34",
                                "url": post.get("file_url"),
                                "page_url": f"https://rule34.xxx/index.php?page=post&s=view&id={post.get('id')}",
                                "artist": "Unknown",
                                "tags": post.get("tags", "").split()[:10],
                                "rating": "e",
                                "score": post.get("score", 0),
                                "id": post.get("id")
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
            "rule34": Rule34(session)
        }
    
    async def search_all(self, query: str, limit: int = 20, nsfw: bool = False) -> List[Dict]:
        """Search all sources and aggregate results"""
        results = []
        
        # Search all sources concurrently
        import asyncio
        tasks = []
        for name, source in self.sources.items():
            if name == "rule34" and not nsfw:
                continue
            tasks.append(source.search(query, limit=5, nsfw=nsfw))
        
        source_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for res in source_results:
            if isinstance(res, list):
                results.extend(res)
        
        # Sort by score
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return results[:limit]
    
    async def search_source(self, source_name: str, query: str, limit: int = 10, nsfw: bool = False) -> List[Dict]:
        """Search a specific source"""
        source = self.sources.get(source_name.lower())
        if not source:
            return []
        return await source.search(query, limit=limit, nsfw=nsfw)
