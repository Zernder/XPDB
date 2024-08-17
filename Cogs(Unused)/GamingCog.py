from concurrent.futures import ThreadPoolExecutor
import requests
import re
import threading
import time
import io
import traceback
import os
import tempfile

import discord
from discord import app_commands
from discord.app_commands import Choice
from discord.ext import commands, tasks

import asyncio
from pyboy import PyBoy
from pyboy.utils import WindowEvent
from PIL import Image


@staticmethod
async def is_allowed_user(interaction: discord.Interaction):
    allowed_users = [175421668850794506, 427689980241117184]  # User IDs go here
    return interaction.user.id in allowed_users

BUTTON_MAPPING = {
        "up": WindowEvent.PRESS_ARROW_UP,
        "down": WindowEvent.PRESS_ARROW_DOWN,
        "left": WindowEvent.PRESS_ARROW_LEFT,
        "right": WindowEvent.PRESS_ARROW_RIGHT,
        "a": WindowEvent.PRESS_BUTTON_A,
        "b": WindowEvent.PRESS_BUTTON_B,
        "start": WindowEvent.PRESS_BUTTON_START,
        "select": WindowEvent.PRESS_BUTTON_SELECT,
    }

RELEASE_MAPPING = {
    WindowEvent.PRESS_ARROW_UP: WindowEvent.RELEASE_ARROW_UP,
    WindowEvent.PRESS_ARROW_DOWN: WindowEvent.RELEASE_ARROW_DOWN,
    WindowEvent.PRESS_ARROW_LEFT: WindowEvent.RELEASE_ARROW_LEFT,
    WindowEvent.PRESS_ARROW_RIGHT: WindowEvent.RELEASE_ARROW_RIGHT,
    WindowEvent.PRESS_BUTTON_A: WindowEvent.RELEASE_BUTTON_A,
    WindowEvent.PRESS_BUTTON_B: WindowEvent.RELEASE_BUTTON_B,
    WindowEvent.PRESS_BUTTON_START: WindowEvent.RELEASE_BUTTON_START,
    WindowEvent.PRESS_BUTTON_SELECT: WindowEvent.RELEASE_BUTTON_SELECT
}


class GameCogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pyboy = None
        self.running = False
        self.last_message = None
        self.save_state_file = os.path.join(tempfile.gettempdir(), "game_state.state")
        self.autosave_file = os.path.join(tempfile.gettempdir(), "autosave.state")
        self.autosave_task = None
        self.autosave_interval = 60  # seconds
        self.autosave_enabled = False

    @commands.Cog.listener()
    async def on_ready(self):
        print("GameCogs is ready.")

    @app_commands.command(name="start_game", description="Start the Game Boy emulator")
    async def start_game(self, interaction: discord.Interaction):
        if self.running:
            await interaction.response.send_message("The game is already running.", ephemeral=True)
            return

        try:
            print("Initializing PyBoy...")
            self.pyboy = PyBoy('roms\Pokemon Crystal Legacy\cryslegacy v1.2.2.gbc', window="null")
            print(f"PyBoy initialized: {self.pyboy}")
            print(f"PyBoy attributes: {dir(self.pyboy)}")
            self.running = True
            self.emulate_game_thread = threading.Thread(target=self.emulate_game)
            self.emulate_game_thread.start()

            await interaction.response.send_message("Game started successfully.", ephemeral=True)
        except Exception as e:
            error_msg = f"Failed to start the game: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            await interaction.response.send_message(f"Failed to start the game: {str(e)}", ephemeral=True)

    @app_commands.command(name="stop_game", description="Stop the Game Boy emulator")
    async def stop_game(self, interaction: discord.Interaction):
        if not self.running:
            await interaction.response.send_message("The game is not running.", ephemeral=True)
            return

        try:
            self.running = False
            if self.emulate_game_thread:
                self.emulate_game_thread.join()  # Wait for the emulation thread to finish
            
            self.pyboy = None

            await interaction.response.send_message("Game stopped successfully.", ephemeral=True)
        except Exception as e:
            error_msg = f"Failed to stop the game: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            await interaction.response.send_message(f"Failed to stop the game: {str(e)}", ephemeral=True)


    async def autosave_loop(self):
            while True:
                if self.running and self.autosave_enabled and self.pyboy:
                    try:
                        with open(self.autosave_file, 'wb') as f:
                            self.pyboy.save_state(f)
                        print("Autosave completed.")
                    except Exception as e:
                        print(f"Failed to autosave game state: {str(e)}")
                await asyncio.sleep(self.autosave_interval)


    def emulate_game(self):
        print("Emulation game started")
        try:
            while self.running:
                self.pyboy.tick()
                time.sleep(1/60)
        except Exception as e:
            print(f"Emulation game stopped due to error: {e}")
        finally:
            if self.pyboy:
                self.pyboy.stop()


    @app_commands.check(is_allowed_user) 
    @app_commands.command(name="game-action", description="Perform an action on the Game Boy")
    @app_commands.choices(action=[Choice(name=b, value=b) for b in list(BUTTON_MAPPING.keys()) + ["SaveState", "LoadState"]])
    async def game_action(self, interaction: discord.Interaction, action: str):
        if not self.pyboy or not self.running:
            await interaction.response.send_message("The emulator is not running. Please start the game first.", ephemeral=True)
            return

        try:
            await interaction.response.defer()

            # Delete the previous message if it exists
            if self.last_message:
                try:
                    await self.last_message.delete()
                except discord.errors.NotFound:
                    pass

            if action == "SaveState":
                try:
                    with open(self.save_state_file, 'wb') as f:
                        self.pyboy.save_state(f)
                    await interaction.followup.send("Game state saved.", ephemeral=True)
                except Exception as e:
                    await interaction.followup.send(f"Failed to save game state: {str(e)}", ephemeral=True)
                return
            elif action == "LoadState":
                if os.path.exists(self.save_state_file):
                    try:
                        with open(self.save_state_file, 'rb') as f:
                            self.pyboy.load_state(f)
                        await interaction.followup.send("Game state loaded.", ephemeral=True)
                    except Exception as e:
                        await interaction.followup.send(f"Failed to load game state: {str(e)}", ephemeral=True)
                else:
                    await interaction.followup.send("No saved state found.", ephemeral=True)
                return

            press_event = BUTTON_MAPPING[action]
            release_event = RELEASE_MAPPING[press_event]

            frames = []
            frame_count = 1200

            self.pyboy.send_input(press_event)
            await asyncio.sleep(0.1)
            self.pyboy.send_input(release_event)
            await asyncio.sleep(0.1)

            for i in range(frame_count):
                self.pyboy.tick()
                screen_image = self.pyboy.screen.image
                frames.append(screen_image.copy())

            # Create and save the GIF
            buffer = io.BytesIO()
            frames[0].save(buffer, format='GIF', save_all=True, append_images=frames[1:], duration=33, loop=0)
            buffer.seek(0)

            # Send the GIF and store the message
            new_message = await interaction.followup.send(
                f"Performed action: {action}",
                file=discord.File(buffer, filename="action.gif"),
                wait=True
            )
            self.last_message = new_message

        except KeyError:
            await interaction.followup.send(f"Error: Invalid action '{action}'", ephemeral=True)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            await interaction.followup.send(f"An unexpected error occurred: {str(e)}", ephemeral=True)



    @commands.command(name="up")
    async def move_up(self, ctx):
        await self.move_direction(ctx, WindowEvent.PRESS_ARROW_UP, WindowEvent.RELEASE_ARROW_UP, "up")

    @commands.command(name="down")
    async def move_down(self, ctx):
        await self.move_direction(ctx, WindowEvent.PRESS_ARROW_DOWN, WindowEvent.RELEASE_ARROW_DOWN, "down")

    @commands.command(name="left")
    async def move_left(self, ctx):
        await self.move_direction(ctx, WindowEvent.PRESS_ARROW_LEFT, WindowEvent.RELEASE_ARROW_LEFT, "left")

    @commands.command(name="right")
    async def move_right(self, ctx):
        await self.move_direction(ctx, WindowEvent.PRESS_ARROW_RIGHT, WindowEvent.RELEASE_ARROW_RIGHT, "right")

    async def move_direction(self, ctx, press_event, release_event, direction):
        if not self.pyboy or not self.running:
            await ctx.send("The emulator is not running. Please start the game first.")
            return

        try:
            if self.last_message:
                try:
                    await self.last_message.delete()
                except discord.errors.NotFound:
                    pass

            # Press the button
            self.pyboy.send_input(press_event)
            await asyncio.sleep(0.1)
            self.pyboy.send_input(release_event)

            frames = []
            frame_count = 60

            for _ in range(frame_count):
                self.pyboy.tick()
                screen_image = self.pyboy.screen.image
                frames.append(screen_image.copy())

            buffer = io.BytesIO()
            frames[0].save(buffer, format='GIF', save_all=True, append_images=frames[1:], duration=33, loop=0)
            buffer.seek(0)

            new_message = await ctx.send(
                f"Moved {direction}",
                file=discord.File(buffer, filename="movement.gif")
            )
            self.last_message = new_message

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            await ctx.send(f"An unexpected error occurred: {str(e)}")
    

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="multiplegameaction", description="Queue up to 5 moves on the Game Boy and get a GIF")
    @app_commands.choices(move1=[Choice(name=b, value=b) for b in BUTTON_MAPPING.keys()])
    @app_commands.choices(move2=[Choice(name=b, value=b) for b in BUTTON_MAPPING.keys()])
    @app_commands.choices(move3=[Choice(name=b, value=b) for b in BUTTON_MAPPING.keys()])
    @app_commands.choices(move4=[Choice(name=b, value=b) for b in BUTTON_MAPPING.keys()])
    @app_commands.choices(move5=[Choice(name=b, value=b) for b in BUTTON_MAPPING.keys()])
    async def button_queue(self, interaction: discord.Interaction, move1: str, move2: str = None, move3: str = None, move4: str = None, move5: str = None):
        if not self.pyboy or not self.running:
            await interaction.response.send_message("The emulator is not running. Please start the game first.", ephemeral=True)
            return

        try:
            await interaction.response.defer()

            # Delete the previous message if it exists
            if self.last_message:
                try:
                    await self.last_message.delete()
                except discord.errors.NotFound:
                    pass

            moves = [move for move in [move1, move2, move3, move4, move5] if move is not None]
            frames = []
            frame_count = 180  # 6 seconds at 30 fps

            for move in moves:
                press_event = BUTTON_MAPPING[move]
                release_event = RELEASE_MAPPING[press_event]

                self.pyboy.send_input(press_event)
                await asyncio.sleep(0.1)
                self.pyboy.send_input(release_event)
                await asyncio.sleep(0.1)

            # Capture frames for 6 seconds
            for i in range(frame_count):
                self.pyboy.tick()
                screen_image = self.pyboy.screen.image
                frames.append(screen_image.copy())

            # Create and save the GIF
            buffer = io.BytesIO()
            frames[0].save(buffer, format='GIF', save_all=True, append_images=frames[1:], duration=16.67, loop=0)  # 33 ms per frame for 30 fps
            buffer.seek(0)

            # Send the GIF and store the message
            moves_str = " -> ".join(moves)
            new_message = await interaction.followup.send(
                f"Executed moves: {moves_str}",
                file=discord.File(buffer, filename="action.gif"),
                wait=True
            )
            self.last_message = new_message

        except KeyError as e:
            await interaction.followup.send(f"Error: Invalid button '{e}'", ephemeral=True)
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            await interaction.followup.send(f"An unexpected error occurred: {str(e)}", ephemeral=True)

        def cog_unload(self):
            if self.emulate_game_task:
                self.emulate_game_task.cancel()
            if self.pyboy:
                self.pyboy.stop()



