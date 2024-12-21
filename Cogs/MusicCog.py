import os
import random
import asyncio
import discord
from discord import app_commands, FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
from discord.utils import get
from yt_dlp import YoutubeDL

class Music(commands.Cog):
    def __init__(self, client: commands.Bot):
        self.client = client
        self.music_queue: list[str] = []
        self.current_audio_file: str | None = None
        self.repeat: bool = False
        self.last_interaction: discord.Interaction | None = None

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()

    @staticmethod
    async def is_music_channel(interaction: discord.Interaction) -> bool:
        return interaction.channel.name == 'music'

    @app_commands.check(is_music_channel)
    @app_commands.command(name="play_youtube", description="Play music from YouTube")
    @app_commands.describe(youtube_url="The YouTube URL of the song to play")
    async def play_youtube_link(self, interaction: discord.Interaction, youtube_url: str):
        await interaction.response.defer()
        
        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first!")
            return
            
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            voice_client = await channel.connect()
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'extractaudio': True,
            'forcejson': True,
            'noplaylist': True,
        }

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)
                url = info['url']
                title = info.get('title', 'Unknown title')

            source = FFmpegPCMAudio(url, executable="ffmpeg")
            voice_client.play(
                source, 
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(interaction), 
                    self.client.loop
                ) if e is None else print(f"Error in playback: {e}")
            )

            await interaction.followup.send(f"Now playing: **{title}**")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")

    async def play_local_song(self, interaction: discord.Interaction, song_name: str):
        if not self.music_queue:
            await interaction.followup.send("No songs in queue.")
            return

        voice_client = interaction.guild.voice_client
        if not voice_client:
            await interaction.followup.send("Not connected to a voice channel.")
            return

        song_path = os.path.join("Songs", self.music_queue[0])
        self.current_audio_file = self.music_queue.pop(0)

        try:
            source = FFmpegPCMAudio(song_path, executable="ffmpeg")
            voice_client.play(
                source,
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self.play_next(interaction),
                    self.client.loop
                ) if e is None else print(f"Error in playback: {e}")
            )
            await interaction.followup.send(f"Now playing: **{self.current_audio_file}**")
        except Exception as e:
            await interaction.followup.send(f"An error occurred: {str(e)}")
            await self.play_next(interaction)

    async def play_next(self, interaction: discord.Interaction):
        if self.repeat and self.current_audio_file:
            self.music_queue.append(self.current_audio_file)
        
        if self.music_queue:
            await self.play_local_song(interaction, self.music_queue[0])
        else:
            await interaction.followup.send("Queue is empty. Add more songs!")

    @app_commands.check(is_music_channel)
    @app_commands.command(name="play", description="Play music from local files")
    @app_commands.describe(song_name="The name of the song to play or 'random' for a random song")
    async def play(self, interaction: discord.Interaction, song_name: str):
        await interaction.response.defer()
        self.last_interaction = interaction

        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel first!")
            return

        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            voice_client = await channel.connect()

        if "youtube.com" in song_name or "youtu.be" in song_name:
            await self.play_youtube_link(interaction, song_name)
            return

        audio_folder = "Songs"
        audio_files = [file for file in os.listdir(audio_folder) 
                      if file.endswith((".mp3", ".m4a", ".flac"))]
        
        if not audio_files:
            await interaction.followup.send("No audio files found in the Songs folder.")
            return

        if song_name.lower() == 'random':
            random.shuffle(audio_files)
        else:
            similar_songs = [file for file in audio_files if song_name.lower() in file.lower()]
            if not similar_songs:
                await interaction.followup.send(f"No songs found matching '{song_name}'.")
                return
            audio_files = similar_songs

        self.music_queue.extend(audio_files)
        
        if not voice_client.is_playing():
            await self.play_next(interaction)
        else:
            await interaction.followup.send(f"Added {len(audio_files)} song(s) to the queue!")

async def setup(client: commands.Bot):
    await client.add_cog(Music(client))
    print("Music Cog is now online!")