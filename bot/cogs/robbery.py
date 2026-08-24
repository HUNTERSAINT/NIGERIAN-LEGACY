"""Risk-based player-to-player robbery for the Nigerian Legacy RP economy."""
import asyncio
import random
from datetime import datetime, timedelta

import discord
from discord.ext import commands
from discord import app_commands

from bot.config import (
    ROBBERY_COOLDOWN_H,
    ROBBERY_FAILURE_PENALTY_PERCENT,
    ROBBERY_MAX_STOLEN_PERCENT,
    ROBBERY_MIN_TARGET_WALLET,
    ROBBERY_SUCCESS_CHANCE,
)
from bot.utils import error_embed, fmt, success_embed, warn_embed


class Robbery(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._lock = asyncio.Lock()

    @property
    def db(self):
        return self.bot.db

    async def _rob(self, robber: discord.Member, target: discord.Member, send):
        if robber.id == target.id:
            return await send(embed=error_embed("Invalid Target", "You cannot rob yourself."))
        if target.bot:
            return await send(embed=error_embed("Invalid Target", "Bots cannot be robbed."))

        async with self._lock:
            robber_row = await self.db.get_or_create_user(str(robber.id), robber.display_name)
            target_row = await self.db.get_or_create_user(str(target.id), target.display_name)
            if target_row["wallet"] < ROBBERY_MIN_TARGET_WALLET:
                return await send(
                    embed=error_embed(
                        "Target Too Poor",
                        f"{target.display_name} needs at least {fmt(ROBBERY_MIN_TARGET_WALLET)} in their wallet.",
                    )
                )

            last = await self.db.get_last_robbery(str(robber.id))
            if last:
                last_time = datetime.fromisoformat(last["last_attempt"])
                available = last_time + timedelta(hours=ROBBERY_COOLDOWN_H)
                if datetime.utcnow() < available:
                    remaining = available - datetime.utcnow()
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes = remainder // 60
                    return await send(
                        embed=warn_embed(
                            "Robbery Cooldown",
                            f"You can try again in **{hours}h {minutes}m**.",
                        )
                    )

            await self.db.set_last_robbery(str(robber.id))
            if random.random() <= ROBBERY_SUCCESS_CHANCE:
                stolen = max(
                    1,
                    int(target_row["wallet"] * random.uniform(0.10, ROBBERY_MAX_STOLEN_PERCENT)),
                )
                stolen = min(stolen, target_row["wallet"])
                await self.db.update_wallet(str(target.id), -stolen)
                await self.db.update_wallet(str(robber.id), stolen)
                await self.db.log_transaction(
                    str(target.id), str(robber.id), stolen, "robbery",
                    f"Successful robbery by {robber.display_name}",
                )
                return await send(
                    embed=success_embed(
                        "Robbery Successful",
                        f"You robbed **{target.display_name}** and got **{fmt(stolen)}**.\n"
                        f"The victim lost the same amount.",
                    )
                )

            penalty = min(
                robber_row["wallet"],
                max(1, int(robber_row["wallet"] * ROBBERY_FAILURE_PENALTY_PERCENT)),
            )
            if penalty:
                await self.db.update_wallet(str(robber.id), -penalty)
                await self.db.update_wallet(str(target.id), penalty)
                await self.db.log_transaction(
                    str(robber.id), str(target.id), penalty, "robbery_failed",
                    f"Failed robbery against {target.display_name}",
                )
            return await send(
                embed=error_embed(
                    "Robbery Failed",
                    f"**{target.display_name}** caught you. "
                    f"You paid them **{fmt(penalty)}** as compensation.",
                )
            )

    @app_commands.command(
        name="rob",
        description="Attempt to rob another player's wallet. Use at your own risk.",
    )
    @app_commands.describe(target="The player you want to rob.")
    async def rob_slash(self, interaction: discord.Interaction, target: discord.Member):
        await interaction.response.defer()
        await self._rob(interaction.user, target, interaction.followup.send)

    @commands.command(name="rob")
    @commands.guild_only()
    async def rob_prefix(self, ctx: commands.Context, target: discord.Member):
        await self._rob(ctx.author, target, ctx.send)


async def setup(bot):
    await bot.add_cog(Robbery(bot))