"""
Shared utility helpers.
"""
import discord
from bot.config import CURRENCY, COLOR_ERROR, COLOR_INFO, COLOR_SUCCESS, COLOR_WARN, GOV_ROLES


def fmt(amount: int) -> str:
    """Format a Naira amount with comma separators."""
    return f"{CURRENCY}{amount:,}"


def success_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"✅  {title}", description=description, color=COLOR_SUCCESS)
    return e


def error_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"❌  {title}", description=description, color=COLOR_ERROR)
    return e


def info_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=COLOR_INFO)
    return e


def warn_embed(title: str, description: str = "") -> discord.Embed:
    e = discord.Embed(title=f"⚠️  {title}", description=description, color=COLOR_WARN)
    return e


def has_gov_role(member: discord.Member) -> bool:
    """Return True if the member holds any government role."""
    return any(r.name in GOV_ROLES for r in member.roles)


def has_any_role(member: discord.Member, roles: set) -> bool:
    return any(r.name in roles for r in member.roles)


def role_names(member: discord.Member) -> list[str]:
    return [r.name for r in member.roles if r.name != "@everyone"]
