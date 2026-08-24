"""Virtual roulette for the Nigerian Legacy RP economy."""
import asyncio
from io import BytesIO
import random

import discord
from discord.ext import commands
from discord import app_commands
from PIL import Image, ImageDraw, ImageFont

from bot.config import (
    BET_MIN,
    COLOR_ERROR,
    COLOR_SUCCESS,
    ROULETTE_COOLDOWN_SECS,
    ROULETTE_MAX_BET,
)
from bot.utils import error_embed, fmt, is_admin, success_embed
from bot.cogs.setup_system import CHANNELS, channel_matches


RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}
BET_OPTIONS = {"red", "black", "green", "odd", "even", "high", "low", "number"}


def roulette_result_file(number: int, colour: str) -> discord.File:
    """Create a shareable visual result card for the spin."""
    background = {"red": (150, 25, 35), "black": (20, 24, 31), "green": (0, 135, 81)}[colour]
    image = Image.new("RGB", (900, 500), background)
    draw = ImageDraw.Draw(image)
    try:
        large = ImageFont.truetype("DejaVuSans-Bold.ttf", 190)
        small = ImageFont.truetype("DejaVuSans-Bold.ttf", 46)
    except OSError:
        large = small = ImageFont.load_default()
    number_text = str(number)
    box = draw.textbbox((0, 0), number_text, font=large)
    draw.text(((900 - (box[2] - box[0])) / 2, 90), number_text, fill="white", font=large)
    label = f"{colour.upper()} • ROULETTE RESULT"
    box = draw.textbbox((0, 0), label, font=small)
    draw.text(((900 - (box[2] - box[0])) / 2, 360), label, fill="white", font=small)
    buffer = BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="roulette-result.png")


def number_colour(number: int) -> str:
    if number == 0:
        return "green"
    return "red" if number in RED_NUMBERS else "black"


def bet_won(bet: str, number: int, selected_number: int | None) -> bool:
    colour = number_colour(number)
    if bet == "number":
        return selected_number == number
    if bet in {"red", "black", "green"}:
        return colour == bet
    if bet == "odd":
        return number != 0 and number % 2 == 1
    if bet == "even":
        return number != 0 and number % 2 == 0
    if bet == "high":
        return 19 <= number <= 36
    if bet == "low":
        return 1 <= number <= 18
    return False


def payout_multiplier(bet: str) -> int:
    return 36 if bet in {"number", "green"} else 2


