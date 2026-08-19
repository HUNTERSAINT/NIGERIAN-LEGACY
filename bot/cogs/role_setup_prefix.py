"""Prefix command for manual role provisioning."""
from discord.ext import commands

from bot.cogs.role_setup import ensure_required_roles
from bot.utils import error_embed, success_embed, is_admin


class RoleSetupPrefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="setuproles", aliases=["createroles"])
    async def setuproles(self, ctx):
        """[Admin] Create missing MetroCity RP roles."""
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Server Administrators only."))
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send(embed=error_embed(
                "Missing Permission",
                "Give the bot Manage Roles and move its bot role above the target roles."
            ))
        try:
            created, existing = await ensure_required_roles(ctx.guild)
        except Exception:
            return await ctx.send(embed=error_embed(
                "Role Setup Failed",
                "Discord rejected role creation. Check Manage Roles and role hierarchy."
            ))
        await ctx.send(embed=success_embed(
            "MetroCity Roles Ready",
            f"Created: **{len(created)}** | Already present: **{len(existing)}**"
        ))


async def setup(bot):
    await bot.add_cog(RoleSetupPrefix(bot))