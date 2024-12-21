import discord
from discord import Forbidden, app_commands
from discord.ext import commands
from typing import Dict, List

class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client
        # # Channel IDs where only bot messages are allowed
        # self.bot_only_channels = [
        #     1171100779201974394  # music channel
        # ]
        
        # # Channel IDs and their allowed message types
        # self.channel_permissions: Dict[int, List[str]] = {
        #     1171100779201974394: ["music_commands"]  # music channel - only allow music commands
        # }

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()

    # @commands.Cog.listener()
    # async def on_message(self, message: discord.Message):
    #     # Ignore messages from this bot
    #     if message.author == self.client.user:
    #         return

    #     # Check if message is in a restricted channel
    #     if message.channel.id in self.bot_only_channels:
    #         # Allow slash commands to pass through
    #         if not message.content.startswith('/'):
    #             try:
    #                 await message.delete()
    #                 # Try to send DM
    #                 try:
    #                     await message.author.send(
    #                         f"❌ The channel {message.channel.mention} is restricted. "
    #                         "Only commands are allowed.",
    #                         delete_after=10
    #                     )
    #                 except discord.Forbidden:
    #                     # If DM fails, send channel message
    #                     await message.channel.send(
    #                         f"❌ {message.author.mention}, this channel is restricted to commands only.",
    #                         delete_after=5
    #                     )
    #             except discord.Forbidden:
    #                 pass  # If we can't delete or send messages, silently fail

    @staticmethod
    async def is_allowed_user(interaction: discord.Interaction):
        allowed_users = [175421668850794506]  # User IDs go here
        return interaction.user.id in allowed_users

    @app_commands.command(name="ping", description="Ping the bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.client.latency * 1000)}ms")

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="purge", description="Clear chat messages")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, count: int):
        try:
            await interaction.response.defer(ephemeral=True)
            deleted = await interaction.channel.purge(limit=count)
            await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)
        except Forbidden:
            await interaction.followup.send("Missing permissions", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Purge failed: {e}", ephemeral=True)

    @app_commands.command(name="reload_cogs", description="Reloads the Cogs")
    @app_commands.check(is_allowed_user)
    async def reload_cogs(self, interaction: discord.Interaction):
        try:
            # Deferring the response and sending an ephemeral loading message
            await interaction.response.defer(ephemeral=True)
            
            # List of cogs to reload
            cogs_to_reload = [
                'Cogs.MusicCog',
                'Cogs.QuizCog',
            ]
            
            # Reloading cogs
            for cog in cogs_to_reload:
                try:
                    await self.client.reload_extension(cog)
                    print(f"Successfully reloaded {cog}")
                except Exception as e:
                    print(f"Error reloading {cog}: {e}")
                    await interaction.followup.send(f"Error reloading {cog}: {e}", ephemeral=True)
                    return  # Stop reloading further if one cog fails

            # Send success message after all cogs have been reloaded
            await interaction.followup.send("Cogs successfully reloaded!", ephemeral=True)
            print("All cogs reloaded successfully.")

        except Exception as e:
            # Catching unexpected errors
            await interaction.followup.send(f"Error reloading cogs: {e}", ephemeral=True)
            print(f"Unexpected error reloading cogs: {e}")


    @app_commands.check(is_allowed_user)
    @app_commands.command(name="kick", description="Kick a member from the server")
    @commands.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member):
        if not member:
            await interaction.response.send_message("Please mention a member to kick.", ephemeral=True)
            return
        
        try:
            await member.kick()
            await interaction.response.send_message(
                f"{member.mention} has been kicked from the server by {interaction.user.mention}.",
                ephemeral=True
            )
        except Forbidden:
            await interaction.response.send_message("I don't have permission to kick this member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to kick member: {e}", ephemeral=True)

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="ban", description="Ban a member from the server")
    @commands.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member):
        if not member:
            await interaction.response.send_message("Please mention a member to ban.", ephemeral=True)
            return
        
        try:
            await member.ban()
            await interaction.response.send_message(
                f"{member.mention} has been banned from the server by {interaction.user.mention}.",
                ephemeral=True
            )
        except Forbidden:
            await interaction.response.send_message("I don't have permission to ban this member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to ban member: {e}", ephemeral=True)

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="unban", description="Unban a member from the server")
    @commands.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.client.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(
                f"{user.mention} has been unbanned from the server by {interaction.user.mention}.",
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("Please provide a valid user ID.", ephemeral=True)
        except Forbidden:
            await interaction.response.send_message("I don't have permission to unban members.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to unban member: {e}", ephemeral=True)

async def setup(client):
    await client.add_cog(Moderation(client))
    print("Moderation Online")