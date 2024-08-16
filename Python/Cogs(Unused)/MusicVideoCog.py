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


class Audiobooks(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.audiobook_series = None
        self.current_audiobook = None
        self.current_position = 0
        self.repeat = False
        self.last_interaction = None

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()

    async def is_music_channel(self, interaction: discord.Interaction):
        return interaction.channel.name == 'music'  # Adjust channel name as needed

    async def get_series_folders(self):
        audiobook_path = os.path.join("Audiobooks")
        return [folder for folder in os.listdir(audiobook_path) if os.path.isdir(os.path.join(audiobook_path, folder))]

    @commands.command(name="playbook", description="Play an audiobook series")
    async def play_book(self, interaction: discord.Interaction, series_folder: str = None):
        await interaction.response.defer()
        self.last_interaction = interaction
        if not interaction.user.voice:
            await interaction.followup.send("You need to be in a voice channel for me to play audiobooks.")
            return
        voice_client = interaction.guild.voice_client
        if voice_client is None:
            channel = interaction.user.voice.channel
            voice_client = await channel.connect()
        if not series_folder:
            series_folders = await self.get_series_folders()
            if not series_folders:
                await interaction.followup.send("No audiobook series found.")
                return
            options = [discord.SelectOption(label=folder, value=folder) for folder in series_folders]
            select = discord.SelectMenu(custom_id="select_series", placeholder="Select an audiobook series", options=options)
            await interaction.followup.send("Please select an audiobook series:", components=[[select]])
            try:
                interaction = await self.client.wait("select_option", check=lambda inter: inter.user == interaction.user)
                series_folder = interaction.values[0]
            except asyncio.TimeoutError:
                await interaction.followup.send("You didn't select an audiobook series in time.")
                return
        series_path = os.path.join("Audiobooks", series_folder)
        if not os.path.exists(series_path):
            await interaction.followup.send(f"Audiobook series '{series_folder}' not found.")
            return
        self.audiobook_series = series_folder
        self.current_position = self.load_position()  # Load position from file
        self.current_audiobook = self.get_next_audiobook()
        if not self.current_audiobook:
            await interaction.followup.send("No audiobooks found in the series folder.")
            return
        audio_path = os.path.join(series_path, self.current_audiobook)
        source = FFmpegPCMAudio(source=audio_path, before_options=f"-ss {self.current_position}")
        if voice_client:
            voice_client.play(PCMVolumeTransformer(source, volume=0.5), after=self.after_playing)
            await interaction.followup.send(f"Now playing: {self.current_audiobook}")

    async def after_playing(self, error):
        if self.last_interaction:
            if not self.repeat:
                self.current_audiobook = self.get_next_audiobook()
                if not self.current_audiobook:
                    await self.last_interaction.followup.send("End of series reached.")
                    self.save_position(0)  # Reset position when series ends
                    return
            audio_path = os.path.join("Audiobooks", self.audiobook_series, self.current_audiobook)
            source = FFmpegPCMAudio(source=audio_path)
            voice_client = self.last_interaction.guild.voice_client
            if voice_client:
                voice_client.play(PCMVolumeTransformer(source, volume=0.5), after=self.after_playing)
                await self.last_interaction.followup.send(f"Now playing: {self.current_audiobook}")
    
    @commands.command(name="stopbook", description="Stop the audiobook and save the position")
    async def stop_book(self, interaction: discord.Interaction):
        voice_client = interaction.guild.voice_client
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            self.save_position(voice_client.source._source.get_output_timestamp()[1])
            await interaction.response.send_message("Audiobook stopped and position saved.")
        else:
            await interaction.response.send_message("I'm not playing any audiobook.")

    @commands.command(name="resumebook", description="Resume the audiobook series from where it was stopped")
    async def resume_book(self, interaction: discord.Interaction):
        if self.audiobook_series:
            await self.play_book(interaction, self.audiobook_series)
        else:
            await interaction.response.send_message("No audiobook series has been played yet.")

    @commands.command(name="repeatbook", description="Toggle repeat for the current audiobook series")
    async def repeat_book(self, interaction: discord.Interaction):
        self.repeat = not self.repeat
        message = "Repeat is now enabled." if self.repeat else "Repeat is now disabled."
        await interaction.response.send_message(message)

    def get_next_audiobook(self):
        series_path = os.path.join("Audiobooks", self.audiobook_series)
        audiobooks = [file for file in os.listdir(series_path) if file.endswith((".mp3", ".m4a", ".flac", ".m4b"))]
        if not audiobooks:
            return None
        audiobooks.sort()  # Sort alphabetically to ensure correct order
        if self.current_audiobook:
            try:
                index = audiobooks.index(self.current_audiobook)
                if index < len(audiobooks) - 1:
                    return audiobooks[index + 1]
            except ValueError:
                pass  # If current audiobook not found, start from the first one
        return audiobooks[0]

    def save_position(self, position):
        position_file = os.path.join("Audiobooks", self.audiobook_series, "position.json")
        data = {"position": position}
        with open(position_file, "w") as file:
            json.dump(data, file)

    def load_position(self):
        position_file = os.path.join("Audiobooks", self.audiobook_series, "position.json")
        if os.path.exists(position_file):
            with open(position_file, "r") as file:
                data = json.load(file)
                return data.get("position", 0)
        return 0


class Youtube(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=2)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()


async def setup(client):
    await client.add_cog(Music(client))
    print("Music Online")

    await client.add_cog(Audiobooks(client))
    print("Audiobook Online")

    await client.add_cog(Youtube(client))
    print("Youtube Online")
