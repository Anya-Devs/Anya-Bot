"""
Music Cog - Voice channel music playback with YouTube integration
Features: Select menu UI, vote-based controls, control panel
"""

import asyncio
import os
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.cogs.music import (
    MusicStateManager,
    MusicEmbed,
    AudioSource,
    Track,
    GuildMusicState,
)
from data.local.const import primary_color


class TrackSelectMenu(discord.ui.Select):
    """Dropdown menu for selecting multiple tracks from search results"""
    
    def __init__(self, tracks: list[Track], cog: "Music"):
        self.tracks = tracks
        self.cog = cog
        
        options = []
        for i, track in enumerate(tracks[:10], 1):
            title = track.title[:45] + "..." if len(track.title) > 45 else track.title
            description = f"{track.duration} • {track.channel[:25]}"
            
            options.append(
                discord.SelectOption(
                    label=f"{i}. {title}",
                    description=description,
                    value=str(i - 1)
                )
            )
        
        super().__init__(
            placeholder="Select songs to add (can pick multiple)...",
            min_values=1,
            max_values=len(options),  # Allow selecting all tracks
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        try:
            # Auto-join functionality
            voice_channel = None
            if interaction.user.voice and interaction.user.voice.channel:
                voice_channel = interaction.user.voice.channel
            else:
                for channel in interaction.guild.voice_channels:
                    if interaction.user in channel.members:
                        voice_channel = channel
                        break
                
                if not voice_channel:
                    return await interaction.response.send_message(
                        embed=MusicEmbed.error("Please join a voice channel first!"),
                        ephemeral=True
                    )
            
            await interaction.response.defer()
            
            # Delete the search message immediately
            try:
                await interaction.message.delete()
            except:
                pass
            
            state = self.cog.manager.get_state(interaction.guild.id)
            
            # Auto-connect to voice channel
            if not state.voice_client or not state.voice_client.is_connected():
                try:
                    state.voice_client = await voice_channel.connect()
                except Exception as e:
                    return await interaction.followup.send(
                        embed=MusicEmbed.error(f"Failed to connect: {str(e)}"),
                        ephemeral=True
                    )
            
            # Add all selected tracks to queue
            added_tracks = []
            for value in self.values:
                track_index = int(value)
                selected_track = self.tracks[track_index]
                state.queue.append(selected_track)
                added_tracks.append(selected_track)
            
            # Create summary embed
            if len(added_tracks) == 1:
                embed = MusicEmbed.added_to_queue(added_tracks[0], len(state.queue))
            else:
                embed = discord.Embed(
                    title=f"✅ Added {len(added_tracks)} songs to queue",
                    description="\n".join([f"• **{t.title[:40]}**" for t in added_tracks[:5]]) + 
                               (f"\n*...and {len(added_tracks) - 5} more*" if len(added_tracks) > 5 else ""),
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Queue now has {len(state.queue)} tracks")
            
            # Start playing if not already
            if not state.voice_client.is_playing() and not state.is_paused:
                await self.cog.play_next(interaction.guild, interaction.channel)
            else:
                await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in TrackSelectMenu callback: {e}")
            try:
                await interaction.followup.send(
                    embed=MusicEmbed.error("An error occurred while adding tracks to queue."),
                    ephemeral=True
                )
            except:
                pass


class TrackSelectView(discord.ui.View):
    """View containing the track selection dropdown"""
    
    def __init__(self, tracks: list[Track], cog: "Music", requester: discord.Member):
        super().__init__(timeout=60)
        self.requester = requester
        self.add_item(TrackSelectMenu(tracks, cog))
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "Only the person who searched can select a track!",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self):
        for item in self.children:
            item.disabled = True


class MusicControlView(discord.ui.View):
    """Control panel for music playback with vote-based buttons"""
    
    def __init__(self, cog: "Music", guild_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self._update_button_styles()
    
    def _is_in_voice(self, interaction: discord.Interaction) -> bool:
        """Check if user is in the bot's voice channel"""
        state = self.cog.manager.get_state(self.guild_id)
        if not state.voice_client or not state.voice_client.channel:
            return False
        return (
            interaction.user.voice and
            interaction.user.voice.channel == state.voice_client.channel
        )
    
    def _get_vc_members(self) -> list[discord.Member]:
        """Get non-bot members in voice channel"""
        state = self.cog.manager.get_state(self.guild_id)
        if not state.voice_client or not state.voice_client.channel:
            return []
        return [m for m in state.voice_client.channel.members if not m.bot]
    
    async def _check_voice(self, interaction: discord.Interaction) -> bool:
        if not self._is_in_voice(interaction):
            await interaction.response.send_message(
                content="❌ `Join the voice channel to use controls`",
                ephemeral=True
            )
            return False
        return True
    
    def _update_button_styles(self):
        """Update button colors based on current state"""
        state = self.cog.manager.get_state(self.guild_id)
        
        # Update pause/resume button color
        for item in self.children:
            if item.custom_id == "music:pause_resume":
                item.style = discord.ButtonStyle.success if state.is_paused else discord.ButtonStyle.primary
            elif item.custom_id == "music:loop":
                if state.loop_mode == "track":
                    item.style = discord.ButtonStyle.success
                elif state.loop_mode == "queue":
                    item.style = discord.ButtonStyle.primary
                else:
                    item.style = discord.ButtonStyle.secondary
    
    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary, custom_id="music:pause_resume", row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        
        if state.is_paused:
            if state.voice_client:
                state.voice_client.resume()
            state.is_paused = False
            await interaction.response.send_message(
                content="▶️ `Resumed`",
                ephemeral=True
            )
        else:
            if state.voice_client:
                state.voice_client.pause()
            state.is_paused = True
            await interaction.response.send_message(
                content="⏸️ `Paused`",
                ephemeral=True
            )
        
        await self.cog.update_control_panel(state)
    
    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="music:vote_skip", row=0)
    async def vote_skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        members = self._get_vc_members()
        required = max(1, len(members) // 2)
        
        if len(members) == 1:
            state.voice_client.stop()
            await interaction.response.send_message(
                content="⏭️ `Skipped`",
                ephemeral=True
            )
            return
        
        if state.has_voted("skip", interaction.user.id):
            state.remove_vote("skip", interaction.user.id)
            current = state.get_vote_count("skip")
            await interaction.response.send_message(
                content=f"🗳️ Vote removed • `{current}/{required}` to skip",
                ephemeral=True
            )
        else:
            current = state.add_vote("skip", interaction.user.id)
            
            if current >= required:
                state.clear_votes()
                state.voice_client.stop()
                await interaction.response.send_message(
                    content="⏭️ `Vote passed - Skipping`",
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    content=f"🗳️ Voted to skip • `{current}/{required}` needed",
                    ephemeral=True
                )
    
    @discord.ui.button(emoji="🔁", style=discord.ButtonStyle.secondary, custom_id="music:loop", row=0)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        
        modes = ["off", "track", "queue"]
        mode_names = {"off": "➡️ `Off`", "track": "🔂 `Track`", "queue": "🔁 `Queue`"}
        
        current_index = modes.index(state.loop_mode)
        state.loop_mode = modes[(current_index + 1) % len(modes)]
        
        await interaction.response.send_message(
            content=f"Loop: {mode_names[state.loop_mode]}",
            ephemeral=True
        )
        await self.cog.update_control_panel(state)
    
    @discord.ui.button(emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="music:shuffle", row=0)
    async def shuffle(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        
        if len(state.queue) < 2:
            return await interaction.response.send_message(
                content="❌ `Need 2+ tracks to shuffle`",
                ephemeral=True
            )
        
        import random
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = type(state.queue)(queue_list)
        
        await interaction.response.send_message(
            content=f"🔀 `Shuffled {len(state.queue)} tracks`",
            ephemeral=True
        )
    
    @discord.ui.button(emoji="📜", style=discord.ButtonStyle.secondary, custom_id="music:queue", row=0)
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.cog.manager.get_state(self.guild_id)
        await interaction.response.send_message(
            embed=MusicEmbed.queue_embed(state),
            ephemeral=True
        )
    
    @discord.ui.button(emoji="🔉", style=discord.ButtonStyle.secondary, custom_id="music:vol_down", row=1)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        state.volume = max(0.0, state.volume - 0.1)
        
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        
        await interaction.response.send_message(
            content=f"🔉 Volume: `{int(state.volume * 100)}%`",
            ephemeral=True
        )
        await self.cog.update_control_panel(state)
    
    @discord.ui.button(emoji="🔊", style=discord.ButtonStyle.secondary, custom_id="music:vol_up", row=1)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        state.volume = min(2.0, state.volume + 0.1)
        
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        
        await interaction.response.send_message(
            content=f"🔊 Volume: `{int(state.volume * 100)}%`",
            ephemeral=True
        )
        await self.cog.update_control_panel(state)
    
    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="music:vote_stop", row=1)
    async def vote_stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        members = self._get_vc_members()
        required = max(1, len(members) // 2)
        
        if len(members) == 1:
            state.queue.clear()
            state.voice_client.stop()
            await state.voice_client.disconnect()
            await interaction.response.send_message(
                embed=MusicEmbed.success("⏹️ Stopped and disconnected!"),
                ephemeral=True
            )
            return
        
        if state.has_voted("stop", interaction.user.id):
            state.remove_vote("stop", interaction.user.id)
            current = state.get_vote_count("stop")
            await interaction.response.send_message(
                embed=MusicEmbed.vote_status("stop", current, required, "stop playback"),
                ephemeral=True
            )
        else:
            current = state.add_vote("stop", interaction.user.id)
            
            if current >= required:
                state.clear_votes()
                state.queue.clear()
                state.voice_client.stop()
                await state.voice_client.disconnect()
                await interaction.response.send_message(
                    embed=MusicEmbed.success("⏹️ Vote passed! Stopping..."),
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    embed=MusicEmbed.vote_status("stop", current, required, "stop playback"),
                    ephemeral=True
                )
    
    @discord.ui.button(emoji="❌", style=discord.ButtonStyle.danger, custom_id="music:disconnect", row=1)
    async def disconnect(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check_voice(interaction):
            return
        
        state = self.cog.manager.get_state(self.guild_id)
        members = self._get_vc_members()
        required = max(1, len(members) // 2)
        
        if len(members) == 1:
            state.queue.clear()
            if state.voice_client:
                state.voice_client.stop()
                await state.voice_client.disconnect()
            if state.control_message:
                try:
                    await state.control_message.delete()
                except:
                    pass
            self.cog.manager.remove_state(self.guild_id)
            await interaction.response.send_message(
                embed=MusicEmbed.success("👋 Disconnected!"),
                ephemeral=True
            )
            return
        
        if state.has_voted("stop", interaction.user.id):
            state.remove_vote("stop", interaction.user.id)
            current = state.get_vote_count("stop")
            await interaction.response.send_message(
                embed=MusicEmbed.vote_status("disconnect", current, required, "disconnect"),
                ephemeral=True
            )
        else:
            current = state.add_vote("stop", interaction.user.id)
            
            if current >= required:
                state.queue.clear()
                if state.voice_client:
                    state.voice_client.stop()
                    await state.voice_client.disconnect()
                if state.control_message:
                    try:
                        await state.control_message.delete()
                    except:
                        pass
                self.cog.manager.remove_state(self.guild_id)
                await interaction.response.send_message(
                    embed=MusicEmbed.success("👋 Vote passed! Disconnecting..."),
                    ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    embed=MusicEmbed.vote_status("disconnect", current, required, "disconnect"),
                    ephemeral=True
                )
    


class Music(commands.Cog):
    """🎵 Music commands for voice channel playback"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.manager = MusicStateManager()
        self.inactivity_check.start()
    
    def cog_unload(self):
        self.inactivity_check.cancel()
        asyncio.create_task(self.manager.cleanup())
    
    @tasks.loop(minutes=5)
    async def inactivity_check(self):
        """Disconnect from inactive voice channels"""
        for guild_id, state in list(self.manager.states.items()):
            if state.voice_client and state.voice_client.is_connected():
                if not state.voice_client.is_playing() and not state.is_paused:
                    if (datetime.now() - state.last_activity).total_seconds() > 300:
                        await state.voice_client.disconnect()
                        if state.control_message:
                            try:
                                await state.control_message.delete()
                            except:
                                pass
                        self.manager.remove_state(guild_id)
    
    @inactivity_check.before_loop
    async def before_inactivity_check(self):
        await self.bot.wait_until_ready()
    
    async def play_next(self, guild: discord.Guild, channel: discord.TextChannel):
        """Play the next track in queue"""
        state = self.manager.get_state(guild.id)
        
        if state.loop_mode == "track" and state.current_track:
            pass
        elif state.queue:
            if state.loop_mode == "queue" and state.current_track:
                state.queue.append(state.current_track)
            state.current_track = state.queue.popleft()
        else:
            state.current_track = None
            if state.control_message:
                embed = discord.Embed(
                    title="🎵 Queue Empty",
                    description="No more tracks in queue. Use `/play` to add more!",
                    color=primary_color()
                )
                try:
                    await state.control_message.edit(embed=embed, view=None)
                except:
                    pass
            return
        
        state.clear_votes()
        state.last_activity = datetime.now()
        
        source = await AudioSource.create_source(state.current_track, state.volume)
        if not source:
            await channel.send(
                embed=MusicEmbed.error(f"Failed to load: {state.current_track.title}"),
                delete_after=10
            )
            await self.play_next(guild, channel)
            return
        
        def after_playing(error):
            if error:
                print(f"Player error: {error}")
            asyncio.run_coroutine_threadsafe(
                self.play_next(guild, channel),
                self.bot.loop
            )
        
        state.voice_client.play(source, after=after_playing)
        
        await self.update_control_panel(state, channel)
    
    async def update_control_panel(self, state: GuildMusicState, channel: discord.TextChannel = None):
        """Update or create the control panel message"""
        if not state.current_track:
            return
        
        embed = MusicEmbed.now_playing(state.current_track, state)
        view = MusicControlView(self, state.guild_id)
        
        try:
            if state.control_message:
                await state.control_message.edit(embed=embed, view=view)
            elif channel:
                state.control_message = await channel.send(embed=embed, view=view)
        except discord.NotFound:
            if channel:
                state.control_message = await channel.send(embed=embed, view=view)
        except Exception as e:
            print(f"Error updating control panel: {e}")
    
    @commands.hybrid_command(name="play", aliases=["p"], description="Search and play a song")
    @app_commands.describe(query="Song name or YouTube URL to search for")
    async def play(self, ctx: commands.Context, *, query: str):
        """Search for a song and select from results - auto-joins voice channel"""
        # Auto-join functionality - find user's voice channel
        voice_channel = None
        if ctx.author.voice and ctx.author.voice.channel:
            voice_channel = ctx.author.voice.channel
        else:
            # Try to find the user in any voice channel in the guild
            for channel in ctx.guild.voice_channels:
                if ctx.author in channel.members:
                    voice_channel = channel
                    break
            
            if not voice_channel:
                return await ctx.reply(
                    embed=MusicEmbed.error("🎵 Please join a voice channel first!"),
                    mention_author=False
                )
        
        await ctx.defer()
        
        # Auto-connect to voice channel
        state = self.manager.get_state(ctx.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            try:
                state.voice_client = await voice_channel.connect()
                await ctx.send(
                    embed=MusicEmbed.success(f"🎵 Connected to **{voice_channel.name}**!")
                )
            except Exception as e:
                return await ctx.send(
                    embed=MusicEmbed.error(f"❌ Failed to connect to voice channel: {str(e)}")
                )
        
        tracks = await self.manager.youtube.search_tracks(query, ctx.author)
        
        if not tracks:
            return await ctx.send(
                embed=MusicEmbed.error("🔍 No results found. Try a different search term!")
            )
        
        embed = MusicEmbed.search_results(tracks, query)
        view = TrackSelectView(tracks, self, ctx.author)
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message
    
    @commands.hybrid_command(name="playnow", aliases=["pn"], description="Play a song immediately (skips queue)")
    @app_commands.describe(query="Song name or YouTube URL")
    async def playnow(self, ctx: commands.Context, *, query: str):
        """Play a song immediately, adding current track back to queue - auto-joins voice channel"""
        # Auto-join functionality - find user's voice channel
        voice_channel = None
        if ctx.author.voice and ctx.author.voice.channel:
            voice_channel = ctx.author.voice.channel
        else:
            # Try to find the user in any voice channel in the guild
            for channel in ctx.guild.voice_channels:
                if ctx.author in channel.members:
                    voice_channel = channel
                    break
            
            if not voice_channel:
                return await ctx.reply(
                    embed=MusicEmbed.error("🎵 Please join a voice channel first!"),
                    mention_author=False
                )
        
        await ctx.defer()
        
        # Auto-connect to voice channel
        state = self.manager.get_state(ctx.guild.id)
        if not state.voice_client or not state.voice_client.is_connected():
            try:
                state.voice_client = await voice_channel.connect()
                await ctx.send(
                    embed=MusicEmbed.success(f"🎵 Connected to **{voice_channel.name}**!")
                )
            except Exception as e:
                return await ctx.send(
                    embed=MusicEmbed.error(f"❌ Failed to connect to voice channel: {str(e)}")
                )
        
        tracks = await self.manager.youtube.search_tracks(query, ctx.author, max_results=1)
        
        if not tracks:
            return await ctx.send(
                embed=MusicEmbed.error("🔍 No results found. Try a different search term!")
            )
        
        track = tracks[0]
        
        if state.current_track:
            state.queue.appendleft(state.current_track)
        
        state.current_track = track
        
        if state.voice_client.is_playing():
            state.voice_client.stop()
        else:
            await self.play_next(ctx.guild, ctx.channel)
        
        await ctx.send(
            embed=MusicEmbed.success(f"🎵 Now playing: **{track.title}**")
        )
    
    @commands.hybrid_command(name="skip", description="Vote to skip the current track")
    async def skip(self, ctx: commands.Context):
        """Vote to skip the current track"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.voice_client or not state.voice_client.is_playing():
            return await ctx.reply(
                embed=MusicEmbed.error("Nothing is playing!"),
                mention_author=False
            )
        
        if not ctx.author.voice or ctx.author.voice.channel != state.voice_client.channel:
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        members = [m for m in state.voice_client.channel.members if not m.bot]
        required = max(1, len(members) // 2)
        
        if len(members) == 1:
            state.voice_client.stop()
            return await ctx.reply(
                embed=MusicEmbed.success("⏭️ Skipped!"),
                mention_author=False
            )
        
        current = state.add_vote("skip", ctx.author.id)
        
        if current >= required:
            state.clear_votes()
            state.voice_client.stop()
            await ctx.reply(
                embed=MusicEmbed.success("⏭️ Vote passed! Skipping..."),
                mention_author=False
            )
        else:
            await ctx.reply(
                embed=MusicEmbed.vote_status("skip", current, required, "skip the track"),
                mention_author=False
            )
    
    @commands.hybrid_command(name="stop", description="Vote to stop playback and clear queue")
    async def stop(self, ctx: commands.Context):
        """Vote to stop playback and clear the queue"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.voice_client:
            return await ctx.reply(
                embed=MusicEmbed.error("Not connected to a voice channel!"),
                mention_author=False
            )
        
        if not ctx.author.voice or ctx.author.voice.channel != state.voice_client.channel:
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        members = [m for m in state.voice_client.channel.members if not m.bot]
        required = max(1, len(members) // 2)
        
        if len(members) == 1:
            state.queue.clear()
            state.voice_client.stop()
            await state.voice_client.disconnect()
            if state.control_message:
                try:
                    await state.control_message.delete()
                except:
                    pass
            self.manager.remove_state(ctx.guild.id)
            return await ctx.reply(
                embed=MusicEmbed.success("⏹️ Stopped and disconnected!"),
                mention_author=False
            )
        
        current = state.add_vote("stop", ctx.author.id)
        
        if current >= required:
            state.clear_votes()
            state.queue.clear()
            state.voice_client.stop()
            await state.voice_client.disconnect()
            if state.control_message:
                try:
                    await state.control_message.delete()
                except:
                    pass
            self.manager.remove_state(ctx.guild.id)
            await ctx.reply(
                embed=MusicEmbed.success("⏹️ Vote passed! Stopping..."),
                mention_author=False
            )
        else:
            await ctx.reply(
                embed=MusicEmbed.vote_status("stop", current, required, "stop playback"),
                mention_author=False
            )
    
    @commands.hybrid_command(name="forcestop", aliases=["fstop"], description="Force stop music (Admin only)")
    @commands.has_permissions(manage_guild=True)
    async def forcestop(self, ctx: commands.Context):
        """Force stop music and disconnect - Admin only"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.voice_client:
            return await ctx.reply(
                embed=MusicEmbed.error("Not connected to a voice channel!"),
                mention_author=False
            )
        
        state.queue.clear()
        state.clear_votes()
        
        if state.voice_client.is_playing():
            state.voice_client.stop()
        
        await state.voice_client.disconnect()
        
        if state.control_message:
            try:
                await state.control_message.delete()
            except:
                pass
        
        self.manager.remove_state(ctx.guild.id)
        
        await ctx.reply(
            embed=MusicEmbed.success("🛑 Force stopped by admin"),
            mention_author=False
        )
    
    @forcestop.error
    async def forcestop_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply(
                embed=MusicEmbed.error("You need **Manage Server** permission to use this command!"),
                mention_author=False
            )
    
    @commands.hybrid_command(name="pause", description="Pause the current track")
    async def pause(self, ctx: commands.Context):
        """Pause the current track"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.voice_client or not state.voice_client.is_playing():
            return await ctx.reply(
                embed=MusicEmbed.error("Nothing is playing!"),
                mention_author=False
            )
        
        if not ctx.author.voice or ctx.author.voice.channel != state.voice_client.channel:
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        state.voice_client.pause()
        state.is_paused = True
        await ctx.reply(
            embed=MusicEmbed.success("⏸️ Paused"),
            mention_author=False
        )
        await self.update_control_panel(state)
    
    @commands.hybrid_command(name="resume", description="Resume the paused track")
    async def resume(self, ctx: commands.Context):
        """Resume the paused track"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.is_paused:
            return await ctx.reply(
                embed=MusicEmbed.error("Playback is not paused!"),
                mention_author=False
            )
        
        if not ctx.author.voice or ctx.author.voice.channel != state.voice_client.channel:
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        state.voice_client.resume()
        state.is_paused = False
        await ctx.reply(
            embed=MusicEmbed.success("▶️ Resumed"),
            mention_author=False
        )
        await self.update_control_panel(state)
    
    @commands.hybrid_command(name="queue", aliases=["qu"], description="View the current queue")
    async def queue(self, ctx: commands.Context):
        """View the current music queue"""
        state = self.manager.get_state(ctx.guild.id)
        
        embed = MusicEmbed.queue_embed(state)
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.hybrid_command(name="nowplaying", aliases=["np"], description="Show the currently playing track")
    async def nowplaying(self, ctx: commands.Context):
        """Show the currently playing track"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.current_track:
            return await ctx.reply(
                embed=MusicEmbed.error("Nothing is playing!"),
                mention_author=False
            )
        
        embed = MusicEmbed.now_playing(state.current_track, state)
        await ctx.reply(embed=embed, mention_author=False)
    
    @commands.hybrid_command(name="volume", aliases=["vol"], description="Set the volume (0-200)")
    @app_commands.describe(level="Volume level (0-200)")
    async def volume(self, ctx: commands.Context, level: int):
        """Set the playback volume"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not ctx.author.voice or (state.voice_client and ctx.author.voice.channel != state.voice_client.channel):
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        if level < 0 or level > 200:
            return await ctx.reply(
                embed=MusicEmbed.error("Volume must be between 0 and 200!"),
                mention_author=False
            )
        
        state.volume = level / 100
        if state.voice_client and state.voice_client.source:
            state.voice_client.source.volume = state.volume
        
        await ctx.reply(
            embed=MusicEmbed.success(f"🔊 Volume set to {level}%"),
            mention_author=False
        )
        await self.update_control_panel(state)
    
    @commands.hybrid_command(name="shuffle", description="Shuffle the queue")
    async def shuffle(self, ctx: commands.Context):
        """Shuffle the current queue"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not ctx.author.voice or (state.voice_client and ctx.author.voice.channel != state.voice_client.channel):
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        if len(state.queue) < 2:
            return await ctx.reply(
                embed=MusicEmbed.error("Not enough tracks to shuffle!"),
                mention_author=False
            )
        
        import random
        queue_list = list(state.queue)
        random.shuffle(queue_list)
        state.queue = type(state.queue)(queue_list)
        
        await ctx.reply(
            embed=MusicEmbed.success(f"🔀 Shuffled {len(state.queue)} tracks!"),
            mention_author=False
        )
    
    @commands.hybrid_command(name="loop", description="Toggle loop mode (off/track/queue)")
    async def loop(self, ctx: commands.Context):
        """Toggle loop mode"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not ctx.author.voice or (state.voice_client and ctx.author.voice.channel != state.voice_client.channel):
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        modes = ["off", "track", "queue"]
        mode_names = {"off": "➡️ Loop Off", "track": "🔂 Loop Track", "queue": "🔁 Loop Queue"}
        
        current_index = modes.index(state.loop_mode)
        state.loop_mode = modes[(current_index + 1) % len(modes)]
        
        await ctx.reply(
            embed=MusicEmbed.success(f"Loop mode: {mode_names[state.loop_mode]}"),
            mention_author=False
        )
        await self.update_control_panel(state)
    
    @commands.hybrid_command(name="clearqueue", description="Clear the queue")
    async def clearqueue(self, ctx: commands.Context):
        """Clear the music queue"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not ctx.author.voice or (state.voice_client and ctx.author.voice.channel != state.voice_client.channel):
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        count = len(state.queue)
        state.queue.clear()
        
        await ctx.reply(
            embed=MusicEmbed.success(f"🗑️ Cleared {count} tracks from queue!"),
            mention_author=False
        )
    
    @commands.hybrid_command(name="remove", description="Remove a track from queue")
    @app_commands.describe(position="Position in queue to remove (1-based)")
    async def remove(self, ctx: commands.Context, position: int):
        """Remove a track from the queue by position"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not ctx.author.voice or (state.voice_client and ctx.author.voice.channel != state.voice_client.channel):
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        if position < 1 or position > len(state.queue):
            return await ctx.reply(
                embed=MusicEmbed.error(f"Invalid position! Queue has {len(state.queue)} tracks."),
                mention_author=False
            )
        
        queue_list = list(state.queue)
        removed = queue_list.pop(position - 1)
        state.queue = type(state.queue)(queue_list)
        
        await ctx.reply(
            embed=MusicEmbed.success(f"🗑️ Removed **{removed.title}** from queue"),
            mention_author=False
        )
    
    @commands.hybrid_command(name="join", description="Join your voice channel")
    async def join(self, ctx: commands.Context):
        """Join the user's voice channel"""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in a voice channel!"),
                mention_author=False
            )
        
        state = self.manager.get_state(ctx.guild.id)
        
        if state.voice_client and state.voice_client.is_connected():
            await state.voice_client.move_to(ctx.author.voice.channel)
        else:
            state.voice_client = await ctx.author.voice.channel.connect()
        
        await ctx.reply(
            embed=MusicEmbed.success(f"🔊 Joined {ctx.author.voice.channel.mention}"),
            mention_author=False
        )
    
    @commands.hybrid_command(name="leave", aliases=["disconnect", "dc"], description="Leave the voice channel")
    async def leave(self, ctx: commands.Context):
        """Leave the voice channel"""
        state = self.manager.get_state(ctx.guild.id)
        
        if not state.voice_client or not state.voice_client.is_connected():
            return await ctx.reply(
                embed=MusicEmbed.error("Not connected to a voice channel!"),
                mention_author=False
            )
        
        if not ctx.author.voice or ctx.author.voice.channel != state.voice_client.channel:
            return await ctx.reply(
                embed=MusicEmbed.error("You must be in the voice channel!"),
                mention_author=False
            )
        
        members = [m for m in state.voice_client.channel.members if not m.bot]
        required = max(1, len(members) // 2)
        
        if len(members) == 1:
            state.queue.clear()
            await state.voice_client.disconnect()
            if state.control_message:
                try:
                    await state.control_message.delete()
                except:
                    pass
            self.manager.remove_state(ctx.guild.id)
            return await ctx.reply(
                embed=MusicEmbed.success("👋 Disconnected!"),
                mention_author=False
            )
        
        current = state.add_vote("stop", ctx.author.id)
        
        if current >= required:
            state.queue.clear()
            await state.voice_client.disconnect()
            if state.control_message:
                try:
                    await state.control_message.delete()
                except:
                    pass
            self.manager.remove_state(ctx.guild.id)
            await ctx.reply(
                embed=MusicEmbed.success("👋 Vote passed! Disconnecting..."),
                mention_author=False
            )
        else:
            await ctx.reply(
                embed=MusicEmbed.vote_status("disconnect", current, required, "disconnect"),
                mention_author=False
            )
    
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Handle voice state updates for auto-disconnect"""
        if member.bot:
            return
        
        state = self.manager.states.get(member.guild.id)
        if not state or not state.voice_client:
            return
        
        if before.channel == state.voice_client.channel and after.channel != state.voice_client.channel:
            members = [m for m in state.voice_client.channel.members if not m.bot]
            if len(members) == 0:
                state.queue.clear()
                await state.voice_client.disconnect()
                if state.control_message:
                    try:
                        await state.control_message.delete()
                    except:
                        pass
                self.manager.remove_state(member.guild.id)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Automatically handle cookies.txt uploads"""
        if message.author.bot or not message.guild:
            return
        
        # Check if user has manage_guild permission
        if not message.author.guild_permissions.manage_guild:
            return
        
        if not message.attachments:
            return
        
        for attachment in message.attachments:
            if attachment.filename.lower() == "cookies.txt":
                from utils.cogs.music import AudioSource
                
                cookies_path = AudioSource._get_cookies_file()
                if not cookies_path:
                    continue
                
                try:
                    import os
                    cookies_data = await attachment.read()
                    cookies_text = cookies_data.decode('utf-8')
                    
                    os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
                    with open(cookies_path, 'w', encoding='utf-8') as f:
                        f.write(cookies_text)
                    
                    await message.reply(
                        embed=MusicEmbed.success("✅ YouTube cookies updated successfully from uploaded file!"),
                        mention_author=False
                    )
                    break  # Only process one cookies.txt per message
                except Exception as e:
                    await message.reply(
                        embed=MusicEmbed.error(f"Failed to save cookies: {str(e)}"),
                        mention_author=False
                    )
                    break


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
