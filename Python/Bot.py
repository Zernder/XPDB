import os
import asyncio
import discord
from discord.ext import commands
import requests
from dotenv import load_dotenv
import argparse

load_dotenv()
ollamaurl = 'http://127.0.0.1:11434/api/chat'

parser = argparse.ArgumentParser(description="Run TamaBot or SakiBot")
parser.add_argument("bot", choices=["tama", "saki"], help="Specify the bot to run (tama or saki)")
args = parser.parse_args()

class DiscordBotBase:
    def __init__(self, command_prefix, intents, token, chat_channel):
        self.client = commands.Bot(command_prefix=command_prefix, case_insensitive=True, intents=intents)
        self.client.chatlog_dir = "logs/"
        self.token = token
        self.chat_channel = chat_channel
        self.user_message_log = {}

    def log_message(self, author_id, content):
        if author_id not in self.user_message_log:
            self.user_message_log[author_id] = []
        self.user_message_log[author_id].append({"role": "user", "content": content})

    async def on_ready(self):
        try:
            guild = discord.utils.get(self.client.guilds, id=945718319007285310)
            if guild:
                print(f"Guild found: {guild.name}")
            else:
                print("Guild not found")
                return
            channel = discord.utils.get(guild.text_channels, name=self.chat_channel)
            messages = []
            async for message in channel.history(limit=10):
                messages.append(message)
            for message in messages:
                if message.author.bot:
                    continue
                self.log_message(message.author.id, message.content)
        except Exception as e:
            print(f"An error occurred in on_ready: {e}")

    async def on_message(self, message):
        try:
            if message.content.startswith('!'):
                await self.client.process_commands(message)
                return
            if message.author.bot:
                return
            if any(name.lower() in message.content.lower() for name in self.tama_names):
                payload = {"model": self.model_name, "messages": [{"role": "user", "content": message.content}], "stream": False}
                response = requests.post(ollamaurl, json=payload)
                response_data = response.json()
                response_text = response_data.get("message", {}).get("content", "")
                await message.channel.send(response_text)
        except Exception as e:
            print(f"Error in on_message: {str(e)}")
        await self.client.process_commands(message)

class TamaBot(DiscordBotBase):
    def __init__(self):
        super().__init__(command_prefix=["!"], intents=discord.Intents.all(), token=os.getenv("TamaToken"), chat_channel=os.getenv("ChatChannel"))
        self.model_name = "Tamaneko"
        self.tama_names = ["tama", "tamaneko"]

class SakiBot(DiscordBotBase):
    def __init__(self):
        super().__init__(command_prefix=["saki"], intents=discord.Intents.all(), token=os.getenv("SakiToken"), chat_channel=os.getenv("ChatChannel"))
        self.model_name = "Autumn"
        self.tama_names = ["saki", "autumn"]

class Cog:
    def __init__(self, client):
        self.client = client

    async def reload(self, ctx, extension):
        extension_name = f'Cogs.{extension}'
        if extension_name in self.client.extensions:
            try:
                await self.client.unload_extension(extension_name)
            except Exception as e:
                await ctx.send(f'Could not unload the extension {extension}. Error: {e}')
                return
        else:
            await ctx.send(f'The extension {extension} is not loaded, attempting to load...')

    async def load_cogs(self):
        try:
            for filename in os.listdir('./Cogs'):
                if filename.endswith('.py'):
                    await self.client.load_extension(f'Cogs.{filename[:-3]}')
                else:
                    print(f'Unable to load {filename[:-3]}')
        except FileNotFoundError as e:
            print(f"Failed to load cogs: {e}")




async def main():
    if args.bot == "tama":
        bot = TamaBot()
    elif args.bot == "saki":
        bot = SakiBot()

    cog = Cog(bot.client)
    await cog.load_cogs()
    print(f"{args.bot.capitalize()} Online")
    await bot.client.start(bot.token)

if __name__ == "__main__":
    asyncio.run(main())
