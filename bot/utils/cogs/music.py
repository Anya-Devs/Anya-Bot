
"""
Music utilities for the Music cog
Handles YouTube API integration, audio streaming, and queue management
"""

import os
import re
import time
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque

import discord
from discord import FFmpegPCMAudio, PCMVolumeTransformer

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"',
    'options': '-vn -loglevel warning'
}

YT_DLP_OPTIONS = {
    'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
    'extractaudio': True,
    'noplaylist': True,
    'extract_flat': False,
    'ignoreerrors': True,
    'audioformat': 'opus',
    'audioquality': 0,
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',
    'prefer_ffmpeg': True,
    'keepvideo': False,
    'extract_flat': False,
    'writethumbnail': False,
    'writeinfojson': False,
    'writesubtitles': False,
    'writeautomaticsub': False,
    'socket_timeout': 30,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    },
    'extractor_args': {
        'youtube': {
            'player_client': ['android', 'web'],
            'player_skip': ['js', 'configs'],
        }
    },
}


@dataclass
class Track:
    title: str
    url: str
    video_id: str
    duration: str
    thumbnail: str
    channel: str
    requester: discord.Member
    stream_url: Optional[str] = None

    @property
    def youtube_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}"

    def to_embed_field(self, index: int = None) -> dict:
        prefix = f"`{index}.` " if index is not None else ""
        return {
            "name": f"{prefix}{self.title[:50]}{'...' if len(self.title) > 50 else ''}",
            "value": f"Duration: `{self.duration}` | By: {self.channel[:20]}",
            "inline": False
        }


