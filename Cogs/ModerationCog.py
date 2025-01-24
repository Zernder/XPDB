import discord
from discord import Forbidden, app_commands
from discord.ext import commands
from typing import Dict, List

class Moderation(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.Cog.listener()
    async def on_ready(self):
        await self.client.tree.sync()

    @staticmethod
    async def is_allowed_user(interaction: discord.Interaction):
        allowed_users = [175421668850794506]  # User IDs go here
        return interaction.user.id in allowed_users

    @app_commands.command(name="ping", description="Ping the bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.client.latency * 1000)}ms")

    @app_commands.command(name="purge", description="Clear chat messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    @app_commands.check(is_allowed_user)
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
            await interaction.response.defer(ephemeral=True)
            cogs_to_reload = ['Cogs.MusicCog', 'Cogs.QuizCog']
            for cog in cogs_to_reload:
                try:
                    await self.client.reload_extension(cog)
                except Exception as e:
                    await interaction.followup.send(f"Error reloading {cog}: {e}", ephemeral=True)
                    return
            await interaction.followup.send("Cogs successfully reloaded!", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"Error reloading cogs: {e}", ephemeral=True)

    @app_commands.command(name="kick", description="Kick a member from the server")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.check(is_allowed_user)
    async def kick(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.kick()
            await interaction.response.send_message(
                f"{member.mention} has been kicked by {interaction.user.mention}.", ephemeral=True
            )
        except Forbidden:
            await interaction.response.send_message("I can't kick this member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.check(is_allowed_user)
    async def ban(self, interaction: discord.Interaction, member: discord.Member):
        try:
            await member.ban()
            await interaction.response.send_message(
                f"{member.mention} has been banned by {interaction.user.mention}.", ephemeral=True
            )
        except Forbidden:
            await interaction.response.send_message("I can't ban this member.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a member from the server")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.check(is_allowed_user)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            user = await self.client.fetch_user(int(user_id))
            await interaction.guild.unban(user)
            await interaction.response.send_message(
                f"{user.mention} has been unbanned by {interaction.user.mention}.", ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message("Invalid user ID.", ephemeral=True)
        except Forbidden:
            await interaction.response.send_message("I can't unban this user.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Error: {e}", ephemeral=True)

    @app_commands.command(name="speak", description="Make the bot send a message")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def speak(
        self,
        interaction: discord.Interaction,
        message: app_commands.Range[str, 1, 2000],  # Allow up to 2000 chars
        channel: discord.TextChannel = None
    ):
        await interaction.response.defer(ephemeral=True)
        target_channel = channel or interaction.channel

        try:
            # Discord messages cannot exceed 2000 characters
            if len(message) > 2000:
                await interaction.followup.send(
                    "Message exceeds 2000 characters.", 
                    ephemeral=True
                )
                return

            await target_channel.send(message)
            await interaction.followup.send(
                f"✅ Message sent to {target_channel.mention}.", 
                ephemeral=True
            )

        except Forbidden:
            await interaction.followup.send(
                "❌ Bot lacks permissions in that channel.", 
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.followup.send(
                f"❌ Failed to send message: {e}", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ Unexpected error: {e}", 
                ephemeral=True
            )

async def setup(client):
    await client.add_cog(Moderation(client))
    print("Moderation Online")