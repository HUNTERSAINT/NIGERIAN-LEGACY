"""Shared 15-second virtual roulette rounds for the Nigerian Legacy RP economy."""
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
    ROULETTE_MAX_BET,
    ROULETTE_ROUND_SECS,
)
from bot.utils import error_embed, fmt, is_admin, success_embed
from bot.cogs.setup_system import channel_matches


RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
}
BET_OPTIONS = {"red", "black", "green", "odd", "even", "high", "low", "number"}


def roulette_result_file(number: int, colour: str) -> discord.File:
    """Create a compact circular result image with the number and colour visible."""
    background = {"red": (150, 25, 35), "black": (20, 24, 31), "green": (0, 135, 81)}[colour]
    image = Image.new("RGB", (420, 420), (245, 247, 250))
    draw = ImageDraw.Draw(image)
    draw.ellipse((30, 30, 390, 390), fill=background, outline=(255, 255, 255), width=8)
    try:
        number_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 150)
        colour_font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    except OSError:
        number_font = colour_font = ImageFont.load_default()
    number_text = str(number)
    box = draw.textbbox((0, 0), number_text, font=number_font)
    draw.text(
        ((420 - (box[2] - box[0])) / 2, 105),
        number_text,
        fill="white",
        font=number_font,
        stroke_width=2,
        stroke_fill=(0, 0, 0),
    )
    label = colour.upper()
    box = draw.textbbox((0, 0), label, font=colour_font)
    draw.text(((420 - (box[2] - box[0])) / 2, 285), label, fill="white", font=colour_font)
    buffer = BytesIO()
    image.save(buffer, "PNG", optimize=True)
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
        self._rounds: dict[str, dict] = {}
        self._round_lock = asyncio.Lock()

    @property
    def db(self):
        return self.bot.db

    async def _finish_round(self, guild_id: str):
        await asyncio.sleep(ROULETTE_ROUND_SECS)
        async with self._round_lock:
            round_data = self._rounds.pop(guild_id, None)
        if not round_data:
            return

        number = random.randint(0, 36)
        colour = number_colour(number)
        lines = []
        total_staked = 0
        total_paid = 0
        for entry in round_data["bets"]:
            won = bet_won(entry["bet"], number, entry["number"])
            payout = entry["amount"] * payout_multiplier(entry["bet"]) if won else 0
            if payout:
                await self.db.update_wallet(entry["user_id"], payout)
                await self.db.log_transaction(
                    None, entry["user_id"], payout, "roulette_win",
                    f"Roulette round win: {entry['bet']}",
                )
            total_staked += entry["amount"]
            total_paid += payout
            display_bet = f"number {entry['number']}" if entry["bet"] == "number" else entry["bet"]
            status = f"WIN +{fmt(payout)}" if won else "LOSS"
            lines.append(f"<@{entry['user_id']}> — {display_bet.upper()} — {status}")

        embed = discord.Embed(
            title="🎰 Roulette Result",
            description=(
                f"**{number} — {colour.upper()}**\n\n"
                + "\n".join(lines)
                + f"\n\nTotal staked: **{fmt(total_staked)}**"
                f"\nTotal paid: **{fmt(total_paid)}**"
            ),
            color=COLOR_SUCCESS if total_paid else COLOR_ERROR,
        )
        embed.set_image(url="attachment://roulette-result.png")
        embed.set_footer(text="New bets open in the next roulette round.")
        try:
            await round_data["channel"].send(embed=embed, file=roulette_result_file(number, colour))
        except discord.HTTPException:
            # Bets are already settled; keep the bot alive if a channel is unavailable.
            pass

    async def _play(self, user, bet, amount, selected_number, send, guild_id, channel):
        if not await self.db.get_roulette_enabled(guild_id):
            return await send(embed=error_embed("Roulette Offline", "An administrator has turned roulette off."))
        bet = bet.lower().strip()
        if bet not in BET_OPTIONS:
            return await send(embed=error_embed(
                "Invalid Roulette Bet",
                "Choose red, black, green, odd, even, high, low, or number.",
            ))
        if bet == "number" and selected_number is None:
            return await send(embed=error_embed("Number Required", "For a number bet, enter a number from 0 to 36."))
        if selected_number is not None and not 0 <= selected_number <= 36:
            return await send(embed=error_embed("Invalid Number", "Roulette numbers run from 0 to 36."))
        if amount < BET_MIN or amount > ROULETTE_MAX_BET:
            return await send(embed=error_embed(
                "Invalid Stake",
                f"Roulette stakes must be between {fmt(BET_MIN)} and {fmt(ROULETTE_MAX_BET)}.",
            ))

        async with self._round_lock:
            round_data = self._rounds.get(guild_id)
            if round_data and any(entry["user_id"] == str(user.id) for entry in round_data["bets"]):
                return await send(embed=error_embed(
                    "Already In This Round",
                    "You already placed a bet in this 15-second session. Wait for the result.",
                ))
            user_row = await self.db.get_or_create_user(str(user.id), user.display_name)
            if user_row["wallet"] < amount:
                return await send(embed=error_embed(
                    "Insufficient Funds", f"You only have {fmt(user_row['wallet'])} in your wallet.",
                ))
            await self.db.update_wallet(str(user.id), -amount)
            await self.db.log_transaction(
                str(user.id), None, amount, "roulette_spin", f"Roulette round bet: {bet}"
            )
            if not round_data:
                round_data = {"channel": channel, "bets": []}
                self._rounds[guild_id] = round_data
                asyncio.create_task(self._finish_round(guild_id))
                opening = await send(embed=discord.Embed(
                    title="🎰 Roulette Bets Open",
                    description=f"Betting is open for **{ROULETTE_ROUND_SECS} seconds**.\n"
                                "Other players can join this session now.",
                    color=0xC0392B,
                ))
            round_data["bets"].append({
                "user_id": str(user.id),
                "bet": bet,
                "number": selected_number,
                "amount": amount,
            })
        if round_data["bets"] and len(round_data["bets"]) > 1:
            return await send(embed=success_embed(
                "Bet Accepted",
                f"Your **{bet.upper()}** bet of **{fmt(amount)}** joined the current round.\n"
                f"Result arrives when the {ROULETTE_ROUND_SECS}-second window closes.",
            ))
        return opening

    @app_commands.command(name="roulette", description="Join the shared 15-second roulette betting round.")
    @app_commands.describe(
        bet="red, black, green, odd, even, high, low, or number",
        amount="Amount in Naira to stake.",
        number="Required only when betting on a specific number (0–36).",
    )
    @app_commands.choices(bet=[
        app_commands.Choice(name="Red", value="red"),
        app_commands.Choice(name="Black", value="black"),
        app_commands.Choice(name="Green (0)", value="green"),
        app_commands.Choice(name="Odd", value="odd"),
        app_commands.Choice(name="Even", value="even"),
        app_commands.Choice(name="High (19–36)", value="high"),
        app_commands.Choice(name="Low (1–18)", value="low"),
        app_commands.Choice(name="Specific number", value="number"),
    ])
    async def roulette_slash(self, interaction: discord.Interaction, bet: str, amount: int, number: int | None = None):
        if not interaction.guild or not channel_matches(interaction.channel, "roulette"):
            return await interaction.response.send_message(
                embed=error_embed("Roulette Channel Only", "Roulette commands can only be used in #roulette."),
                ephemeral=True,
            )
        await interaction.response.defer()
        await self._play(interaction.user, bet, amount, number, interaction.followup.send,
                         str(interaction.guild.id), interaction.channel)

    @commands.command(name="roulette")
    @commands.guild_only()
    async def roulette_prefix(self, ctx: commands.Context, bet: str, amount: int, number: int | None = None):
        if not channel_matches(ctx.channel, "roulette"):
            return await ctx.send(embed=error_embed("Roulette Channel Only", "Roulette commands can only be used in #roulette."))
        await self._play(ctx.author, bet, amount, number, ctx.send, str(ctx.guild.id), ctx.channel)

    @app_commands.command(name="roulette-toggle", description="[Admin] Turn roulette on or off for this server.")
    @app_commands.describe(enabled="Whether roulette should accept new rounds.")
    async def roulette_toggle(self, interaction: discord.Interaction, enabled: bool):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Access Denied", "Server Administrators only."), ephemeral=True)
        await self.db.set_roulette_enabled(str(interaction.guild.id), enabled)
        await interaction.response.send_message(embed=success_embed("Roulette Updated", f"Roulette is now **{'ON' if enabled else 'OFF'}** for this server."))

    @commands.command(name="roulettetoggle")
    @commands.guild_only()
    async def roulette_toggle_prefix(self, ctx: commands.Context, state: str):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Server Administrators only."))
        if state.lower() not in {"on", "off", "true", "false", "1", "0", "yes", "no"}:
            return await ctx.send(embed=error_embed("Invalid State", "Use `on` or `off`."))
        enabled = state.lower() in {"on", "true", "1", "yes"}
        await self.db.set_roulette_enabled(str(ctx.guild.id), enabled)
        await ctx.send(embed=success_embed("Roulette Updated", f"Roulette is now **{'ON' if enabled else 'OFF'}** for this server."))


async def setup(bot):
    await bot.add_cog(Roulette(bot))