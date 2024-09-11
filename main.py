import os
import asyncio
import discord
from discord.ext import commands
import requests
from dotenv import load_dotenv
import argparse
import ollama

load_dotenv()

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

        # Register event handlers
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

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
        if message.author.bot:
            return
        
        try:
            response = ollama.chat(
                model='Tamaneko',
                messages=[{'role': 'user', 'content': message.content}],
                stream=False,
            )
            AIResponse = response['message']['content']
            print(f"AI Response: {AIResponse}")
            await message.channel.send(AIResponse)
        except Exception as e:
            print(f"An error occurred in on_message: {e}")


class TamaBot(DiscordBotBase):
    def __init__(self):
        super().__init__(command_prefix=["!"], intents=discord.Intents.all(), token=os.getenv("TamaToken"), chat_channel=os.getenv("ChatChannel"))
        self.model_name = "Tamaneko"
        self.botNames = ["tama", "tamaneko"]

    async def load_cogs(self):
        await self.client.load_extension(f'Cogs.ModerationCog')
        # await self.client.load_extension(f'Cogs.MusicCog')
  

class SakiBot(DiscordBotBase):
    def __init__(self):
        super().__init__(command_prefix=["saki"], intents=discord.Intents.all(), token=os.getenv("SakiToken"), chat_channel=os.getenv("ChatChannel"))
        self.model_name = "Autumn"
        self.botNames = ["saki", "autumn"]

    async def load_cogs(self):
        await self.client.load_extension(f'Cogs.ModerationCog')
        # await self.client.load_extension(f'Cogs.MusicCog')
  

class Cog:
    def __init__(self, client):
        self.client = client

  
    async def remove_cogs(self):
        await self.client.remove_cog(f'Cogs.ModerationCog')
        await self.client.remove_cog(f'Cogs.MusicCog')


async def main():
    
    if args.bot == "tama":
        bot = TamaBot()
        await Cog.remove_cogs(bot)
        await TamaBot.load_cogs(bot)
    elif args.bot == "saki":
        bot = SakiBot()
        await Cog.remove_cogs(bot)
        await SakiBot.load_cogs(bot)
    print(f"{args.bot.capitalize()} Online")
    await bot.client.start(bot.token)


if __name__ == "__main__":
    asyncio.run(main())