class Roulette(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._spin_lock = asyncio.Lock()
        self._cooldowns: dict[int, float] = {}

    @property
    def db(self):
        return self.bot.db

    async def _play(
        self,
        user: discord.abc.User,
        bet: str,
        amount: int,
        selected_number: int | None,
        send,
        guild_id: str,
    ):
        if not await self.db.get_roulette_enabled(guild_id):
            return await send(embed=error_embed(
                "Roulette Offline", "An administrator has turned roulette off."
            ))
        now = asyncio.get_running_loop().time()
        remaining = ROULETTE_COOLDOWN_SECS - (now - self._cooldowns.get(user.id, 0))
        if remaining > 0:
            return await send(embed=error_embed(
                "Roulette Cooldown",
                f"Wait **{remaining:.0f} seconds** before spinning again.",
            ))
        bet = bet.lower().strip()
        if bet not in BET_OPTIONS:
            return await send(
                embed=error_embed(
                    "Invalid Roulette Bet",
                    "Choose red, black, green, odd, even, high, low, or number.",
                )
            )
        if bet == "number" and selected_number is None:
            return await send(
                embed=error_embed(
                    "Number Required",
                    "For a number bet, enter a number from 0 to 36.",
                )
            )
        if selected_number is not None and not 0 <= selected_number <= 36:
            return await send(
                embed=error_embed("Invalid Number", "Roulette numbers run from 0 to 36.")
            )

        if amount < BET_MIN or amount > ROULETTE_MAX_BET:
            return await send(
                embed=error_embed(
                    "Invalid Stake",
                    f"Roulette stakes must be between {fmt(BET_MIN)} and {fmt(ROULETTE_MAX_BET)}.",
                )
            )

        async with self._spin_lock:
            now = asyncio.get_running_loop().time()
            remaining = ROULETTE_COOLDOWN_SECS - (now - self._cooldowns.get(user.id, 0))
            if remaining > 0:
                return await send(embed=error_embed(
                    "Roulette Cooldown",
                    f"Wait **{remaining:.0f} seconds** before spinning again.",
                ))
            user_row = await self.db.get_or_create_user(str(user.id), user.display_name)
            if user_row["wallet"] < amount:
                return await send(
                    embed=error_embed(
                        "Insufficient Funds",
                        f"You only have {fmt(user_row['wallet'])} in your wallet.",
                    )
                )

            self._cooldowns[user.id] = now
            number = random.randint(0, 36)
            colour = number_colour(number)
            won = bet_won(bet, number, selected_number)
            payout = amount * payout_multiplier(bet) if won else 0
            await self.db.update_wallet(str(user.id), -amount)
            await self.db.log_transaction(
                str(user.id), None, amount, "roulette_spin", f"Roulette bet: {bet}"
            )
            if won:
                await self.db.update_wallet(str(user.id), payout)
                await self.db.log_transaction(
                    None,
                    str(user.id),
                    payout,
                    "roulette_win",
                    f"Roulette win: {bet}",
                )

        display_bet = (
            f"number {selected_number}"
            if bet == "number"
            else bet
        )
        embed = discord.Embed(
            title="🎰 Roulette Spin",
            description=(
                f"The wheel landed on **{number} ({colour.upper()})**.\n\n"
                f"Your bet: **{display_bet.upper()}**\n"
                f"Stake: **{fmt(amount)}**\n"
                + (
                    f"Result: **WIN** — payout **{fmt(payout)}**"
                    if won
                    else "Result: **LOSS** — better luck on the next spin."
                )
            ),
            color=COLOR_SUCCESS if won else COLOR_ERROR,
        )
        embed.set_image(url="attachment://roulette-result.png")
        embed.set_footer(text="Play responsibly • Use /roulette in #roulette")
        return await send(embed=embed, file=roulette_result_file(number, colour))

    @app_commands.command(
        name="roulette",
        description="Spin the roulette wheel with your Nigerian Legacy wallet.",
    )
    @app_commands.describe(
        bet="red, black, green, odd, even, high, low, or number",
        amount="Amount in Naira to stake.",
        number="Required only when betting on a specific number (0–36).",
    )
    @app_commands.choices(
        bet=[
            app_commands.Choice(name="Red", value="red"),
            app_commands.Choice(name="Black", value="black"),
            app_commands.Choice(name="Green (0)", value="green"),
            app_commands.Choice(name="Odd", value="odd"),
            app_commands.Choice(name="Even", value="even"),
            app_commands.Choice(name="High (19–36)", value="high"),
            app_commands.Choice(name="Low (1–18)", value="low"),
            app_commands.Choice(name="Specific number", value="number"),
        ]
    )
    async def roulette_slash(
        self,
        interaction: discord.Interaction,
        bet: str,
        amount: int,
        number: int | None = None,
    ):
        if not interaction.guild or not channel_matches(interaction.channel, "roulette"):
            return await interaction.response.send_message(
                embed=error_embed(
                    "Roulette Channel Only",
                    "Roulette commands can only be used in #roulette.",
                ),
                ephemeral=True,
            )
        await interaction.response.defer()
        await self._play(
            interaction.user,
            bet,
            amount,
            number,
            interaction.followup.send,
            str(interaction.guild.id),
        )

    @commands.command(name="roulette")
    @commands.guild_only()
    async def roulette_prefix(
        self, ctx: commands.Context, bet: str, amount: int, number: int | None = None
    ):
        if not channel_matches(ctx.channel, "roulette"):
            return await ctx.send(
                embed=error_embed(
                    "Roulette Channel Only",
                    "Roulette commands can only be used in #roulette.",
                )
            )
        await self._play(ctx.author, bet, amount, number, ctx.send, str(ctx.guild.id))

    @app_commands.command(
        name="roulette-toggle",
        description="[Admin] Turn roulette on or off for this server.",
    )
    @app_commands.describe(enabled="Whether roulette should accept new spins.")
    async def roulette_toggle(self, interaction: discord.Interaction, enabled: bool):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "Server Administrators only."),
                ephemeral=True,
            )
        await self.db.set_roulette_enabled(str(interaction.guild.id), enabled)
        await interaction.response.send_message(
            embed=success_embed(
                "Roulette Updated",
                f"Roulette is now **{'ON' if enabled else 'OFF'}** for this server.",
            )
        )

    @commands.command(name="roulettetoggle")
    @commands.guild_only()
    async def roulette_toggle_prefix(self, ctx: commands.Context, state: str):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Server Administrators only."))
        enabled = state.lower() in {"on", "true", "1", "yes"}
        if state.lower() not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            return await ctx.send(embed=error_embed("Invalid State", "Use `on` or `off`."))
        await self.db.set_roulette_enabled(str(ctx.guild.id), enabled)
        await ctx.send(embed=success_embed(
            "Roulette Updated",
            f"Roulette is now **{'ON' if enabled else 'OFF'}** for this server.",
        ))


async def setup(bot):
    await bot.add_cog(Roulette(bot))