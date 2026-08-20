"""Police department and jail controls."""
import discord
from discord.ext import commands
from discord import app_commands

from bot.utils import error_embed, info_embed, is_admin, success_embed


def police_or_admin(member: discord.Member) -> bool:
    return is_admin(member) or any(
        role.name == "Police Officer" for role in member.roles
    )


class Police(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _jail(self, guild, member, officer, reason):
        record = await self.bot.db.jail_user(
            str(guild.id), str(member.id), reason, str(officer.id)
        )
        inmate = discord.utils.get(guild.roles, name="Jail Inmate")
        if inmate:
            try:
                await member.add_roles(inmate, reason=f"Jailed by {officer}")
            except discord.Forbidden:
                pass
        await self._log(guild, f"🚓 {member} jailed by {officer}: {reason}")
        return record

    async def _release(self, guild, member, officer):
        await self.bot.db.release_user(str(guild.id), str(member.id))
        inmate = discord.utils.get(guild.roles, name="Jail Inmate")
        if inmate:
            try:
                await member.remove_roles(inmate, reason=f"Released by {officer}")
            except discord.Forbidden:
                pass
        await self._log(guild, f"🚓 {member} released by {officer}")

    async def _log(self, guild, message):
        channel = discord.utils.get(guild.text_channels, name="metrocity-logs")
        if channel:
            try:
                await channel.send(message)
            except discord.Forbidden:
                pass

    @app_commands.command(name="jail", description="[Police/Admin] Jail a player and block financial commands.")
    @app_commands.describe(member="Player to jail.", reason="Reason for the arrest.")
    async def jail_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "Police detention"):
        if not police_or_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Access Denied", "Police Officers or Administrators only."), ephemeral=True)
        if member.bot or member.id == interaction.user.id:
            return await interaction.response.send_message(embed=error_embed("Invalid Target", "Choose a player other than yourself."), ephemeral=True)
        await interaction.response.defer()
        await self._jail(interaction.guild, member, interaction.user, reason)
        await interaction.followup.send(embed=success_embed("Player Jailed", f"{member.mention} is jailed.\n**Reason:** {reason}\nThey cannot use economy, betting, business, or loan commands."))

    @app_commands.command(name="unjail", description="[Police/Admin] Release a player from jail.")
    async def unjail_slash(self, interaction: discord.Interaction, member: discord.Member):
        if not police_or_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Access Denied", "Police Officers or Administrators only."), ephemeral=True)
        await interaction.response.defer()
        await self._release(interaction.guild, member, interaction.user)
        await interaction.followup.send(embed=success_embed("Player Released", f"{member.mention} has been released from jail."))

    @app_commands.command(name="police", description="View Police Department commands.")
    async def police_slash(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=info_embed(
            "🚓 Police Department",
            "`/jail @user [reason]` — detain a player\n"
            "`/unjail @user` — release a player\n"
            "`!police` shows the prefix equivalents.\n\n"
            "Jailed users cannot use economy, business, betting, or loan commands.",
        ))

    @commands.command(name="jail")
    @commands.guild_only()
    async def jail_prefix(self, ctx, member: discord.Member, *, reason: str = "Police detention"):
        if not police_or_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Police Officers or Administrators only."))
        if member.bot or member.id == ctx.author.id:
            return await ctx.send(embed=error_embed("Invalid Target", "Choose a player other than yourself."))
        await self._jail(ctx.guild, member, ctx.author, reason)
        await ctx.send(embed=success_embed("Player Jailed", f"{member.mention} is jailed.\n**Reason:** {reason}"))

    @commands.command(name="unjail", aliases=["release"])
    @commands.guild_only()
    async def unjail_prefix(self, ctx, member: discord.Member):
        if not police_or_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Police Officers or Administrators only."))
        await self._release(ctx.guild, member, ctx.author)
        await ctx.send(embed=success_embed("Player Released", f"{member.mention} has been released from jail."))

    @commands.command(name="police")
    @commands.guild_only()
    async def police_prefix(self, ctx):
        await ctx.send(embed=info_embed(
            "🚓 Police Department",
            "`!jail @user [reason]`\n`!unjail @user`\n\n"
            "Police Officers and Administrators can use these commands.",
        ))


async def setup(bot):
    await bot.add_cog(Police(bot))