@dataclass
class GuildMusicState:
    guild_id: int
    queue: deque = field(default_factory=deque)
    current_track: Optional[Track] = None
    voice_client: Optional[discord.VoiceClient] = None
    volume: float = 1.0
    loop_mode: str = "off"
    is_paused: bool = False
    control_message: Optional[discord.Message] = None
    votes: Dict[str, set] = field(default_factory=lambda: {"skip": set(), "stop": set(), "pause": set()})
    last_activity: datetime = field(default_factory=datetime.now)

    def clear_votes(self):
        self.votes = {"skip": set(), "stop": set(), "pause": set()}

    def add_vote(self, vote_type: str, user_id: int) -> int:
        if vote_type in self.votes:
            self.votes[vote_type].add(user_id)
        return len(self.votes.get(vote_type, set()))

    def remove_vote(self, vote_type: str, user_id: int):
        if vote_type in self.votes:
            self.votes[vote_type].discard(user_id)

    def get_vote_count(self, vote_type: str) -> int:
        return len(self.votes.get(vote_type, set()))

    def get_required_votes(self) -> int:
        if self.voice_client and self.voice_client.channel:
            members = [m for m in self.voice_client.channel.members if not m.bot]
            return max(1, len(members) // 2)
        return 1

    def has_voted(self, vote_type: str, user_id: int) -> bool:
        return user_id in self.votes.get(vote_type, set())


class YouTubeAPI:
    def __init__(self):
        self.api_key = YOUTUBE_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None

    async def ensure_session(self):
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()

    async def search(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        await self.ensure_session()
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key,
            "videoCategoryId": "10",
        }
        try:
            async with self.session.get(YOUTUBE_SEARCH_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("items", [])
                else:
                    error_data = await resp.json()
                    print(f"YouTube API Error: {error_data}")
                    return []
        except Exception as e:
            print(f"YouTube search error: {e}")
            return []

    async def get_video_details(self, video_ids: List[str]) -> Dict[str, Dict]:
        await self.ensure_session()
        params = {
            "part": "contentDetails,snippet",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        try:
            async with self.session.get(YOUTUBE_VIDEO_URL, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    results = {}
                    for item in data.get("items", []):
                        vid_id = item["id"]
                        duration = self._parse_duration(item["contentDetails"]["duration"])
                        results[vid_id] = {
                            "duration": duration,
                            "title": item["snippet"]["title"],
                            "channel": item["snippet"]["channelTitle"],
                            "thumbnail": item["snippet"]["thumbnails"].get("high", {}).get("url", ""),
                        }
                    return results
                return {}
        except Exception as e:
            print(f"YouTube video details error: {e}")
            return {}

    def _parse_duration(self, duration: str) -> str:
        match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', duration)
        if not match:
            return "0:00"
        hours, minutes, seconds = match.groups()
        hours = int(hours) if hours else 0
        minutes = int(minutes) if minutes else 0
        seconds = int(seconds) if seconds else 0
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    async def search_tracks(self, query: str, requester: discord.Member, max_results: int = 10) -> List[Track]:
        await self.ensure_session()
        try:
            api_key = YOUTUBE_API_KEY
            if not api_key:
                print("YouTube API key not configured")
                return []
            
            print('Searching YouTube for:', query)
            
            # Search for videos
            search_url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&maxResults=20&key={api_key}&videoCategoryId=10"
            async with self.session.get(search_url) as search_response:
                if not search_response.ok:
                    print(f"YouTube API error: {search_response.status}")
                    return []
                
                search_data = await search_response.json()
                video_ids = [item["id"]["videoId"] for item in search_data["items"]]
                
                # Get video details (including duration)
                details_url = f"https://www.googleapis.com/youtube/v3/videos?part=contentDetails&id={','.join(video_ids)}&key={api_key}"
                async with self.session.get(details_url) as details_response:
                    details_data = await details_response.json()
                    
                    tracks = []
                    for i, item in enumerate(search_data["items"][:max_results]):
                        snippet = item["snippet"]
                        video_id = item["id"]["videoId"]
                        details = details_data["items"][i] if i < len(details_data["items"]) else {}
                        
                        track = Track(
                            title=snippet.get("title", "Unknown"),
                            url=f"https://www.youtube.com/watch?v={video_id}",
                            video_id=video_id,
                            duration=self._parse_duration(details.get("contentDetails", {}).get("duration", "PT0S")),
                            thumbnail=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                            channel=snippet.get("channelTitle", "Unknown"),
                            requester=requester,
                        )
                        tracks.append(track)
                    
                    print(f"Found {len(tracks)} tracks")
                    return tracks
        except Exception as e:
            print(f"Error searching YouTube: {e}")
            return []


class AudioSource:
    """Audio source using yt-dlp with improved bot detection avoidance"""

    @staticmethod
    async def get_stream_url(video_url: str) -> Optional[str]:
        """Get audio stream URL using yt-dlp with multiple fallback strategies"""
        try:
            import yt_dlp
            loop = asyncio.get_event_loop()

            def extract():
                # Try with default settings first
                ydl_opts = {**YT_DLP_OPTIONS}
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    if not info:
                        return None

                    # Pick best available audio
                    audio_formats = [f for f in info.get('formats', []) if f.get('acodec') != 'none']
                    if audio_formats:
                        audio_formats.sort(key=lambda f: f.get('abr') or 0, reverse=True)
                        return audio_formats[0].get('url')

                    # Fallback: any format url
                    return info.get('url')

            try:
                stream_url = await loop.run_in_executor(None, extract)
                if stream_url:
                    return stream_url
            except Exception as e:
                error_msg = str(e)
                print(f"yt-dlp error: {error_msg}")

                # If bot detection, try with different client
                if "Sign in to confirm you're not a bot" in error_msg or "bot" in error_msg.lower():
                    print("Trying with Android client...")
                    def extract_android():
                        ydl_opts = {**YT_DLP_OPTIONS}
                        ydl_opts['extractor_args']['youtube']['player_client'] = ['android']
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(video_url, download=False)
                            if info and info.get('formats'):
                                audio_formats = [f for f in info['formats'] if f.get('acodec') != 'none']
                                if audio_formats:
                                    audio_formats.sort(key=lambda f: f.get('abr') or 0, reverse=True)
                                    return audio_formats[0].get('url')
                        return None

                    try:
                        stream_url = await loop.run_in_executor(None, extract_android)
                        if stream_url:
                            print("Android client worked!")
                            return stream_url
                    except Exception as e2:
                        print(f"Android client also failed: {e2}")

            return None

        except Exception as e:
            print(f"Error getting stream URL: {e}")
            return None
    
    @staticmethod
    async def close_session():
        """Compatibility method - pytubefix doesn't need session cleanup"""
        pass

    @staticmethod
    async def create_source(track: Track, volume: float = 0.5) -> Optional[PCMVolumeTransformer]:
        """Create audio source for a track"""
        stream_url = await AudioSource.get_stream_url(track.youtube_url)
        if not stream_url:
            print(f"Failed to get stream URL for {track.title}")
            return None
        
        track.stream_url = stream_url
        
        # Try multiple ffmpeg paths for compatibility
        ffmpeg_paths = []
        
        # Local development paths
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ffmpeg_paths.append(os.path.join(project_root, "ffmpeg", "ffmpeg-8.0.1-essentials_build", "bin", "ffmpeg.exe"))
        ffmpeg_paths.append(os.path.join(project_root, "ffmpeg", "ffmpeg-8.0.1-essentials_build", "bin", "ffmpeg"))
        
        # Docker container paths
        ffmpeg_paths.append("/home/container/ffmpeg/ffmpeg-8.0.1-essentials_build/bin/ffmpeg")
        ffmpeg_paths.append("/usr/bin/ffmpeg")
        ffmpeg_paths.append("/bin/ffmpeg")
        
        # Try each path
        ffmpeg_executable = None
        for path in ffmpeg_paths:
            if os.path.exists(path) and os.access(path, os.X_OK):
                ffmpeg_executable = path
                break
        
        try:
            # If no executable found, let discord.py use system ffmpeg
            if ffmpeg_executable:
                source = FFmpegPCMAudio(stream_url, executable=ffmpeg_executable, **FFMPEG_OPTIONS)
            else:
                source = FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
            return PCMVolumeTransformer(source, volume=volume)
        except Exception as e:
            print(f"Error creating audio source: {e}")
            return None


class MusicEmbed:
    """Creates embeds for music-related displays"""
    
    @staticmethod
    def now_playing(track: Track, state: GuildMusicState) -> discord.Embed:
        """Create now playing embed with natural formatted info"""
        loop_icons = {"off": "", "track": "🔂", "queue": "🔁"}
        status_icon = "⏸️" if state.is_paused else "▶️"
        
        embed = discord.Embed(
            title=f"{status_icon} Now Playing",
            description=f"**[{track.title}]({track.youtube_url})**",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        
        # Natural formatted info layout
        info_text = f"```yaml\nDuration: {track.duration}\nChannel:  {track.channel[:35]}\nVolume:   {int(state.volume * 100)}%"
        
        if state.loop_mode != "off":
            loop_text = "Track" if state.loop_mode == "track" else "Queue"
            info_text += f"\nLoop:     {loop_text}"
        
        if len(state.queue) > 0:
            info_text += f"\nQueue:    {len(state.queue)} tracks waiting"
        
        info_text += "```"
        
        embed.add_field(
            name="📊 Track Info",
            value=info_text,
            inline=False
        )
        
        embed.set_image(url=track.thumbnail)
        
        embed.set_footer(
            text=f"Requested by {track.requester.display_name}",
            icon_url=track.requester.display_avatar.url
        )
        
        return embed
    
    @staticmethod
    def search_results(tracks: List[Track], query: str) -> discord.Embed:
        """Create search results embed showing all 10 tracks"""
        embed = discord.Embed(
            title="🎵 Search Results",
            description=f"Found **{len(tracks)}** results for: `{query}`\n\n**Select a song from the dropdown below**",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        
        # Show all 10 tracks
        for i, track in enumerate(tracks[:10], 1):
            title = track.title[:35] + "..." if len(track.title) > 35 else track.title
            embed.add_field(
                name=f"`{i}.` {title}",
                value=f"{track.duration} • {track.channel[:20]}",
                inline=False
            )
        
        return embed
    
    @staticmethod
    def queue_embed(state: GuildMusicState, page: int = 0) -> discord.Embed:
        """Create queue embed with code block formatting"""
        embed = discord.Embed(
            title="🎶 Music Queue",
            color=discord.Color.from_rgb(88, 101, 242)
        )
        
        # Current track section
        if state.current_track:
            status = "⏸️ Paused" if state.is_paused else "▶️ Playing"
            current_title = state.current_track.title[:50] + "..." if len(state.current_track.title) > 50 else state.current_track.title
            embed.add_field(
                name=f"{status} Now",
                value=f"```{current_title}```\n**Duration:** `{state.current_track.duration}` | **By:** {state.current_track.requester.mention}",
                inline=False
            )
        
        # Queue section
        if not state.queue:
            embed.add_field(
                name="🎵 Up Next",
                value="```Queue is empty```\nUse `/play` to add songs!",
                inline=False
            )
        else:
            items_per_page = 10
            start = page * items_per_page
            end = start + items_per_page
            queue_list = list(state.queue)
            
            # Build code block for queue
            queue_lines = []
            for i, track in enumerate(queue_list[start:end], start + 1):
                title = track.title[:40] + "..." if len(track.title) > 40 else track.title
                queue_lines.append(f"{i}. {title} [{track.duration}]")
            
            queue_code = "```\n" + "\n".join(queue_lines) + "\n```"
            
            # Build requester info
            requester_info = " | ".join([f"`{i+1}.` {queue_list[start+i].requester.display_name}" for i in range(min(len(queue_list[start:end]), 5))])
            if len(queue_list[start:end]) > 5:
                requester_info += f" *+{len(queue_list[start:end]) - 5} more*"
            
            embed.add_field(
                name=f"🎵 Up Next ({len(state.queue)} tracks)",
                value=queue_code,
                inline=False
            )
            
            embed.add_field(
                name="👤 Requested By",
                value=requester_info,
                inline=False
            )
            
            # Calculate total duration
            total_seconds = 0
            for track in state.queue:
                parts = track.duration.split(":")
                if len(parts) == 2:
                    total_seconds += int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    total_seconds += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0:
                total_duration = f"{hours}h {minutes}m"
            else:
                total_duration = f"{minutes}m {seconds}s"
            
            total_pages = (len(state.queue) - 1) // items_per_page + 1
            footer_text = f"Total Duration: {total_duration}"
            if total_pages > 1:
                footer_text += f" | Page {page + 1}/{total_pages}"
            embed.set_footer(text=footer_text)
        
        return embed
    
    @staticmethod
    def added_to_queue(track: Track, position: int) -> discord.Embed:
        """Create added to queue embed - clean and simple"""
        title = track.title[:50] + "..." if len(track.title) > 50 else track.title
        embed = discord.Embed(
            title="✅ Added to Queue",
            description=f"**{title}**\n⏱️ {track.duration} • Position #{position}",
            color=discord.Color.green()
        )
        embed.set_footer(
            text=f"Requested by {track.requester.display_name}",
            icon_url=track.requester.display_avatar.url
        )
        return embed
    
    @staticmethod
    def vote_status(vote_type: str, current: int, required: int, action: str) -> discord.Embed:
        """Create vote status embed - clean progress display"""
        progress_filled = "█" * current
        progress_empty = "░" * (required - current)
        progress_bar = f"`[{progress_filled}{progress_empty}]`"
        
        embed = discord.Embed(
            title=f"🗳️ Vote to {action.title()}",
            description=f"**{current}/{required}** votes needed\n{progress_bar}",
            color=discord.Color.orange()
        )
        embed.set_footer(text="Click the button again to remove your vote")
        return embed
    
    @staticmethod
    def error(message: str) -> discord.Embed:
        """Create error embed - clean and informative"""
        return discord.Embed(
            description=f"❌ {message}",
            color=discord.Color.red()
        )
    
    @staticmethod
    def success(message: str) -> discord.Embed:
        """Create success embed - clean and positive"""
        return discord.Embed(
            description=f"✅ {message}",
            color=discord.Color.green()
        )


class MusicStateManager:
    """Manages music states across all guilds"""
    
    def __init__(self):
        self.states: Dict[int, GuildMusicState] = {}
        self.youtube = YouTubeAPI()
    
    def get_state(self, guild_id: int) -> GuildMusicState:
        if guild_id not in self.states:
            self.states[guild_id] = GuildMusicState(guild_id=guild_id)
        return self.states[guild_id]
    
    def remove_state(self, guild_id: int):
        if guild_id in self.states:
            del self.states[guild_id]
    
    async def cleanup(self):
        """Cleanup all states and close sessions"""
        await self.youtube.close()
        await AudioSource.close_session()
        for state in self.states.values():
            if state.voice_client and state.voice_client.is_connected():
                await state.voice_client.disconnect()
        self.states.clear()
