import os
import random
import asyncio
import discord
from discord import app_commands, FFmpegPCMAudio, PCMVolumeTransformer
from discord.ext import commands
import yt_dlp
import json
from concurrent.futures import ThreadPoolExecutor
from discord.ext import commands
from discord.utils import get
from discord import FFmpegPCMAudio, PCMVolumeTransformer

class Music(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.music_queue = []
        self.current_audio_file = None
        self.repeat = False
        self.last_interaction = None

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()

    async def is_music_channel(interaction: discord.Interaction):
        return interaction.channel.name == 'music'

    @app_commands.check(is_music_channel)
    @app_commands.command(name="play", description="Play music based on a name or random from a folder")
    @app_commands.describe(song_name="The name of the song to play or 'random' for a random song.")
    async def play(self, interaction: discord.Interaction, song_name: str):
        await interaction.response.defer()
        self.last_interaction = interaction
        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel for me to play music.")
            return
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            voice_client = await channel.connect()
        audio_folder = "Songs"
        audio_files = [file for file in os.listdir(audio_folder) if file.endswith((".mp3", ".m4a", ".flac"))]
        if not audio_files:
            await interaction.followup.send("No audio files found in the Songs folder.")
            return
        if song_name.lower() == 'random':
            random.shuffle(audio_files)
        else:
            similar_songs = [file for file in audio_files if song_name.lower() in file.lower()]
            if not similar_songs:
                await interaction.followup.send(f"No songs found similar to '{song_name}'.")
                return
            audio_files = similar_songs
        self.music_queue.extend(audio_files)
        if not voice_client.is_playing():
            await self.play_next(interaction)
        else:
            if "youtube.com" in song_name or "youtu.be" in song_name:  # Check if the input is a YouTube link
                await self.play_youtube_link(interaction, song_name, voice_client)
            else:
                await self.play_local_song(interaction, song_name, voice_client)

    async def play_next(self, interaction):
        if not self.music_queue and not self.repeat:
            await interaction.followup.send("The music queue is empty.")
            return
        if not self.repeat:
            self.current_audio_file = self.music_queue.pop(0)
        audio_path = os.path.join("Songs", self.current_audio_file)
        source = FFmpegPCMAudio(source=audio_path)
        voice_client = interaction.guild.voice_client
        if voice_client:
            voice_client.play(PCMVolumeTransformer(source, volume=0.2), after=self.after_playing)
            await interaction.followup.send(f"Now playing: {self.current_audio_file}")
    def after_playing(self, error):
        if self.last_interaction:
            if not self.repeat:
                coroutine = self.play_next(self.last_interaction)
            else:
                coroutine = self.start_repeat(self.last_interaction)
            
            future = asyncio.run_coroutine_threadsafe(coroutine, self.client.loop)
            try:
                future.result()
            except Exception as e:
                print(f'Error when trying to play next song: {e}')
            if error:
                print(f'Error: {error}')
            else:
                print(f'Finished playing {self.current_audio_file}')

    @app_commands.check(is_music_channel)
    @app_commands.command(name="skip", description="Skip the current song")
    async def skip(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("Skipping to the next song.")
        else:
            await interaction.response.send_message("I'm not playing any music.")

    @app_commands.check(is_music_channel)
    @app_commands.command(name="volume", description="Set the audio volume")
    async def volume(self, interaction: discord.Interaction, volume: float):
        await interaction.response.defer()
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.source:
            voice_client.source.volume = volume
            await interaction.followup.send(f"Volume set to {volume:.2f}")
        else:
            await interaction.followup.send("No music is currently playing.")

    @app_commands.check(is_music_channel)
    @app_commands.command(name="pause", description="Pause the music")
    async def pause(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("Music paused.")
        else:
            await interaction.response.send_message("I'm not playing any music or music is already paused.")

    @app_commands.check(is_music_channel)
    @app_commands.command(name="resume", description="Resume the music")
    async def resume(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("Music resumed.")
        else:
            await interaction.response.send_message("I'm not playing any music or music is not paused.")

    @app_commands.check(is_music_channel)
    @app_commands.command(name="stop", description="Stop the music and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            self.music_queue.clear()  # Clear the music queue
            self.repeat = False  # Turn off repeat
            await interaction.response.send_message("Music stopped and queue cleared.")
        else:
            await interaction.response.send_message("I'm not playing any music.")

    @app_commands.check(is_music_channel)
    @app_commands.command(name="repeat", description="Toggle repeat for the current song")
    async def repeat(self, interaction: discord.Interaction):
        self.repeat = not self.repeat
        message = "Repeat is now enabled." if self.repeat else "Repeat is now disabled."
        await interaction.response.send_message(message)
    async def start_repeat(self, interaction):
        if self.current_audio_file:
            await self.play_next(interaction)

    @app_commands.check(is_music_channel)
    @app_commands.command(name="queue", description="Show the music queue")
    async def queue(self, interaction: discord.Interaction):
        if not self.music_queue:
            await interaction.response.send_message("The music queue is empty.")
            return
        queue_text = "\n".join(f"{index + 1}. {song}" for index, song in enumerate(self.music_queue))
        await interaction.response.send_message(f"Music Queue:\n{queue_text}")

async def setup(client):
    await client.add_cog(Music(client))
    print("Music Online")