class Servers(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.executor = ThreadPoolExecutor(max_workers=2)

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()
        self.soap_command = ".server info"
        self.update_status.start()

    def cog_unload(self):
        self.update_status.cancel()

    @tasks.loop(seconds=60)
    async def update_status(self):
        result = await self.execute_soap_command(self.soap_command)
        server_info = self.parse_server_info(result)
        await self.client.change_presence(activity=discord.Game(name=server_info))

    def parse_server_info(self, soap_response):
        connected_players = re.search(r"Connected players: (\d+)", soap_response).group(1)
        connection_peak = re.search(r"Connection peak: (\d+)", soap_response).group(1)
        server_uptime = re.search(r"Server uptime: ([\d hour(s) minute(s) second(s)]+)", soap_response).group(1)
        update_time_diff = re.search(r"Update time diff: ([\dms, average: \dms]+)", soap_response).group(1)

        server_status = "Online" if soap_response else "Offline"
        formatted_status = f"WoW: {connected_players} players, peak {connection_peak}"
        return formatted_status

    @update_status.before_loop
    async def before_update_status(self):
        await self.client.wait_until_ready()

    async def execute_soap_command(self, soap_command):
        host = "xanmal.zapto.org"
        port = "7878"
        url = f'http://{host}:{port}/'
        soap_body = self.construct_soap_body(soap_command)
        auth = ('Xanmal', 'K1347334F!King!')

        response = await asyncio.get_event_loop().run_in_executor(self.executor, self.send_soap_request, url, auth, soap_body)
        return response

    def construct_soap_body(self, command):
        return f'''<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/"
                    xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/"
                    xmlns:xsi="http://www.w3.org/1999/XMLSchema-instance"
                    xmlns:xsd="http://www.w3.org/1999/XMLSchema"
                    xmlns:ns1="urn:AC">
                <SOAP-ENV:Body>
                    <ns1:executeCommand>
                        <command>{command}</command>
                    </ns1:executeCommand>
                </SOAP-ENV:Body>
            </SOAP-ENV:Envelope>'''

    def send_soap_request(self, url, auth, soap_body):
        headers = {'Content-Type': 'application/xml'}
        try:
            response = requests.post(url, auth=auth, data=soap_body, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.HTTPError as e:
            return f"Error occurred: {e}"

    @app_commands.command(name="create_account", description="Create a new game account")
    async def create_account(self, interaction: discord.Interaction, username: str, password: str):
        soap_command = f".account create {username} {password}"
        result = await self.execute_soap_command(soap_command)

        start_index = result.find("Account created: ") + len("Account created: ")
        end_index = result.find("&#xD;")
        account_name = result[start_index:end_index]

        extracted_part = f"Account created: {account_name}"
        await interaction.response.send_message(extracted_part)

    @app_commands.command(name="delete_account", description="Delete a game account")
    async def delete_account(self, interaction: discord.Interaction, account: str):
        soap_command = f".account delete {account}"
        result = await self.execute_soap_command(soap_command)

        start_index = result.find("Account deleted: ") + len("Account deleted: ")
        end_index = result.find("&#xD;")
        account_name = result[start_index:end_index]

        extracted_part = f"Account deleted: {account_name}"
        await interaction.response.send_message(extracted_part)

    @app_commands.command(name="olist", description="See who is online")
    async def olist(self, interaction: discord.Interaction):
        soap_command = ".account onlinelist"
        result = await self.execute_soap_command(soap_command)
        extracted_part = self.extract_response_part(result)
        await interaction.response.send_message(extracted_part)

    @app_commands.command(name="change_faction", description="Change character's faction")
    async def change_faction(self, interaction: discord.Interaction, name: str):
        soap_command = f".character changefaction {name}"
        result = await self.execute_soap_command(soap_command)
        extracted_part = self.extract_response_part(result)
        await interaction.response.send_message(extracted_part)

    def extract_response_part(self, result):
        start_index = result.find("<result>") + len("<result>")
        end_index = result.find("</result>")
        extracted_part = result[start_index:end_index]
        return extracted_part

async def setup(client):
    await client.add_cog(Servers(client))
    print("Wowserver Online")
    await client.add_cog(GameCogs(client))
    print("PokemonCog Online")
