import os
import asyncio
import discord
from discord.ext import commands
import random
from dotenv import load_dotenv
import argparse
import ollama
import json

load_dotenv()

parser = argparse.ArgumentParser(description="Run TamaBot or SakiBot")
parser.add_argument("bot", choices=["tama", "saki"], help="Specify the bot to run (tama or saki)", nargs="?", default="tama")
args = parser.parse_args()


def GenerateResponse(message, modelName):
    try:
        response = ollama.chat(
            model=modelName,
            messages=[{'role': 'user', 'content': message.content}],
            stream=False,
        )
        AIResponse = response['message']['content']
        return AIResponse
    except Exception as e:
        print(f"An error occurred in GenerateResponse: {e}")
        return None

def GenerateGameList():
    # Path to the bot folder
    bot_directory = os.path.dirname(os.path.abspath(__file__))
    game_list_file = os.path.join(bot_directory, "DataFiles/GameList.json")

    games = []

    # Read games from GameList.json in the bot folder
    try:
        with open(game_list_file, "r") as file:
            gamelist = json.load(file)["games"]
            games.extend(gamelist)
    except FileNotFoundError:
        print(f"GameList.json not found: {game_list_file}")
    except json.JSONDecodeError as e:
        print(f"Error parsing GameList.json: {e}")
    except KeyError:
        print("'games' key not found in GameList.json")

    steam_directory = os.path.join(r"C:\\Program Files (x86)\\Steam\\steamapps\\common")
    if os.path.isdir(steam_directory):
        try:
            steam_games = [name for name in os.listdir(steam_directory) if os.path.isdir(os.path.join(steam_directory, name))]
            games.extend(steam_games)
        except Exception as e:
            print(f"Error accessing Steam directory {steam_directory}: {e}")

    return games

async def SetActivity(self):
    while True:
        games = GenerateGameList()
        if not games:
            print("No games found.")
            return

        game = random.choice(games)
        await self.client.change_presence(status=discord.Status.online, activity=discord.Game(name=game))
        print("Activity loop started")
        await asyncio.sleep(43200)

class DiscordBotBase:
    def __init__(self, modelName, commandPrefix, intents, token, chatChannel):
        self.client = commands.Bot(command_prefix=commandPrefix, case_insensitive=True, intents=intents)
        self.client.chatlog_dir = "logs/"
        self.token = token
        self.chatChannel = chatChannel
        self.modelName = modelName

        self.client.event(self.on_ready)
        self.client.event(self.on_message)


    async def on_ready(self):
        self.client.loop.create_task(SetActivity(self))
        channel = discord.utils.get(name=self.chatChannel)
        messages = []
        async for message in channel.history(limit=10):
            messages.append(message)
        for message in messages:
            if message.author.bot:
                continue

    async def on_message(self, message):
        if message.author.bot or message.content.startswith("!"):
            return

        if message.channel.name == self.chatChannel:
            AIResponse = GenerateResponse(message, self.modelName)
            if AIResponse:
                await message.channel.send(AIResponse)
        
        elif "tama" in message.content.lower() or "saki" in message.content.lower():
            AIResponse = GenerateResponse(message, self.modelName)
            if AIResponse:
                await message.channel.send(AIResponse)
    
        elif message.channel.name != self.chatChannel:
            rand = random.randrange(0, 6)
            if rand == 0:
                AIResponse = GenerateResponse(message)
                if AIResponse:
                    await message.channel.send(AIResponse)


class TamaBot(DiscordBotBase):
    def __init__(self):
        super().__init__(modelName="Tamaneko", commandPrefix=["tama"], intents=discord.Intents.all(), token=os.getenv("TamaToken"), chatChannel=os.getenv("ChatChannel"))
        self.botNames = ["tama", "tamaneko"]

    async def on_ready(self):
        await super().on_ready()


class SakiBot(DiscordBotBase):
    def __init__(self):
        super().__init__(modelName="Autumn", commandPrefix=["saki"], intents=discord.Intents.all(), token=os.getenv("SakiToken"), chatChannel=os.getenv("ChatChannel"))
        # self.modelName = "Autumn"
        self.botNames = ["saki", "autumn"]

    async def on_ready(self):
        await super().on_ready()


class Cog:
    def __init__(self, client):
        self.client = client

    async def load_cogs(self):
        if args.bot == "tama":
            await self.client.load_extension('Cogs.ModerationCog')
            await self.client.load_extension('Cogs.MusicCog')

        elif args.bot == "saki":
            await self.client.load_extension('Cogs.ModerationCog')
            await self.client.load_extension('Cogs.QuizCog')
            

    async def remove_cogs(self):
        await self.client.remove_cog('Cogs.ModerationCog')
        await self.client.remove_cog('Cogs.MusicCog')
        await self.client.remove_cog('Cogs.QuizCog')

    async def reloadcogs(self):
        await self.client.reload_extension('Cogs.ModerationCog')
        await self.client.reload_extension('Cogs.MusicCog')
        await self.client.reload_extension('Cogs.QuizCog')

async def main():
    if args.bot == "tama":
        bot = TamaBot()
    elif args.bot == "saki":
        bot = SakiBot()
    await Cog.remove_cogs(bot)
    await Cog.load_cogs(bot)
    print(f"{args.bot.capitalize()} Online")
    await bot.client.start(bot.token)


if __name__ == "__main__":
    asyncio.run(main())
