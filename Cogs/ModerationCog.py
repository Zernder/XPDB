import discord
from discord import Forbidden, app_commands
from discord.ext import commands

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

    @app_commands.command(name= "ping", description= "Ping the bot")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message(f"Pong! {round(self.client.latency * 1000)}ms")

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="purge", description="Clear chat messages")
    @commands.has_permissions(manage_messages=True)
    async def purge(self, interaction: discord.Interaction, count: int):
        try:
            await interaction.response.send_message(f"Purging {count} messages...", ephemeral=True)
            await interaction.response.defer(ephemeral=True)
            await interaction.channel.purge(limit=count)
            await interaction.followup.send(f"Deleted {count} messages.")
        except Forbidden:
            await interaction.send("Missing permissions")
        except Exception as e:
            await interaction.send(f"Purge failed: {e}")

    @app_commands.command(name="reload_cogs", description="Reloads the Cogs")
    async def reloadcogs(self, interaction: discord.Interaction):
        try:
            await interaction.client.reload_extension('Cogs.ModerationCog')
            await interaction.client.reload_extension('Cogs.MusicCog')
            await interaction.client.reload_extension('Cogs.QuizCog')
            print("Cogs Reloaded")

        except:
            print("Error Reloading Cogs")

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="kick", description="Kick Member")
    @commands.has_permissions(kick_members=True)
    async def kick(self, interaction: discord.Interaction, member: discord.Member=None,):
        await interaction.send_message("Please mention a member to kick.")
        await interaction.guild.kick(member)
        await interaction.send_message(f"{member.mention} has been kicked from the server {interaction.author.mention}.")
        await interaction.user.kick(discord.Member)
        await interaction.send_message(f"{interaction.member.mention} has been kicked from the server {interaction.author.mention}.")

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="ban", description="Ban Member")
    @commands.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member=None,):
        await interaction.send_message("Please mention a member to ban.")
        await interaction.guild.ban(member)
        await interaction.send_message(f"{member.mention} has been banned from the server {interaction.author.mention}.")
        await interaction.user.ban(discord.Member)
        await interaction.send_message(f"{interaction.member.mention} has been banned from the server {interaction.author.mention}.")

    @app_commands.check(is_allowed_user)
    @app_commands.command(name="unban", description="Unban Member")
    @commands.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, member: discord.Member=None,):
        await interaction.send_message("Please mention a member to unban.")
        await interaction.guild.unban(member)
        await interaction.send_message(f"{member.mention} has been unbanned from the server {interaction.author.mention}.")
        await interaction.user.unban(discord.Member)
        await interaction.send_message(f"{interaction.member.mention} has been unbanned from the server {interaction.author.mention}.")

async def setup(client):
    await client.add_cog(Moderation(client))
    print("Moderation Online")