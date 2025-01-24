import os
import asyncio
import discord
import traceback
from discord import app_commands, FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
from yt_dlp import YoutubeDL
from typing import Optional
from enum import Enum

class RepeatMode(Enum):
    NONE = 0
    TRACK = 1
    QUEUE = 2

class Track:
    def __init__(self, source: str, title: str, url: str, requester: discord.Member):
        self.source = source
        self.title = title
        self.url = url
        self.requester = requester

class YTSearchView(discord.ui.View):
    def __init__(self, tracks: list[Track], cog: 'Music', guild_id: int):
        super().__init__(timeout=30)
        self.tracks = tracks
        self.cog = cog
        self.guild_id = guild_id
        self.message = None

        for idx, track in enumerate(tracks):
            btn_label = f"{idx+1}. {track.title[:45]}"
            button = discord.ui.Button(label=btn_label, custom_id=f"track_{idx}")
            button.callback = self.create_callback(idx)
            self.add_item(button)

    def create_callback(self, index: int):
        async def button_callback(interaction: discord.Interaction):
            selected_track = self.tracks[index]
            self.cog.queues.setdefault(self.guild_id, []).append(selected_track)
            
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)
            self.stop()

            await interaction.response.send_message(f"🎵 Added **{selected_track.title}** to queue")
            voice_client = await self.cog._get_voice_client(self.guild_id)
            if voice_client and not voice_client.is_playing():
                await self.cog._play_next(self.guild_id)
            
            if self in self.cog.active_views:
                self.cog.active_views.remove(self)
        return button_callback

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)
        if self in self.cog.active_views:
            self.cog.active_views.remove(self)

