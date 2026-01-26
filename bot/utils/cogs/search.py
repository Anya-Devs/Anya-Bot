"""
Search & API Utilities - External API integrations for search commands
Includes: Google, YouTube, Art Gallery, Translation, Weather, Dictionary, Wikipedia, etc.
"""

import os
import aiohttp
import asyncio
import urllib.parse
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from imports.discord_imports import *
from data.local.const import primary_color
from bot.utils.cogs.art import ART_SOURCES, ArtAggregator


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
    """Google Search using web scraping (no API key required)"""
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1"
    }
    
    def __init__(self):
        super().__init__()
    
    async def search(self, query: str, num: int = 10, start: int = 0, safe: bool = True) -> List[Dict]:
        """Scrape Google web search results
        
        Args:
            query: Search query
            num: Number of results
            start: Start offset for pagination
            safe: Enable SafeSearch (default True)
        """
        session = await self.get_session()
        encoded_query = urllib.parse.quote(query)
        # safe=active enables SafeSearch, safe=off disables it
        safe_param = "active" if safe else "off"
        url = f"https://www.google.com/search?q={encoded_query}&num={num}&start={start}&safe={safe_param}"
        
        try:
            async with session.get(url, headers=self.HEADERS) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return self._parse_web_results(text)
        except Exception as e:
            print(f"Google search error: {e}")
        return []
    
    def _parse_web_results(self, html: str) -> List[Dict]:
        """Parse web search results from HTML - simplified and more reliable"""
        import re
        results = []
        
        # Split by result containers - Google wraps each result in specific divs
        # Look for the pattern: href="/url?q=..." which is Google's redirect link
        
        # Pattern 1: Find all /url?q= patterns (Google's main result links)
        # This captures the actual destination URL
        url_pattern = r'/url\?q=([^&]+)&'
        urls = re.findall(url_pattern, html)
        
        # Pattern 2: Find h3 tags which contain titles
        # h3 tags are used for search result titles
        h3_pattern = r'<h3[^>]*>([^<]+)</h3>'
        titles = re.findall(h3_pattern, html)
        
        # Pattern 3: Find description text in divs/spans
        # Look for text that appears after titles (usually in divs with specific classes)
        # This is trickier - we'll extract text between certain markers
        desc_pattern = r'<span[^>]*>([^<]{30,400})</span>'
        descriptions = re.findall(desc_pattern, html)
        
        # Clean and deduplicate URLs
        seen_urls = set()
        clean_urls = []
        
        for url in urls:
            try:
                # URL decode the URL
                decoded = urllib.parse.unquote(url)
                
                # Skip Google's own domains and duplicates
                if any(skip in decoded.lower() for skip in ['google.com', 'gstatic.com', 'googleusercontent.com']):
                    continue
                
                if decoded not in seen_urls and decoded.startswith('http'):
                    seen_urls.add(decoded)
                    clean_urls.append(decoded)
                    
                    if len(clean_urls) >= 10:
                        break
            except:
                continue
        
        # If we didn't get URLs from the redirect pattern, try direct href extraction
        if len(clean_urls) < 3:
            href_pattern = r'href="(https?://[^"]+)"'
            href_urls = re.findall(href_pattern, html)
            
            for url in href_urls:
                if any(skip in url.lower() for skip in ['google.com', 'gstatic.com', 'javascript:', '#']):
                    continue
                    
                if url not in seen_urls:
                    seen_urls.add(url)
                    clean_urls.append(url)
                    
                    if len(clean_urls) >= 10:
                        break
        
        # Clean titles - remove HTML tags
        clean_titles = []
        for title in titles:
            clean_title = re.sub(r'<[^>]+>', '', title).strip()
            if clean_title and len(clean_title) > 3:
                clean_titles.append(clean_title)
        
        # Clean descriptions - remove HTML tags and filter
        clean_descs = []
        for desc in descriptions:
            clean_desc = re.sub(r'<[^>]+>', '', desc).strip()
            # Filter out UI text and very short descriptions
            if clean_desc and len(clean_desc) > 30 and not clean_desc.startswith('http'):
                clean_descs.append(clean_desc)
        
        # Build results by combining URLs, titles, and descriptions
        for i, url in enumerate(clean_urls):
            title = clean_titles[i] if i < len(clean_titles) else self._extract_title_from_url(url)
            snippet = clean_descs[i] if i < len(clean_descs) else "No description available"
            
            if title and url:
                results.append({
                    "title": title[:100],
                    "link": url,
                    "snippet": snippet[:250]
                })
        
        return results
    
    def _extract_title_from_url(self, url: str) -> str:
        """Extract a readable title from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            # Use domain + path for title
            domain = parsed.netloc.replace('www.', '')
            path = parsed.path.strip('/').split('/')[-1] if parsed.path.strip('/') else ''
            if path:
                path = path.replace('-', ' ').replace('_', ' ').replace('.html', '').replace('.php', '')
                return f"{path.title()} - {domain}"[:80]
            return domain[:60]
        except:
            return "Web Result"
    
    async def image_search(self, query: str, num: int = 20, start: int = 0, safe: bool = True) -> List[Dict]:
        """Scrape Google Images search results
        
        Args:
            query: Search query
            num: Number of results
            start: Start offset
            safe: Enable SafeSearch (default True)
        """
        session = await self.get_session()
        encoded_query = urllib.parse.quote(query)
        safe_param = "active" if safe else "off"
        url = f"https://www.google.com/search?q={encoded_query}&tbm=isch&start={start}&safe={safe_param}"
        
        try:
            async with session.get(url, headers=self.HEADERS) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return self._parse_image_results(text, num)
        except Exception as e:
            print(f"Image search error: {e}")
        return []
    
    def _parse_image_results(self, html: str, limit: int = 20) -> List[Dict]:
        """Parse image search results from HTML"""
        import re
        import json
        results = []
        
        # Google Images embeds image data in JSON within the page
        # Look for image URLs in various patterns
        
        # Pattern 1: Direct image URLs in data attributes
        img_pattern = r'"(https?://[^"]+\.(?:jpg|jpeg|png|gif|webp)[^"]*)"'
        
        # Pattern 2: Thumbnail URLs
        thumb_pattern = r'data:image/[^"]+|https?://encrypted-tbn[^"]+|https?://[^"]+\.googleusercontent\.com[^"]+'
        
        # Find all potential image URLs
        all_urls = re.findall(img_pattern, html, re.IGNORECASE)
        
        seen = set()
        for url in all_urls:
            # Skip Google's own assets and tiny images
            if any(skip in url.lower() for skip in ['gstatic.com', 'google.com/images', 'googlelogo', 'favicon', 'icon', 'logo', 'sprite', 'button']):
                continue
            if url in seen:
                continue
            if len(url) < 30:  # Skip very short URLs (likely not real images)
                continue
                
            seen.add(url)
            
            # Try to extract source page URL
            source_url = ""
            
            results.append({
                "link": url,
                "thumbnail": url,
                "source": source_url,
                "title": f"Image {len(results) + 1}"
            })
            
            if len(results) >= limit:
                break
        
        # Fallback: Try to find images in JSON data blocks
        if len(results) < 5:
            json_pattern = r'\["(https?://[^"]+)",\d+,\d+\]'
            json_urls = re.findall(json_pattern, html)
            for url in json_urls:
                if url not in seen and not any(skip in url.lower() for skip in ['gstatic', 'google.com', 'favicon']):
                    seen.add(url)
                    results.append({
                        "link": url,
                        "thumbnail": url,
                        "source": "",
                        "title": f"Image {len(results) + 1}"
                    })
                    if len(results) >= limit:
                        break
        
        return results
    
    async def video_search(self, query: str, num: int = 10, start: int = 0, safe: bool = True) -> List[Dict]:
        """Scrape Google Videos search results
        
        Args:
            query: Search query
            num: Number of results
            start: Start offset
            safe: Enable SafeSearch (default True)
        """
        session = await self.get_session()
        encoded_query = urllib.parse.quote(query)
        safe_param = "active" if safe else "off"
        url = f"https://www.google.com/search?q={encoded_query}&tbm=vid&start={start}&safe={safe_param}"
        
        try:
            async with session.get(url, headers=self.HEADERS) as resp:
                if resp.status == 200:
                    text = await resp.text()
                    return self._parse_video_results(text, num)
        except Exception as e:
            print(f"Video search error: {e}")
        return []
    
    def _parse_video_results(self, html: str, limit: int = 10) -> List[Dict]:
        """Parse video search results from HTML"""
        import re
        results = []
        
        # Find YouTube video IDs
        yt_pattern = r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})'
        video_ids = re.findall(yt_pattern, html)
        
        # Also look for other video platforms
        vimeo_pattern = r'vimeo\.com/(\d+)'
        vimeo_ids = re.findall(vimeo_pattern, html)
        
        seen = set()
        
        # Add YouTube videos
        for vid_id in video_ids:
            if vid_id in seen:
                continue
            seen.add(vid_id)
            
            results.append({
                "platform": "youtube",
                "video_id": vid_id,
                "url": f"https://www.youtube.com/watch?v={vid_id}",
                "thumbnail": f"https://img.youtube.com/vi/{vid_id}/hqdefault.jpg",
                "title": f"YouTube Video",
                "embed_url": f"https://www.youtube.com/embed/{vid_id}"
            })
            
            if len(results) >= limit:
                break
        
        # Add Vimeo videos
        for vid_id in vimeo_ids:
            if vid_id in seen or len(results) >= limit:
                continue
            seen.add(vid_id)
            
            results.append({
                "platform": "vimeo",
                "video_id": vid_id,
                "url": f"https://vimeo.com/{vid_id}",
                "thumbnail": "",
                "title": f"Vimeo Video",
                "embed_url": f"https://player.vimeo.com/video/{vid_id}"
            })
        
        return results


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









# ═══════════════════════════════════════════════════════════════
# CONTENT POLICY - Prohibited tags that violate Discord TOS
# ═══════════════════════════════════════════════════════════════

PROHIBITED_TAGS = {
    # CSAM / Minor sexualization
    "loli", "lolicon", "shota", "shotacon", "toddlercon", "child", "minor",
    "underage", "young_girl", "young_boy", "elementary", "preschool",
    # Gore / Extreme violence
    "gore", "guro", "snuff", "death", "dismemberment", "decapitation",
    "mutilation", "torture", "vore", "cannibalism", "necrophilia",
    # Bodily waste
    "scat", "scatology", "piss", "urine", "pee", "feces", "shit", "diaper",
    "watersports", "coprophilia", "omorashi",
    # Bestiality
    "bestiality", "zoophilia", "feral", "animal_abuse",
    # Non-consensual
    "rape", "non-con", "noncon", "forced", "drugged", "unconscious_sex",
    # Other illegal
    "real_child", "csam", "cp", "pedo", "pedophilia",
}

def contains_prohibited_content(text: str) -> bool:
    """Check if text contains any prohibited terms"""
    if not text:
        return False
    text_lower = text.lower().replace("-", "_").replace(" ", "_")
    # Check each prohibited tag
    for tag in PROHIBITED_TAGS:
        # Match as whole word or with underscores
        if re.search(rf'\b{re.escape(tag)}\b', text_lower) or tag in text_lower:
            return True
    return False

def filter_prohibited_results(results: list) -> list:
    """Filter out results that contain prohibited tags"""
    if not results:
        return results
    
    filtered = []
    for r in results:
        # Check tags
        tags = r.get("tags", [])
        if isinstance(tags, str):
            tags = tags.split()
        
        tags_str = " ".join(str(t).lower() for t in tags)
        
        # Check if any prohibited tag is in the result's tags
        is_prohibited = False
        for tag in PROHIBITED_TAGS:
            if tag in tags_str:
                is_prohibited = True
                break
        
        if not is_prohibited:
            filtered.append(r)
    
    return filtered


# ═══════════════════════════════════════════════════════════════
# ART GALLERY VIEW - Multi-source, multi-image gallery with filters
# ═══════════════════════════════════════════════════════════════

class PageSelectorModal(discord.ui.Modal, title="Go to Page"):
    """Modal for jumping to a specific page"""
    page_input = discord.ui.TextInput(
        label="Page Number",
        placeholder="Enter page number...",
        required=True,
        max_length=5
    )
    
    def __init__(self, max_pages: int):
        super().__init__()
        self.max_pages = max_pages
        self.selected_page = None
        self.page_input.placeholder = f"Enter 1-{max_pages}"
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            page_num = int(self.page_input.value)
            if 1 <= page_num <= self.max_pages:
                self.selected_page = page_num - 1  # Convert to 0-indexed
                await interaction.response.defer()
            else:
                await interaction.response.send_message(f"❌ Page must be between 1 and {self.max_pages}", ephemeral=True)
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)


class ArtSourceSelect(discord.ui.Select):
    """Multi-select dropdown for choosing art sources"""
    
    def __init__(self, available_sources: dict, selected_sources: Set[str], is_nsfw: bool, sources_with_results: Set[str], row: int = 0):
        # Get available sources based on NSFW and safety requirements
        self.available_sources = {}
        for key, meta in ART_SOURCES.items():
            # Block NSFW-only sources if not in NSFW channel
            if meta["nsfw_only"] and not is_nsfw:
                continue
            # Block mixed-content sources if not in NSFW channel
            if meta.get("requires_nsfw_channel") and not is_nsfw:
                continue
            # Only show sources that have results for this query
            if sources_with_results is not None and key not in sources_with_results:
                continue
            self.available_sources[key] = meta
        
        options = []
        for key, meta in self.available_sources.items():
            options.append(discord.SelectOption(
                label=meta["name"],
                value=key,
                description=meta["description"][:50],
                default=key in selected_sources
            ))
        
        # Limit to 25 options (Discord limit)
        options = options[:25]

        disabled = False
        if not options:
            options = [discord.SelectOption(label="No sources available", value="__none__")]
            disabled = True
        
        # Ensure max_values doesn't exceed Discord's limit of 25
        max_vals = min(len(options), 25) if not disabled else 1
        min_vals = 1 if not disabled else 0
        
        super().__init__(
            placeholder="Select art sources...",
            min_values=min_vals,
            max_values=max_vals,
            options=options,
            row=row,
            disabled=disabled
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtGalleryView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # Skip if disabled or no valid selection
        if self.disabled or "__none__" in self.values:
            return await interaction.response.send_message("❌ No valid sources selected!", ephemeral=True)
        
        # Update selected sources
        view.selected_sources = set(self.values)
        
        # Update select defaults
        for opt in self.options:
            opt.default = opt.value in view.selected_sources
        
        # Refetch results with new sources
        await interaction.response.defer()
        view.page = 0
        view.results = []
        
        try:
            await view.fetch_results()
            embeds = view.build_embeds()
            view.update_buttons()
            await interaction.edit_original_response(embeds=embeds, view=view)
        except Exception as e:
            await interaction.followup.send(f"❌ Error updating results: {str(e)[:100]}", ephemeral=True)


class ArtViewModeSelect(discord.ui.Select):
    """Select for switching between single and gallery view modes"""
    
    def __init__(self, current_mode: str = "gallery", row: int = 1):
        options = [
            discord.SelectOption(
                label="Gallery Mode",
                value="gallery",
                description="Show 4 images per page",
                default=current_mode == "gallery"
            ),
            discord.SelectOption(
                label="Single Mode",
                value="single",
                description="Show 1 large image per page",
                default=current_mode == "single"
            ),
            discord.SelectOption(
                label="Preview Mode",
                value="preview",
                description="Show 6 thumbnail previews",
                default=current_mode == "preview"
            )
        ]
        super().__init__(
            placeholder="View mode...",
            options=options,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtGalleryView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        old_mode = view.view_mode
        new_mode = self.values[0]
        
        # Calculate which image index we're currently viewing
        old_images_per_page = {"gallery": 3, "single": 1, "preview": 6}.get(old_mode, 3)
        new_images_per_page = {"gallery": 3, "single": 1, "preview": 6}.get(new_mode, 3)
        
        # Get the first image index of current page and translate to new page
        current_image_index = view.page * old_images_per_page
        new_page = current_image_index // new_images_per_page
        
        view.view_mode = new_mode
        view.page = min(new_page, max(0, (len(view.results) - 1) // new_images_per_page)) if view.results else 0
        
        # Update select defaults
        for opt in self.options:
            opt.default = opt.value == view.view_mode
        
        embeds = view.build_embeds()
        view.update_buttons()
        await interaction.response.edit_message(embeds=embeds, view=view)


class ArtContentTypeSelect(discord.ui.Select):
    """Multi-select dropdown for filtering content type (images/videos)"""
    
    def __init__(self, current_filter: Set[str] = None, row: int = 2):
        # Default to showing both images and videos
        if current_filter is None:
            current_filter = {"images", "videos"}
        
        options = [
            discord.SelectOption(
                label="🖼️ Images",
                value="images",
                description="Show static images (JPG, PNG, GIF, WebP)",
                default="images" in current_filter
            ),
            discord.SelectOption(
                label="🎬 Videos", 
                value="videos",
                description="Show videos (MP4, WebM, GIFV)",
                default="videos" in current_filter
            )
        ]
        
        super().__init__(
            placeholder="Content type...",
            min_values=1,
            max_values=2,  # Allow both to be selected
            options=options,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction):
        view: ArtGalleryView = self.view
        if interaction.user != view.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        await interaction.response.defer()
        
        # Update content filter based on selections
        selected_values = set(self.values)
        
        if "images" in selected_values and "videos" in selected_values:
            view.content_filter = "all"  # Both selected = show all
        elif "images" in selected_values:
            view.content_filter = "images"  # Only images selected
        elif "videos" in selected_values:
            view.content_filter = "videos"  # Only videos selected
        else:
            view.content_filter = "all"  # Fallback to all
        
        # Update select defaults
        for opt in self.options:
            opt.default = opt.value in self.values
        
        # Refilter current results and rebuild embeds
        view.page = 0  # Reset to first page
        
        # If switching to videos-only, fetch more video-specific content
        if view.content_filter == "videos":
            # Check if we have enough video content using enhanced detection
            video_count = len(view.get_filtered_results())  # This now uses enhanced detection
            if video_count < 500:  # If not enough videos, fetch more
                await interaction.followup.send("🎬 Fetching more video content...", ephemeral=True)
                await view.fetch_results(aggressive=True)
        
        embeds = view.build_embeds()
        view.update_buttons()
        await interaction.edit_original_response(embeds=embeds, view=view)


class ArtGalleryView(discord.ui.View):
    """Advanced art gallery with multi-source selection and gallery mode"""
    
    def __init__(
        self, 
        cog,
        author: discord.Member,
        query: str,
        is_nsfw: bool,
        ctx,
        initial_results: list = None,
        selected_sources: Set[str] = None
    ):
        super().__init__(timeout=None)  # No timeout - buttons don't expire
        self.cog = cog
        self.author = author
        self.query = query
        self.is_nsfw = is_nsfw
        self.ctx = ctx
        self.results = initial_results or []
        self.page = 0
        self.view_mode = "gallery"  # gallery, single, preview
        self.loading_more = False
        self.api_page = 0  # Track API pagination
        self.source_pages = dict()  # Track page number per source for pagination
        self.total_loaded = len(initial_results) if initial_results else 0
        self.background_loading = False
        self.all_loaded = False
        
        # Content type filter: "all", "images", "videos"
        self.content_filter = "all"  # Default to show all content
        
        # Source category filter: "all", "safe", "mix", "nsfw"
        self.source_category = "mix"
        
        self.available_sources = self.get_available_sources(self.is_nsfw)
        
        # Default to sources matching the default category (mix)
        if selected_sources is None:
            filtered_sources = self.get_sources_by_category()
            self.selected_sources = set(filtered_sources.keys())
        else:
            self.selected_sources = selected_sources
        
        # Initialize source pages
        for source in self.selected_sources:
            self.source_pages[source] = 0

        self.sources_with_results = self.get_sources_with_results()
        
        self._setup_components()
    
    def _setup_components(self):
        """Setup all UI components - simplified layout"""
        self.clear_items()
        
        # Row 0: Source selection (filtered by category)
        filtered_sources = self.get_sources_by_category()
        self.source_select = ArtSourceSelect(
            filtered_sources, 
            self.selected_sources,
            self.is_nsfw,
            self.sources_with_results,
            row=0
        )
        self.add_item(self.source_select)
        
        # Row 1: View mode selection
        self.mode_select = ArtViewModeSelect(self.view_mode, row=1)
        self.add_item(self.mode_select)
        
        # Row 2: Content type filter (NEW)
        current_filter_set = {"images", "videos"} if self.content_filter == "all" else {self.content_filter}
        self.content_select = ArtContentTypeSelect(current_filter_set, row=2)
        self.add_item(self.content_select)
        
        # Row 3: Navigation buttons (simplified)
        self.add_item(self.prev_btn)
        self.add_item(self.page_indicator)
        self.add_item(self.next_btn)
        self.add_item(self.random_page_btn)
    
    def get_filtered_results(self) -> list:
        """Get results filtered by content type"""
        if self.content_filter == "all":
            return self.results
        
        filtered = []
        video_debug_count = 0
        image_debug_count = 0
        
        for result in self.results:
            content_url = result.get("url", "").lower()
            preview_url = result.get("preview_url", "").lower()
            
            # Enhanced video detection - check both content and preview URLs
            video_extensions = ['.mp4', '.webm', '.gifv', '.mov', '.avi', '.mkv', '.flv', '.m4v', '.3gp']
            video_indicators = ['video', 'webm', 'mp4', 'gifv', 'mov', 'anim']
            
            # Check if it's a video by URL extension
            is_video_by_url = any(content_url.endswith(ext) for ext in video_extensions)
            is_video_by_preview = any(preview_url.endswith(ext) for ext in video_extensions)
            
            # Check if it's a video by URL content indicators
            is_video_by_content = any(indicator in content_url for indicator in video_indicators)
            is_video_by_preview_content = any(indicator in preview_url for indicator in video_indicators)
            
            # Check file type metadata if available
            file_type = result.get("file_type", "").lower()
            is_video_by_type = file_type in ['video', 'webm', 'mp4', 'gifv', 'mov']
            
            # Check tags for video indicators
            tags = result.get("tags", [])
            if isinstance(tags, str):
                tags = tags.lower().split()
            is_video_by_tags = any(tag in tags for tag in ['video', 'animated', 'gif', 'webm', 'mp4'])
            
            # Consider it a video if any indicator matches
            is_video = (is_video_by_url or is_video_by_preview or 
                       is_video_by_content or is_video_by_preview_content or
                       is_video_by_type or is_video_by_tags)
            
            if is_video:
                video_debug_count += 1
            else:
                image_debug_count += 1
            
            if self.content_filter == "images" and not is_video:
                filtered.append(result)
            elif self.content_filter == "videos" and is_video:
                filtered.append(result)
        
        # Debug logging (can be removed later)
        if self.content_filter == "videos":
            print(f"DEBUG: Found {video_debug_count} videos, {image_debug_count} images out of {len(self.results)} total results")
            print(f"DEBUG: Filtered to {len(filtered)} videos")
        
        return filtered
    
    def get_page_results(self) -> list:
        """Get results for current page with content filtering"""
        filtered_results = self.get_filtered_results()
        start = self.page * self.images_per_page
        end = start + self.images_per_page
        return filtered_results[start:end]
    
    @property
    def images_per_page(self) -> int:
        """Number of images per page based on view mode"""
        return {"gallery": 3, "single": 1, "preview": 6}.get(self.view_mode, 3)
    
    @property
    def max_pages(self) -> int:
        """Calculate max pages based on filtered results"""
        filtered_results = self.get_filtered_results()
        if not filtered_results:
            return 1
        return max(1, (len(filtered_results) + self.images_per_page - 1) // self.images_per_page)
    
    async def fetch_results(self, aggressive: bool = True):
        """Fetch art results from selected sources
        
        Args:
            aggressive: If True, fetches multiple pages from all sources at once
        """
        if not hasattr(self.cog, 'art_aggregator'):
            import aiohttp
            if not hasattr(self.cog, 'session') or self.cog.session.closed:
                self.cog.session = aiohttp.ClientSession()
            self.cog.art_aggregator = ArtAggregator(self.cog.session)
        
        # Adjust search depth based on content filter
        if self.content_filter == "videos":
            # For videos, go much deeper to get more results
            max_pages = 200  # Double the depth for videos
            limit = 3000     # Higher limit for videos
        elif self.content_filter == "images":
            max_pages = 100  # Standard depth for images
            limit = 2000
        else:
            max_pages = 150  # Balanced for mixed content
            limit = 2500
        
        new_results = await self.cog.art_aggregator.search_all(
            self.query,
            limit=limit,
            nsfw=self.is_nsfw,
            selected_sources=self.selected_sources,
            page=self.api_page,
            aggressive_load=True,
            max_pages_per_source=max_pages
        )
        
        # Filter out prohibited content
        new_results = filter_prohibited_results(new_results)
        
        if new_results:
            # Add new results, avoiding duplicates
            existing_ids = {(r.get("source"), r.get("id")) for r in self.results}
            added = 0
            for r in new_results:
                if (r.get("source"), r.get("id")) not in existing_ids:
                    self.results.append(r)
                    existing_ids.add((r.get("source"), r.get("id")))
                    added += 1

            self.refresh_sources_with_results()
            
            self.total_loaded = len(self.results)
            
            # If we got fewer than expected, we might be done
            if added < 50:
                self.all_loaded = True
            
            return added
        else:
            self.all_loaded = True
            return 0
    
    async def fetch_from_source(self, source_key: str, page: int = None):
        """Fetch next page from a specific source
        
        Args:
            source_key: The source to fetch from
            page: Specific page number, or None to use tracked page
        """
        if not hasattr(self.cog, 'art_aggregator'):
            import aiohttp
            if not hasattr(self.cog, 'session') or self.cog.session.closed:
                self.cog.session = aiohttp.ClientSession()
            self.cog.art_aggregator = ArtAggregator(self.cog.session)
        
        # Get current page for this source
        if page is None:
            page = self.source_pages.get(source_key, 0) + 1
        
        # Fetch from specific source
        new_results = await self.cog.art_aggregator.search_source(
            source_key,
            self.query,
            limit=50,
            nsfw=self.is_nsfw,
            page=page
        )
        
        # Filter out prohibited content
        new_results = filter_prohibited_results(new_results)
        
        if new_results:
            # Add new results, avoiding duplicates
            existing_ids = {(r.get("source"), r.get("id")) for r in self.results}
            added = 0
            for r in new_results:
                if (r.get("source"), r.get("id")) not in existing_ids:
                    self.results.append(r)
                    existing_ids.add((r.get("source"), r.get("id")))
                    added += 1

            self.refresh_sources_with_results()
            
            # Update source page tracker
            self.source_pages[source_key] = page
            self.total_loaded = len(self.results)
            
            return added
        return 0
    
    async def fetch_more(self, aggressive: bool = False):
        """Fetch more results when approaching the end"""
        if self.loading_more or self.all_loaded:
            return 0
        self.loading_more = True
        try:
            self.api_page += 1
            added = await self.fetch_results(aggressive=aggressive)
            return added
        finally:
            self.loading_more = False
    
    async def start_background_loading(self):
        """Start background task to continuously load more results"""
        if self.background_loading or self.all_loaded:
            return
        
        self.background_loading = True
        
        # Continue fetching in background
        while not self.all_loaded and self.background_loading:
            try:
                added = await self.fetch_more(aggressive=True)
                if added == 0:
                    break
                # Small delay to avoid overwhelming the APIs
                await asyncio.sleep(2)
            except Exception:
                break
        
        self.background_loading = False
    
    def get_available_sources(self, nsfw: bool = False) -> dict:
        """Get available sources based on NSFW setting and channel safety"""
        available = {}
        for key, meta in ART_SOURCES.items():
            # Block NSFW-only sources if not in NSFW channel
            if meta["nsfw_only"] and not nsfw:
                continue
            # Block mixed-content sources if not in NSFW channel
            if meta.get("requires_nsfw_channel") and not nsfw:
                continue
            available[key] = meta
        return available
    
    def get_sources_by_category(self) -> dict:
        """Get sources filtered by the current category (safe/mix/nsfw/all)"""
        if self.source_category == "all":
            return self.available_sources
        
        filtered = {}
        for key, meta in self.available_sources.items():
            if self.source_category == "safe":
                # Safe sources: not nsfw_only and don't require nsfw channel
                if not meta["nsfw_only"] and not meta.get("requires_nsfw_channel"):
                    filtered[key] = meta
            elif self.source_category == "mix":
                # Mixed sources: require nsfw channel but not nsfw_only
                if not meta["nsfw_only"] and meta.get("requires_nsfw_channel"):
                    filtered[key] = meta
            elif self.source_category == "nsfw":
                # NSFW only sources
                if meta["nsfw_only"]:
                    filtered[key] = meta
        return filtered

    def get_sources_with_results(self) -> Set[str]:
        """Return ART_SOURCES keys that have at least 1 result in current results list."""
        if not self.results:
            return set()

        name_to_key = {meta.get("name"): key for key, meta in ART_SOURCES.items()}
        lower_name_to_key = {str(meta.get("name", "")).lower(): key for key, meta in ART_SOURCES.items()}

        found = set()
        for r in self.results:
            src = r.get("source")
            if not src:
                continue
            key = name_to_key.get(src) or lower_name_to_key.get(str(src).lower())
            if key:
                found.add(key)
        return found

    def refresh_sources_with_results(self):
        """Refresh dropdown options to only include sources that currently have results."""
        new_sources = self.get_sources_with_results()
        if new_sources != getattr(self, "sources_with_results", set()):
            self.sources_with_results = new_sources

            # Keep selections only if they still exist
            self.selected_sources = set(self.selected_sources) & set(self.sources_with_results)
            if not self.selected_sources and self.sources_with_results:
                self.selected_sources = set(self.sources_with_results)

            self._setup_components()
    
    def build_embeds(self) -> list:
        """Build embeds for current page based on view mode"""
        page_results = self.get_page_results()
        filtered_results = self.get_filtered_results()
        
        if not page_results:
            loading_msg = "Loading more results..." if self.background_loading else "No artwork found. Try different sources or search terms."
            embed = discord.Embed(
                title=f"🎨 Art Search: {self.query[:40]}",
                description=loading_msg,
                color=discord.Color.orange() if not self.background_loading else discord.Color.blue()
            )
            embed.add_field(
                name="Selected Sources",
                value=", ".join([ART_SOURCES.get(s, {}).get("name", s) for s in self.selected_sources][:5]) or "None",
                inline=False
            )
            # Add content filter info
            if self.content_filter == "all":
                filter_text = "🖼️🎬 Images + Videos"
            elif self.content_filter == "images":
                filter_text = "🖼️ Images Only"
            elif self.content_filter == "videos":
                filter_text = "🎬 Videos Only"
            else:
                filter_text = "🖼️🎬 Images + Videos"
            
            embed.add_field(
                name="Content Filter",
                value=filter_text,
                inline=True
            )
            if self.total_loaded > 0:
                embed.add_field(
                    name="Progress",
                    value=f"Loaded {self.total_loaded} results ({len(filtered_results)} after filter)" + (" (still loading...)" if self.background_loading else ""),
                    inline=False
                )
            return [embed]
        
        embeds = []
        base_color = discord.Color.from_rgb(255, 105, 180) if self.is_nsfw else primary_color()
        
        if self.view_mode == "single":
            # Single large image mode
            art = page_results[0]
            embed = self._build_single_embed(art, base_color)
            embeds.append(embed)
            
        elif self.view_mode == "gallery":
            # Gallery mode - up to 4 images with embeds
            for i, art in enumerate(page_results):
                embed = self._build_gallery_embed(art, i, len(page_results), base_color)
                embeds.append(embed)
                
        elif self.view_mode == "preview":
            # Preview mode - compact list with thumbnails
            embed = self._build_preview_embed(page_results, base_color)
            embeds.append(embed)
        
        return embeds
    
    def _build_single_embed(self, art: dict, color) -> discord.Embed:
        """Build embed for single image view"""
        embed = discord.Embed(
            title=f"🎨 {self.query[:50]}",
            url=art.get("page_url"),
            color=color
        )
        
        # Content safety warning system
        rating = art.get("rating", "s")
        source = art.get("source", "Unknown")
        source_meta = ART_SOURCES.get(source.lower().replace(" ", "_").replace(".", ""), {})
        requires_nsfw = source_meta.get("requires_nsfw_channel", False)
        
        # Build safety warning
        warnings = []
        if rating in ["e", "explicit"]:
            warnings.append("🔞 **Explicit NSFW Content**")
        elif rating in ["q", "questionable"]:
            warnings.append("⚠️ **Questionable Content**")
        
        # Warn about mixed-content sources
        if requires_nsfw and not self.is_nsfw:
            warnings.append("⚠️ **Warning: This source may contain unsafe content**")
        
        if warnings:
            embed.description = " | ".join(warnings)
        else:
            embed.description = "✅ Safe content"
        
        # Art info in compact format
        info_parts = [
            f"**Source:** {art.get('source', 'Unknown')}",
            f"**Artist:** {art.get('artist', 'Unknown')[:30]}",
            f"**Score:** ⭐ {art.get('score', 0)}"
        ]
        
        if art.get("width") and art.get("height"):
            info_parts.append(f"**Size:** {art.get('width')}x{art.get('height')}")
        
        embed.add_field(name="Info", value=" • ".join(info_parts), inline=False)
        
        # Tags
        tags = art.get("tags", [])[:12]
        if tags:
            tag_str = " ".join([f"`{tag}`" for tag in tags])
            embed.add_field(name="Tags", value=tag_str[:1024], inline=False)
        
        # Check if content is a video or non-image
        content_url = art.get("url", "")
        is_video = any(content_url.lower().endswith(ext) for ext in ['.mp4', '.webm', '.gifv', '.mov'])
        is_non_image = not any(content_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
        
        if is_video or is_non_image:
            # For videos and non-image content, show link instead of embedding
            if not embed.description:
                embed.description = ""
            embed.description += f"\n\n🔗 **[View Content]({art.get('page_url', content_url)})**\n*Click to view {('video' if is_video else 'content')}*"
            # Use thumbnail if available, otherwise don't set image
            if art.get("preview_url"):
                embed.set_image(url=art.get("preview_url"))
        else:
            # For regular images, embed normally
            embed.set_image(url=content_url)
        
        # Footer with loading indicator
        art_id = f"{art.get('source', 'unknown').lower()}_{art.get('id', 'unknown')}"
        footer_text = f"Page {self.page + 1}/{self.max_pages} • {len(self.results)} total"
        if self.background_loading:
            footer_text += " • 🔄 Loading more..."
        elif self.all_loaded:
            footer_text += " • ✅ All loaded"
        footer_text += f" • ID: {art_id}"
        embed.set_footer(text=footer_text)
        
        return embed
    
    def _build_gallery_embed(self, art: dict, index: int, total: int, color) -> discord.Embed:
        """Build embed for gallery mode (multiple images)"""
        # Only first embed gets full info
        if index == 0:
            desc_parts = [f"Showing {total} images • Page {self.page + 1}/{self.max_pages}"]
            if self.is_nsfw:
                desc_parts.insert(0, "🔞 NSFW")
            if self.background_loading:
                desc_parts.append("🔄 Loading more...")
            elif self.all_loaded:
                desc_parts.append(f"✅ {len(self.results)} total loaded")
            
            embed = discord.Embed(
                title=f"🖼️ {self.query[:40]} - Gallery",
                description=" • ".join(desc_parts),
                color=color
            )
        else:
            embed = discord.Embed(color=color)
        
        # Compact info for each image
        embed.add_field(
            name=f"{art.get('source', 'Unknown')}",
            value=f"⭐ {art.get('score', 0)} • {art.get('artist', 'Unknown')[:20]}",
            inline=True
        )
        
        # Check if content is a video or non-image
        content_url = art.get("url", "")
        is_video = any(content_url.lower().endswith(ext) for ext in ['.mp4', '.webm', '.gifv', '.mov'])
        is_non_image = not any(content_url.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp'])
        
        if is_video or is_non_image:
            # For videos and non-image content, show link instead of embedding
            embed.description = f"🔗 **[View Content]({art.get('page_url', content_url)})**\n*Click to view {('video' if is_video else 'content')}*"
            # Use thumbnail if available, otherwise don't set image
            if art.get("preview_url"):
                embed.set_image(url=art.get("preview_url"))
        else:
            # For regular images, embed normally
            embed.set_image(url=content_url)
        
        return embed
    
    def _build_preview_embed(self, arts: list, color) -> discord.Embed:
        """Build embed for preview mode (thumbnails list)"""
        embed = discord.Embed(
            title=f"📋 {self.query[:40]} - Preview",
            description=f"Page {self.page + 1}/{self.max_pages} • {len(self.results)} total results",
            color=color
        )
        
        if self.is_nsfw:
            embed.description = f"🔞 NSFW • " + embed.description
        
        for i, art in enumerate(arts, 1):
            art_id = f"{art.get('source', '?').lower()}_{art.get('id', '?')}"
            embed.add_field(
                name=f"{i}. {art.get('source', 'Unknown')}",
                value=f"⭐ {art.get('score', 0)} • [{art.get('artist', 'Unknown')[:15]}]({art.get('page_url', '')})",
                inline=True
            )
        
        # Set first image as thumbnail
        if arts:
            embed.set_thumbnail(url=arts[0].get("preview_url") or arts[0].get("url"))
        
        embed.set_footer(text="Use Single Mode to view full images")
        
        return embed
    
    def update_buttons(self):
        """Update button states"""
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= self.max_pages - 1
        
        # Update page indicator
        self.page_indicator.label = f"{self.page + 1}/{self.max_pages}"
    
    # Navigation buttons (Row 3) - Main navigation
    @discord.ui.button(label="◀️", style=discord.ButtonStyle.primary, row=3)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        self.page = max(0, self.page - 1)
        self.update_buttons()
        embeds = self.build_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    @discord.ui.button(label="1/1", style=discord.ButtonStyle.secondary, row=3)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page selector - opens modal to jump to specific page"""
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # Show page selector modal
        modal = PageSelectorModal(self.max_pages)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.selected_page is not None:
            self.page = modal.selected_page
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.edit_original_response(embeds=embeds, view=self)
    
    @discord.ui.button(label="▶️", style=discord.ButtonStyle.primary, row=3)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        self.page = min(self.max_pages - 1, self.page + 1)
        
        # Auto-fetch more content if approaching end and filtering videos
        if (self.page >= self.max_pages - 3 and 
            self.content_filter == "videos" and 
            not self.all_loaded):
            await interaction.response.defer()
            await self.fetch_results(aggressive=True)
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.edit_original_response(embeds=embeds, view=self)
        else:
            self.update_buttons()
            embeds = self.build_embeds()
            await interaction.response.edit_message(embeds=embeds, view=self)
    
    @discord.ui.button(label="🎲", style=discord.ButtonStyle.success, row=3)
    async def random_page_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Instantly jump to a random page"""
        if interaction.user != self.author:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        import random
        # Jump to random page instantly
        self.page = random.randint(0, self.max_pages - 1)
        self.update_buttons()
        embeds = self.build_embeds()
        await interaction.response.edit_message(embeds=embeds, view=self)
    
    

class SaveArtModal(discord.ui.Modal, title="Save Art to Favorites"):
    folder = discord.ui.TextInput(
        label="Folder Name",
        placeholder="Enter folder name (default: 'default')",
        default="default",
        required=False,
        max_length=50
    )
    
    def __init__(self, art_id: str, art_data: dict):
        super().__init__()
        self.art_id = art_id
        self.art_data = art_data
    
    async def on_submit(self, interaction: discord.Interaction):
        folder_name = self.folder.value or "default"
        
        from utils.cogs.quest import Quest_Data
        quest_data = Quest_Data(interaction.client)
        
        guild_id = str(interaction.guild.id)
        user_id = str(interaction.user.id)
        
        try:
            await quest_data.mongoConnect[quest_data.DB_NAME]["Servers"].update_one(
                {"guild_id": guild_id},
                {
                    "$push": {
                        f"members.{user_id}.art_favorites.{folder_name}": {
                            "id": self.art_id,
                            "source": self.art_data.get("source"),
                            "url": self.art_data.get("url"),
                            "preview_url": self.art_data.get("preview_url"),
                            "artist": self.art_data.get("artist"),
                            "tags": self.art_data.get("tags", [])[:10],
                            "saved_at": discord.utils.utcnow().timestamp()
                        }
                    }
                },
                upsert=True
            )
            
            embed = discord.Embed(
                title="✅ Art Saved!",
                description=f"Saved to folder: **{folder_name}**\nArt ID: `{self.art_id}`",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=self.art_data.get("preview_url") or self.art_data.get("url"))
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to save: {e}", ephemeral=True)


# Legacy ArtView for backwards compatibility
class ArtView(ArtGalleryView):
    """Legacy wrapper - redirects to new ArtGalleryView"""
    def __init__(self, results, author, query, is_nsfw, ctx):
        super().__init__(
            cog=None,
            author=author,
            query=query,
            is_nsfw=is_nsfw,
            ctx=ctx,
            initial_results=results
        )


class GoogleSearchTypeSelect(discord.ui.Select):
    """Select menu for switching between search types"""
    def __init__(self, current_type: str = "web"):
        options = [
            discord.SelectOption(label="Web Results", value="web", emoji="🔗", default=(current_type == "web")),
            discord.SelectOption(label="Images", value="images", emoji="🖼️", default=(current_type == "images")),
            discord.SelectOption(label="Videos", value="videos", emoji="🎬", default=(current_type == "videos")),
        ]
        super().__init__(placeholder="Select search type...", options=options, row=0)
    
    async def callback(self, interaction: discord.Interaction):
        view: GoogleSearchView = self.view
        if interaction.user.id != view.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        view.search_type = self.values[0]
        view.page = 0
        
        # Update select default
        for opt in self.options:
            opt.default = (opt.value == view.search_type)
        
        # Fetch new results
        await interaction.response.defer()
        await view.fetch_results()
        embed = view.build_embed()
        view.update_buttons()
        await interaction.edit_original_response(embed=embed, view=view)


class GoogleSearchView(discord.ui.View):
    """Interactive view for Google search with tabs for web/images/videos"""
    
    def __init__(self, cog, author: discord.Member, query: str, search_type: str = "web", safe_search: bool = True):
        super().__init__(timeout=180)
        self.cog = cog
        self.author = author
        self.query = query
        self.search_type = search_type
        self.safe_search = safe_search  # SafeSearch enabled by default
        self.page = 0
        self.results = {"web": [], "images": [], "videos": []}
        self.per_page = {"web": 5, "images": 1, "videos": 1}
        self.image_fetch_offset = 0  # Track how many batches we've fetched for images
        self.loading_more = False  # Prevent duplicate fetches
        
        # Add select menu
        self.type_select = GoogleSearchTypeSelect(search_type)
        self.add_item(self.type_select)
    
    async def fetch_results(self):
        """Fetch results for current search type with SafeSearch"""
        if self.search_type == "web" and not self.results["web"]:
            self.results["web"] = await self.cog.google.search(self.query, num=10, safe=self.safe_search)
        elif self.search_type == "images" and not self.results["images"]:
            self.results["images"] = await self.cog.google.image_search(self.query, num=50, safe=self.safe_search)
            self.image_fetch_offset = 50
        elif self.search_type == "videos" and not self.results["videos"]:
            self.results["videos"] = await self.cog.google.video_search(self.query, num=10, safe=self.safe_search)
    
    async def fetch_more_images(self):
        """Fetch more images when user reaches near the end (infinite scroll)"""
        if self.loading_more:
            return
        self.loading_more = True
        try:
            new_images = await self.cog.google.image_search(
                self.query, num=50, start=self.image_fetch_offset, safe=self.safe_search
            )
            if new_images:
                # Filter out duplicates
                existing_urls = {img.get("link") for img in self.results["images"]}
                for img in new_images:
                    if img.get("link") not in existing_urls:
                        self.results["images"].append(img)
                        existing_urls.add(img.get("link"))
                self.image_fetch_offset += 50
        finally:
            self.loading_more = False
    
    def get_current_results(self):
        return self.results.get(self.search_type, [])
    
    def get_max_pages(self):
        results = self.get_current_results()
        per_page = self.per_page.get(self.search_type, 1)
        return max(1, (len(results) + per_page - 1) // per_page)
    
    def update_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        # For images, never disable next button (infinite scroll)
        if self.search_type == "images":
            self.next_btn.disabled = False
        else:
            self.next_btn.disabled = self.page >= self.get_max_pages() - 1
        # Show/hide set image button based on search type
        self.set_image_btn.disabled = self.search_type != "images" or not self.get_current_results()
    
    def build_embed(self) -> discord.Embed:
        results = self.get_current_results()
        
        if not results:
            embed = discord.Embed(
                title=f"Google Search: {self.query[:50]}",
                description=f"No {self.search_type} results found for **{self.query}**\n\n"
                           f"Try a different search term or type.",
                color=discord.Color.orange()
            )
            return embed
        
        if self.search_type == "web":
            return self._build_web_embed(results)
        elif self.search_type == "images":
            return self._build_image_embed(results)
        elif self.search_type == "videos":
            return self._build_video_embed(results)
        
        return discord.Embed(title="Error", color=discord.Color.red())
    
    def _build_web_embed(self, results: list) -> discord.Embed:
        embed = discord.Embed(
            title=f"Web Results: {self.query[:40]}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        start = self.page * 5
        page_results = results[start:start + 5]
        
        for i, result in enumerate(page_results, start + 1):
            title = result.get("title", "No Title")[:55]
            link = result.get("link", "")
            snippet = result.get("snippet", "No description")[:150]
            
            # Clean up the snippet
            snippet = snippet.replace("\n", " ").strip()
            
            embed.add_field(
                name=f"{i}. {title}",
                value=f"{snippet}\n🔗 [Visit]({link})",
                inline=False
            )
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.get_max_pages()} • {len(results)} results")
        return embed
    
    def _build_image_embed(self, results: list) -> discord.Embed:
        if self.page >= len(results):
            self.page = 0
        
        image = results[self.page]
        
        embed = discord.Embed(
            title=f"Images: {self.query[:40]}",
            color=primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        image_url = image.get("link", "")
        if image_url:
            embed.set_image(url=image_url)
        
        if image.get("source"):
            embed.add_field(name="Source", value=f"[View Source]({image['source']})", inline=True)
        
        embed.set_footer(text=f"Image {self.page + 1}/{len(results)}+ • Click 📌 Set Image to select • Infinite scroll enabled")
        return embed
    
    def _build_video_embed(self, results: list) -> discord.Embed:
        if self.page >= len(results):
            self.page = 0
        
        video = results[self.page]
        
        platform_emoji = "🎬"
        if video.get("platform") == "youtube":
            platform_emoji = "📺"
        elif video.get("platform") == "vimeo":
            platform_emoji = "🎥"
        
        embed = discord.Embed(
            title=f"{platform_emoji} Videos: {self.query[:40]}",
            url=video.get("url", ""),
            color=discord.Color.red() if video.get("platform") == "youtube" else primary_color(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="🎬 Watch Video",
            value=f"**[Click to Watch]({video.get('url', '')})**",
            inline=False
        )
        
        if video.get("platform") == "youtube":
            embed.add_field(name="Platform", value="YouTube", inline=True)
            embed.add_field(name="Video ID", value=f"`{video.get('video_id', 'N/A')}`", inline=True)
        
        # Set thumbnail
        if video.get("thumbnail"):
            embed.set_image(url=video["thumbnail"])
        
        embed.set_footer(text=f"Video {self.page + 1}/{len(results)} • Click link to watch")
        return embed
    
    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary, row=1)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        self.page = max(0, self.page - 1)
        self.update_buttons()
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # For images, implement infinite scroll
        if self.search_type == "images":
            self.page += 1
            # Fetch more images when approaching the end
            if self.page >= len(self.results["images"]) - 5:
                await interaction.response.defer()
                await self.fetch_more_images()
                self.update_buttons()
                embed = self.build_embed()
                await interaction.edit_original_response(embed=embed, view=self)
                return
        else:
            self.page = min(self.get_max_pages() - 1, self.page + 1)
        
        self.update_buttons()
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.primary, row=1)
    async def refresh_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        # Clear cached results for current type and refetch
        self.results[self.search_type] = []
        self.image_fetch_offset = 0
        await interaction.response.defer()
        await self.fetch_results()
        self.page = 0
        self.update_buttons()
        embed = self.build_embed()
        await interaction.edit_original_response(embed=embed, view=self)
    
    @discord.ui.button(label="📌 Set Image", style=discord.ButtonStyle.success, row=1)
    async def set_image_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ This isn't your search!", ephemeral=True)
        
        if self.search_type != "images" or not self.results["images"]:
            return await interaction.response.send_message("❌ No image to set!", ephemeral=True)
        
        # Get current image
        image = self.results["images"][self.page]
        image_url = image.get("link", "")
        
        if not image_url:
            return await interaction.response.send_message("❌ Could not get image URL!", ephemeral=True)
        
        # Send the image as a standalone message
        embed = discord.Embed(
            title=f"Selected Image",
            description=f"**Search:** {self.query}\n**Image {self.page + 1}** of {len(self.results['images'])}+",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_image(url=image_url)
        embed.add_field(name="Direct Link", value=f"[Click to open]({image_url})", inline=False)
        embed.set_footer(text=f"Selected by {interaction.user.display_name}")
        
        await interaction.response.send_message(embed=embed)
