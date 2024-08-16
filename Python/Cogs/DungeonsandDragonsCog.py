import discord
from discord import Forbidden, app_commands
from discord.ext import commands
import random
import dotenv
import os
import ast
import traceback
import logging

logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv
PokemonList = os.getenv("WildEncounterPokemon")


class DungeonsandDragons(commands.Cog):
    def __init__(self, client):
        self.client = client


    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()


    @app_commands.command(name='wild-encounter', description="Make a random list of Pokémon encounters.")
    async def WildEncounter(self, interaction: discord.Interaction, level: int):
        if level < 1 or level > 20:
            await interaction.response.send_message("Please enter a number between 1 and 20.")
            return
        
        pokemon_list = os.getenv("WildEncounterPokemon")
        
        if pokemon_list is None:
            await interaction.response.send_message("Error: Pokémon list is not available.")
            return

        pokemon_list = pokemon_list.split(',')

        await interaction.response.send_message(f"Generating random encounters around Trainer's highest level {level}...")

        # Generate random levels for up to 20 Pokémon within ±3 of the highest level
        pokemon_encounters = []
        for _ in range(min(20, level)):
            random_level = random.randint(max(1, level - 3), min(100, level + 3))
            random_pokemon = random.choice(pokemon_list)
            pokemon_encounters.append(f"{random_pokemon} Level {random_level}")

        response = "\n".join(pokemon_encounters)
        await interaction.followup.send(f"Random encounters Ready!):\n{response}")



async def setup(client):
    await client.add_cog(DungeonsandDragons(client))
    print("DND Ready!")