class Music(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.queues = {}
        self.current_tracks = {}
        self.repeat_modes = {}
        self.volume_levels = {}
        self.user_last_channel = {}
        self.active_views = []

        if not os.path.exists("Songs"):
            os.makedirs("Songs")

    async def _get_voice_client(self, guild_id: int) -> Optional[discord.VoiceClient]:
        guild = self.client.get_guild(guild_id)
        return guild.voice_client if guild else None

    async def _connect_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.user.voice:
            await interaction.followup.send("❌ You need to be in a voice channel!")
            return None

        voice_client = await self._get_voice_client(interaction.guild_id)
        if voice_client:
            if voice_client.channel != interaction.user.voice.channel:
                await voice_client.move_to(interaction.user.voice.channel)
            return voice_client

        try:
            voice_client = await interaction.user.voice.channel.connect()
            self.user_last_channel[interaction.guild_id] = interaction.channel
            return voice_client
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to connect: {str(e)}")
            return None

    async def _play_next(self, guild_id: int):
        voice_client = await self._get_voice_client(guild_id)
        if not voice_client:
            return

        queue = self.queues.get(guild_id, [])
        repeat_mode = self.repeat_modes.get(guild_id, RepeatMode.NONE)

        if repeat_mode == RepeatMode.TRACK and self.current_tracks.get(guild_id):
            queue.insert(0, self.current_tracks[guild_id])

        if queue:
            track = queue.pop(0)
            self.current_tracks[guild_id] = track

            try:
                # Use FFmpegPCMAudio for better compatibility
                source = FFmpegPCMAudio(
                    track.source,
                    before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                    options="-vn -b:a 128k -ac 2"
                )

                def after_playback(error):
                    if error:
                        print(f"Playback error: {error}")
                    asyncio.run_coroutine_threadsafe(
                        self._play_next(guild_id),
                        self.client.loop
                    )

                voice_client.play(source, after=after_playback)
                voice_client.source = PCMVolumeTransformer(voice_client.source, self.volume_levels.get(guild_id, 0.5))
                
                channel = self.user_last_channel.get(guild_id)
                if channel:
                    await channel.send(f"🎶 Now playing: **{track.title}** (Requested by {track.requester.mention})")

            except Exception as e:
                await self._handle_playback_error(guild_id, f"Failed to play: {str(e)}")
                await self._play_next(guild_id)
        else:
            await self._disconnect_voice(guild_id)

    async def _disconnect_voice(self, guild_id: int):
        voice_client = await self._get_voice_client(guild_id)
        if voice_client:
            await voice_client.disconnect()
            self.current_tracks.pop(guild_id, None)
            self.queues.pop(guild_id, None)
            channel = self.user_last_channel.get(guild_id)
            if channel:
                await channel.send("✅ Queue finished. Disconnecting...")

    async def _handle_playback_error(self, guild_id: int, error: str):
        channel = self.user_last_channel.get(guild_id)
        if channel:
            await channel.send(f"❌ Playback error: {error}")
        await self._play_next(guild_id)

    async def _ytdl_extract(self, url: str, requester: discord.Member) -> Optional[list[Track]]:
        ytdl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'ignoreerrors': True,
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 15,
            'source_address': '0.0.0.0',
            'nocheckcertificate': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'best',
            }],
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.youtube.com/'
            }
        }

        try:
            with YoutubeDL(ytdl_opts) as ytdl:
                data = await asyncio.to_thread(ytdl.extract_info, url, download=False)
                
                if not data:
                    return None

                entries = data.get('entries', [])
                if url.startswith(('ytsearch', 'ytsearch5:')):
                    entries = entries[:5]

                valid_tracks = []
                for entry in entries:
                    if not entry:
                        continue

                    try:
                        track_url = entry.get('url')
                        if not track_url:
                            continue

                        valid_tracks.append(Track(
                            source=track_url,
                            title=entry.get('title', 'Unknown Track'),
                            url=entry.get('webpage_url', url),
                            requester=requester
                        ))
                        
                    except Exception as e:
                        print(f"Failed to process entry: {str(e)}")
                        continue

                return valid_tracks

        except Exception as e:
            print(f"YTDL Error: {str(e)}")
            return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member == self.client.user and not after.channel:
            self.current_tracks.pop(member.guild.id, None)
            self.queues.pop(member.guild.id, None)

    @app_commands.command(name="play", description="Play music from YouTube or local files")
    @app_commands.describe(query="YouTube URL/search query or local file name")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        voice_client = await self._connect_voice(interaction)
        if not voice_client:
            return

        guild_id = interaction.guild_id
        self.volume_levels.setdefault(guild_id, 0.5)

        try:
            # Handle local files
            if not query.startswith(('http://', 'https://')):
                local_files = [f for f in os.listdir("Songs") if f.endswith(('.mp3', '.m4a', '.flac'))]
                matched = [f for f in local_files if query.lower() in f.lower()]
                
                if matched:
                    tracks = [
                        Track(
                            source=os.path.join("Songs", f),
                            title=os.path.splitext(f)[0],
                            url="local-file",
                            requester=interaction.user
                        )
                        for f in matched
                    ]
                    self.queues.setdefault(guild_id, []).extend(tracks)
                    await interaction.followup.send(f"🎵 Added {len(tracks)} local track(s) to queue")
                    if not voice_client.is_playing():
                        await self._play_next(guild_id)
                    return

            # Handle YouTube content
            if query.startswith(('http://', 'https://')):
                tracks = await self._ytdl_extract(query, interaction.user)
            else:
                tracks = await self._ytdl_extract(f"ytsearch5:{query}", interaction.user)

            if not tracks:
                await interaction.followup.send(f"🔍 No results found for '{query}'")
                return

            # Direct URL handling
            if query.startswith(('http://', 'https://')):
                self.queues.setdefault(guild_id, []).extend(tracks)
                await interaction.followup.send(f"🎵 Added **{tracks[0].title}** to queue")
                if not voice_client.is_playing():
                    await self._play_next(guild_id)
                return

            # Search results handling
            view = YTSearchView(tracks, self, guild_id)
            view.message = await interaction.followup.send("🎵 Select a track:", view=view)
            self.active_views.append(view)

        except Exception as e:
            await interaction.followup.send(f"❌ Error processing request: {str(e)}")
            print(f"Play Command Error: {traceback.format_exc()}")

    @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, interaction: discord.Interaction):
        voice_client = await self._get_voice_client(interaction.guild_id)
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭ Skipped current track")
        else:
            await interaction.response.send_message("❌ Nothing is currently playing")

    @app_commands.command(name="stop", description="Stop playback and clear queue")
    async def stop(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        self.queues[guild_id] = []
        voice_client = await self._get_voice_client(guild_id)
        if voice_client:
            voice_client.stop()
            await self._disconnect_voice(guild_id)
        await interaction.response.send_message("⏹ Stopped playback and cleared queue")

    @app_commands.command(name="volume", description="Adjust playback volume (0-100)")
    @app_commands.describe(level="Volume level (0-100)")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        guild_id = interaction.guild_id
        self.volume_levels[guild_id] = level / 100
        voice_client = await self._get_voice_client(guild_id)
        if voice_client and voice_client.source:
            voice_client.source.volume = self.volume_levels[guild_id]
            await interaction.response.send_message(f"🔊 Volume set to {level}%")
        else:
            await interaction.response.send_message("❌ Nothing is currently playing")

    @app_commands.command(name="nowplaying", description="Show current track info")
    async def nowplaying(self, interaction: discord.Interaction):
        track = self.current_tracks.get(interaction.guild_id)
        if track:
            embed = discord.Embed(title="Now Playing", color=0x00ff00)
            embed.add_field(name="Title", value=track.title, inline=False)
            embed.add_field(name="Requested By", value=track.requester.mention)
            embed.add_field(name="URL", value=track.url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("❌ Nothing is currently playing")

async def setup(client: commands.Bot):
    await client.add_cog(Music(client))
    print("🎵 Music Cog loaded!")