"""Automatic and manual creation of the bot's standard RP roles."""
import discord
from discord.ext import commands
from discord import app_commands

from bot.config import REQUIRED_DISCORD_ROLES
from bot.utils import error_embed, success_embed, is_admin


async def ensure_required_roles(guild: discord.Guild) -> tuple[list[str], list[str]]:
    """Create missing standard roles; return (created, existing)."""
    existing_by_name = {role.name: role for role in guild.roles}
    created, existing = [], []
    for name in REQUIRED_DISCORD_ROLES:
        if name in existing_by_name:
            existing.append(name)
            continue
        try:
            await guild.create_role(
                name=name,
                mentionable=True,
                reason="MetroCity RP standard role setup",
            )
            created.append(name)
        except discord.Forbidden:
            raise
    return created, existing


class RoleSetup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        """Provision the standard roles immediately after installation."""
        try:
            created, _ = await ensure_required_roles(guild)
            channel = guild.system_channel
            if channel and channel.permissions_for(guild.me).send_messages:
                await channel.send(
                    f"🇳🇬 MetroCity roles are ready. Created **{len(created)}** missing roles. "
                    "An administrator can run `/setup-roles` or `!setuproles` anytime."
                )
        except discord.Forbidden:
            # The bot needs Manage Roles. The admin command gives a useful error
            # if the permission is granted later.
            return

    @app_commands.command(
        name="setup-roles",
        description="[Admin] Create all standard MetroCity RP roles that are missing.",
    )
    async def setup_roles(self, interaction: discord.Interaction):
        # Role creation can take longer than Discord's three-second initial
        # response window, so acknowledge before doing any API work.
        await interaction.response.defer(ephemeral=True)
        if not is_admin(interaction.user):
            return await interaction.edit_original_response(
                embed=error_embed("Admins Only", "Server Administrators only."),
            )
        if not interaction.guild.me.guild_permissions.manage_roles:
            return await interaction.edit_original_response(
                embed=error_embed(
                    "Missing Permission",
                    "Give the bot **Manage Roles**, and make sure its own bot role is above the roles it must create.",
                ),
            )
        try:
            created, existing = await ensure_required_roles(interaction.guild)
        except discord.Forbidden:
            return await interaction.edit_original_response(
                embed=error_embed(
                    "Role Setup Failed",
                    "Discord rejected role creation. Give the bot Manage Roles and move its bot role above the target roles.",
                ),
            )
        await interaction.edit_original_response(
            embed=success_embed(
                "MetroCity Roles Ready",
                f"Created: **{len(created)}**\nAlready present: **{len(existing)}**\n\n"
                + (", ".join(created) if created else "No new roles were needed.")
            )
        )


async def setup(bot):
    await bot.add_cog(RoleSetup(bot))