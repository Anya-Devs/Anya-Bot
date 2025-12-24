"""
Search & API Utilities - External API integrations for search commands
Includes: Google, YouTube, Art Gallery, Translation, Weather, Dictionary, Wikipedia, etc.
"""

import os
import aiohttp
import asyncio
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from imports.discord_imports import *
from data.local.const import primary_color


class SearchAPI:
    """Base class for API requests"""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        return self.session
    
    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()


class GoogleSearch(SearchAPI):
    """Google Custom Search API wrapper"""
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.cx = os.getenv("GOOGLE_CX")  # Custom Search Engine ID
    
    async def search(self, query: str, num: int = 5, search_type: str = None) -> List[Dict]:
        """Perform a Google search"""
        if not self.api_key or not self.cx:
            return []
        
        session = await self.get_session()
        params = {
            "key": self.api_key,
            "cx": self.cx,
            "q": query,
            "num": min(num, 10)
        }
        if search_type:
            params["searchType"] = search_type
        
        try:
            async with session.get("https://www.googleapis.com/customsearch/v1", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
        except Exception:
            pass
        return []
    
    async def image_search(self, query: str, num: int = 5) -> List[Dict]:
        """Search for images"""
        return await self.search(query, num, search_type="image")


class YouTubeSearch(SearchAPI):
    """YouTube Data API wrapper"""
    
    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("YOUTUBE_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    async def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search YouTube videos"""
        if not self.api_key:
            # Fallback to scraping method
            return await self.search_fallback(query, max_results)
        
        session = await self.get_session()
        params = {
            "key": self.api_key,
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": min(max_results, 25)
        }
        
        try:
            async with session.get("https://www.googleapis.com/youtube/v3/search", params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
        except Exception:
            pass
        return await self.search_fallback(query, max_results)
    
    async def search_fallback(self, query: str, max_results: int = 5) -> List[Dict]:
        """Fallback YouTube search without API"""
        session = await self.get_session()
        encoded = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={encoded}"
        
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    # Extract video IDs from page
                    import re
                    video_ids = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', text)
                    unique_ids = list(dict.fromkeys(video_ids))[:max_results]
                    return [{"id": {"videoId": vid}, "snippet": {"title": f"Video {i+1}"}} for i, vid in enumerate(unique_ids)]
        except Exception:
            pass
        return []


class TranslationAPI(SearchAPI):
    """Translation API wrapper using LibreTranslate or Google"""
    
    LANGUAGES = {
        "en": "English", "es": "Spanish", "fr": "French", "de": "German",
        "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese",
        "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "hi": "Hindi",
        "nl": "Dutch", "pl": "Polish", "tr": "Turkish", "vi": "Vietnamese"
    }
    
    async def translate(self, text: str, target: str = "en", source: str = "auto") -> Dict:
        """Translate text"""
        session = await self.get_session()
        
        # Try LibreTranslate first (free)
        try:
            async with session.post(
                "https://libretranslate.com/translate",
                json={"q": text, "source": source, "target": target, "format": "text"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "translated": data.get("translatedText", text),
                        "source_lang": source,
                        "target_lang": target,
                        "success": True
                    }
        except Exception:
            pass
        
        # Fallback to MyMemory (free, limited)
        try:
            langpair = f"{source}|{target}" if source != "auto" else f"en|{target}"
            async with session.get(
                f"https://api.mymemory.translated.net/get",
                params={"q": text, "langpair": langpair}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "translated": data.get("responseData", {}).get("translatedText", text),
                        "source_lang": source,
                        "target_lang": target,
                        "success": True
                    }
        except Exception:
            pass
        
        return {"translated": text, "source_lang": source, "target_lang": target, "success": False}
    
    async def detect_language(self, text: str) -> str:
        """Detect language of text"""
        session = await self.get_session()
        
        try:
            async with session.post(
                "https://libretranslate.com/detect",
                json={"q": text}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        return data[0].get("language", "unknown")
        except Exception:
            pass
        return "unknown"


class WeatherAPI(SearchAPI):
    """Weather API wrapper using Open-Meteo (free)"""
    
    async def get_weather(self, location: str) -> Optional[Dict]:
        """Get weather for a location"""
        session = await self.get_session()
        
        # First, geocode the location
        try:
            async with session.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": location, "count": 1}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = data.get("results", [])
                    if not results:
                        return None
                    
                    loc = results[0]
                    lat, lon = loc["latitude"], loc["longitude"]
                    name = f"{loc.get('name', location)}, {loc.get('country', '')}"
        except Exception:
            return None
        
        # Get weather data
        try:
            async with session.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "temperature_2m_max,temperature_2m_min,weather_code",
                    "timezone": "auto"
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    current = data.get("current", {})
                    daily = data.get("daily", {})
                    
                    return {
                        "location": name,
                        "temperature": current.get("temperature_2m"),
                        "humidity": current.get("relative_humidity_2m"),
                        "wind_speed": current.get("wind_speed_10m"),
                        "weather_code": current.get("weather_code"),
                        "high": daily.get("temperature_2m_max", [None])[0],
                        "low": daily.get("temperature_2m_min", [None])[0]
                    }
        except Exception:
            pass
        return None
    
    @staticmethod
    def get_weather_emoji(code: int) -> str:
        """Get emoji for weather code"""
        if code is None:
            return "❓"
        if code == 0:
            return "☀️"
        elif code in [1, 2, 3]:
            return "⛅"
        elif code in [45, 48]:
            return "🌫️"
        elif code in [51, 53, 55, 56, 57]:
            return "🌧️"
        elif code in [61, 63, 65, 66, 67]:
            return "🌧️"
        elif code in [71, 73, 75, 77]:
            return "🌨️"
        elif code in [80, 81, 82]:
            return "🌧️"
        elif code in [85, 86]:
            return "🌨️"
        elif code in [95, 96, 99]:
            return "⛈️"
        return "🌤️"


class DictionaryAPI(SearchAPI):
    """Dictionary API wrapper"""
    
    async def define(self, word: str) -> Optional[Dict]:
        """Get definition of a word"""
        session = await self.get_session()
        
        try:
            async with session.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data:
                        entry = data[0]
                        meanings = entry.get("meanings", [])
                        
                        definitions = []
                        for meaning in meanings[:3]:
                            part = meaning.get("partOfSpeech", "")
                            defs = meaning.get("definitions", [])[:2]
                            for d in defs:
                                definitions.append({
                                    "part_of_speech": part,
                                    "definition": d.get("definition", ""),
                                    "example": d.get("example", "")
                                })
                        
                        return {
                            "word": entry.get("word", word),
                            "phonetic": entry.get("phonetic", ""),
                            "definitions": definitions,
                            "audio": entry.get("phonetics", [{}])[0].get("audio", "")
                        }
        except Exception:
            pass
        return None


class WikipediaAPI(SearchAPI):
    """Wikipedia API wrapper"""
    
    async def search(self, query: str) -> Optional[Dict]:
        """Search Wikipedia"""
        session = await self.get_session()
        
        try:
            # Search for article
            async with session.get(
                "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(query)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "title": data.get("title", query),
                        "extract": data.get("extract", "No summary available."),
                        "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                        "thumbnail": data.get("thumbnail", {}).get("source", "")
                    }
        except Exception:
            pass
        return None


class ArtGalleryAPI(SearchAPI):
    """Art gallery search using multiple museum APIs"""
    
    async def search_met(self, query: str, limit: int = 5) -> List[Dict]:
        """Search Metropolitan Museum of Art"""
        session = await self.get_session()
        
        try:
            # Search for objects
            async with session.get(
                "https://collectionapi.metmuseum.org/public/collection/v1/search",
                params={"q": query, "hasImages": True}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    object_ids = data.get("objectIDs", [])[:limit]
                    
                    results = []
                    for obj_id in object_ids:
                        async with session.get(
                            f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}"
                        ) as obj_resp:
                            if obj_resp.status == 200:
                                obj_data = await obj_resp.json()
                                results.append({
                                    "title": obj_data.get("title", "Untitled"),
                                    "artist": obj_data.get("artistDisplayName", "Unknown Artist"),
                                    "date": obj_data.get("objectDate", "Unknown Date"),
                                    "medium": obj_data.get("medium", ""),
                                    "image": obj_data.get("primaryImage", ""),
                                    "url": obj_data.get("objectURL", ""),
                                    "museum": "Metropolitan Museum of Art"
                                })
                    return results
        except Exception:
            pass
        return []
    
    async def search_aic(self, query: str, limit: int = 5) -> List[Dict]:
        """Search Art Institute of Chicago"""
        session = await self.get_session()
        
        try:
            async with session.get(
                "https://api.artic.edu/api/v1/artworks/search",
                params={"q": query, "limit": limit, "fields": "id,title,artist_display,date_display,image_id,medium_display"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    config = data.get("config", {})
                    iiif_url = config.get("iiif_url", "https://www.artic.edu/iiif/2")
                    
                    results = []
                    for item in data.get("data", []):
                        image_id = item.get("image_id")
                        image_url = f"{iiif_url}/{image_id}/full/843,/0/default.jpg" if image_id else ""
                        
                        results.append({
                            "title": item.get("title", "Untitled"),
                            "artist": item.get("artist_display", "Unknown Artist"),
                            "date": item.get("date_display", "Unknown Date"),
                            "medium": item.get("medium_display", ""),
                            "image": image_url,
                            "url": f"https://www.artic.edu/artworks/{item.get('id')}",
                            "museum": "Art Institute of Chicago"
                        })
                    return results
        except Exception:
            pass
        return []
    
    async def search(self, query: str, limit: int = 5) -> List[Dict]:
        """Search multiple art galleries"""
        met_results = await self.search_met(query, limit)
        aic_results = await self.search_aic(query, limit)
        
        # Interleave results
        results = []
        for i in range(max(len(met_results), len(aic_results))):
            if i < len(met_results):
                results.append(met_results[i])
            if i < len(aic_results):
                results.append(aic_results[i])
        
        return results[:limit * 2]


class UrbanDictionaryAPI(SearchAPI):
    """Urban Dictionary API wrapper"""
    
    async def define(self, term: str) -> Optional[Dict]:
        """Get Urban Dictionary definition"""
        session = await self.get_session()
        
        try:
            async with session.get(
                "https://api.urbandictionary.com/v0/define",
                params={"term": term}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    definitions = data.get("list", [])
                    if definitions:
                        top = definitions[0]
                        return {
                            "word": top.get("word", term),
                            "definition": top.get("definition", "").replace("[", "").replace("]", ""),
                            "example": top.get("example", "").replace("[", "").replace("]", ""),
                            "thumbs_up": top.get("thumbs_up", 0),
                            "thumbs_down": top.get("thumbs_down", 0),
                            "author": top.get("author", "Anonymous"),
                            "url": top.get("permalink", "")
                        }
        except Exception:
            pass
        return None


class SearchViews:
    """Interactive views for search results"""
    
    class SearchResultsPaginator(discord.ui.View):
        """Paginated search results view"""
        
        def __init__(self, results: List[Dict], author: discord.Member, title: str, per_page: int = 1):
            super().__init__(timeout=120)
            self.results = results
            self.author = author
            self.title = title
            self.per_page = per_page
            self.page = 0
            self.max_pages = max(1, (len(results) + per_page - 1) // per_page)
            self.update_buttons()
        
        def update_buttons(self):
            self.prev_btn.disabled = self.page <= 0
            self.next_btn.disabled = self.page >= self.max_pages - 1
        
        def build_embed(self) -> discord.Embed:
            """Override in subclass"""
            embed = discord.Embed(title=self.title, color=primary_color())
            embed.set_footer(text=f"Page {self.page + 1}/{self.max_pages}")
            return embed
        
        @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
        async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                return await interaction.response.send_message("Not your search!", ephemeral=True)
            self.page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
        
        @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
        async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            if interaction.user != self.author:
                return await interaction.response.send_message("Not your search!", ephemeral=True)
            self.page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    class ArtGalleryView(SearchResultsPaginator):
        """Art gallery results view"""
        
        def build_embed(self) -> discord.Embed:
            if not self.results:
                return discord.Embed(title="No Results", description="No artwork found.", color=discord.Color.orange())
            
            art = self.results[self.page]
            embed = discord.Embed(
                title=art.get("title", "Untitled"),
                url=art.get("url", ""),
                color=primary_color(),
                timestamp=datetime.now(timezone.utc)
            )
            
            embed.add_field(name="Artist", value=art.get("artist", "Unknown"), inline=True)
            embed.add_field(name="Date", value=art.get("date", "Unknown"), inline=True)
            embed.add_field(name="Museum", value=art.get("museum", "Unknown"), inline=True)
            
            if art.get("medium"):
                embed.add_field(name="Medium", value=art.get("medium")[:100], inline=False)
            
            if art.get("image"):
                embed.set_image(url=art.get("image"))
            
            embed.set_footer(text=f"Result {self.page + 1}/{len(self.results)}")
            return embed
    
    class VideoSearchView(SearchResultsPaginator):
        """Video search results view"""
        
        def build_embed(self) -> discord.Embed:
            if not self.results:
                return discord.Embed(title="No Results", description="No videos found.", color=discord.Color.orange())
            
            video = self.results[self.page]
            video_id = video.get("id", {}).get("videoId", "")
            snippet = video.get("snippet", {})
            
            embed = discord.Embed(
                title=snippet.get("title", "Unknown Title"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                description=snippet.get("description", "")[:200],
                color=discord.Color.red(),
                timestamp=datetime.now(timezone.utc)
            )
            
            if snippet.get("thumbnails", {}).get("high", {}).get("url"):
                embed.set_image(url=snippet["thumbnails"]["high"]["url"])
            
            embed.add_field(name="Channel", value=snippet.get("channelTitle", "Unknown"), inline=True)
            embed.set_footer(text=f"Result {self.page + 1}/{len(self.results)} • YouTube")
            return embed
