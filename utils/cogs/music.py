"""
Music utilities for the Music cog
Handles YouTube API integration, audio streaming, and queue management
"""

import os
import re
import asyncio
import aiohttp
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
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

YT_DLP_OPTIONS = {
    'format': 'bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio/best',
    'extractaudio': True,
    'audioformat': 'opus',
    'audioquality': 0,  # Best quality
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
}


@dataclass
class Track:
    """Represents a music track"""
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
    """Manages music state for a guild"""
    guild_id: int
    queue: deque = field(default_factory=deque)
    current_track: Optional[Track] = None
    voice_client: Optional[discord.VoiceClient] = None
    volume: float = 1.0
    loop_mode: str = "off"  # off, track, queue
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
    """Handles YouTube Data API v3 interactions"""
    
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
        """Search YouTube for videos"""
        await self.ensure_session()
        
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": max_results,
            "key": self.api_key,
            "videoCategoryId": "10",  # Music category
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
        """Get detailed info for videos including duration"""
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
        """Parse ISO 8601 duration to readable format"""
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
        """Search and return Track objects"""
        search_results = await self.search(query, max_results)
        if not search_results:
            return []
        
        video_ids = [item["id"]["videoId"] for item in search_results]
        video_details = await self.get_video_details(video_ids)
        
        tracks = []
        for item in search_results:
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            details = video_details.get(video_id, {})
            
            track = Track(
                title=snippet.get("title", "Unknown"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                video_id=video_id,
                duration=details.get("duration", "0:00"),
                thumbnail=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                channel=snippet.get("channelTitle", "Unknown"),
                requester=requester,
            )
            tracks.append(track)
        
        return tracks


class AudioSource:
    """Handles audio streaming from YouTube"""
    
    @staticmethod
    async def get_stream_url(video_url: str) -> Optional[str]:
        """Get highest quality audio stream URL using yt-dlp"""
        try:
            import yt_dlp
            
            # Enhanced options for best quality
            ydl_opts = {
                **YT_DLP_OPTIONS,
                'extract_flat': False,
                'format_sort': ['quality', 'res', 'fps', 'hdr:12', 'codec:vp9.2', 'size', 'br', 'asr', 'proto'],
                'format_sort_force': True,
            }
            
            loop = asyncio.get_event_loop()
            
            def extract():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(video_url, download=False)
                    if info:
                        formats = info.get('formats', [])
                        
                        # Priority order for best audio quality
                        audio_formats = []
                        for f in formats:
                            if f.get('acodec') and f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                                audio_formats.append(f)
                        
                        if audio_formats:
                            # Sort by audio bitrate (highest first)
                            audio_formats.sort(key=lambda x: x.get('abr', 0) or 0, reverse=True)
                            return audio_formats[0].get('url')
                        
                        # Fallback to any format with audio
                        for f in formats:
                            if f.get('acodec') and f.get('acodec') != 'none':
                                return f.get('url')
                        
                        # Last resort
                        if formats:
                            return formats[0].get('url')
                    
                    return info.get('url') if info else None
            
            return await loop.run_in_executor(None, extract)
        except Exception as e:
            print(f"Error getting stream URL: {e}")
            return None
    
    @staticmethod
    async def create_source(track: Track, volume: float = 0.5) -> Optional[PCMVolumeTransformer]:
        """Create audio source for a track"""
        stream_url = await AudioSource.get_stream_url(track.youtube_url)
        if not stream_url:
            print(f"Failed to get stream URL for {track.title}")
            return None
        
        track.stream_url = stream_url
        
        # Get the project root directory and build ffmpeg path
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        ffmpeg_path = os.path.join(project_root, "ffmpeg", "ffmpeg-8.0.1-essentials_build", "bin", "ffmpeg.exe")
        
        try:
            source = FFmpegPCMAudio(stream_url, executable=ffmpeg_path, **FFMPEG_OPTIONS)
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
        for state in self.states.values():
            if state.voice_client and state.voice_client.is_connected():
                await state.voice_client.disconnect()
        self.states.clear()
