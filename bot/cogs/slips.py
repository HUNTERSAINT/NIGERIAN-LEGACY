"""Shareable virtual football betting slips, up to 10 games per slip."""
import asyncio
import json
import random
import secrets
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands

from bot.config import FOOTBALL_TEAMS, BET_MIN, HOUSE_EDGE, COLOR_BET
from bot.utils import fmt, success_embed, error_embed, info_embed, is_admin


def make_game():
    home, away = random.sample(FOOTBALL_TEAMS, 2)
    odds = {
        "home": round(random.uniform(1.5, 3.8), 2),
        "draw": round(random.uniform(2.8, 4.2), 2),
        "away": round(random.uniform(1.5, 3.8), 2),
    }
    return {"home": home, "away": away, "odds": odds}


def resolve_game(game):
    odds = game["odds"]
    result = random.choices(["home", "draw", "away"],
                            weights=[1 / odds["home"], 1 / odds["draw"], 1 / odds["away"]])[0]
    return result


class BettingSlips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settle_loop.start()

    def cog_unload(self):
        self.settle_loop.cancel()

    @property
    def db(self):
        return self.bot.db

    @tasks.loop(seconds=15)
    async def settle_loop(self):
        slips = await self.db.get_pending_betting_slips()
        for slip in slips:
            selections = json.loads(slip["selections"])
            won = True
            results = []
            total_odds = 1.0
            for game in selections:
                result = resolve_game(game)
                pick = game["pick"]
                results.append(result)
                total_odds *= game["odds"][pick]
                if pick != result:
                    won = False
            payout = int(slip["stake"] * total_odds * HOUSE_EDGE) if won else 0
            await self.db.settle_betting_slip(slip["id"], "won" if won else "lost", payout)
            if won:
                await self.db.update_wallet(slip["creator_id"], payout)
                await self.db.log_transaction(None, slip["creator_id"], payout, "slip_win",
                                              f"Bet slip {slip['code']}")
            channel = self.bot.get_channel(int(slip["channel_id"]))
            if channel:
                result_text = " ".join(f"{i+1}:{r.upper()}" for i, r in enumerate(results))
                title = "🎉 BET SLIP WON" if won else "❌ BET SLIP LOST"
                description = (
                    f"Slip **{slip['code']}**\n"
                    f"Results: `{result_text}`\n"
                    f"{'Payout: **' + fmt(payout) + '**' if won else 'No payout — one or more selections missed.'}"
                )
                await channel.send(embed=discord.Embed(title=title, description=description,
                                                       color=0x00B300 if won else 0xCC0000))

    @settle_loop.before_loop
    async def before_settle_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="slip-create", description="Create a shareable slip with up to 10 virtual games.")
    @app_commands.describe(amount="Stake in Naira.", selections="Comma-separated picks: home,draw,away (up to 10).")
    async def slip_create(self, interaction: discord.Interaction, amount: int, selections: str):
        await interaction.response.defer()
        await self._create(interaction.user, interaction.channel, amount, selections, interaction.followup.send)

    @app_commands.command(name="slip-play", description="Play someone else's shared betting slip code.")
    @app_commands.describe(code="Shared slip code.", amount="Your stake in Naira.")
    async def slip_play(self, interaction: discord.Interaction, code: str, amount: int):
        await interaction.response.defer()
        slip = await self.db.get_betting_slip(code.upper())
        if not slip:
            return await interaction.followup.send(embed=error_embed("Slip Not Found"))
        await self._play_existing(interaction.user, interaction.channel, slip, amount, interaction.followup.send)

    @app_commands.command(name="slip-info", description="View the games and picks inside a betting slip.")
    @app_commands.describe(code="Slip code.")
    async def slip_info(self, interaction: discord.Interaction, code: str):
        slip = await self.db.get_betting_slip(code.upper())
        if not slip:
            return await interaction.response.send_message(embed=error_embed("Slip Not Found"))
        selections = json.loads(slip["selections"])
        lines = []
        for i, game in enumerate(selections, 1):
            lines.append(f"**{i}.** {game['home']['name']} vs {game['away']['name']} — `{game['pick']}` @ {game['odds'][game['pick']]}x")
        embed = discord.Embed(title=f"🎟️ Betting Slip {slip['code']}",
                              description="\n".join(lines), color=COLOR_BET)
        embed.add_field(name="Games", value=str(len(selections)), inline=True)
        embed.add_field(name="Status", value=slip["status"].upper(), inline=True)
        embed.add_field(name="Potential", value=fmt(slip["potential"]), inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bet-max", description="[Admin] Set the maximum stake for bets and slips.")
    @app_commands.describe(amount="New maximum stake in Naira.")
    async def bet_max(self, interaction: discord.Interaction, amount: int):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Admins Only"), ephemeral=True)
        if amount < BET_MIN:
            return await interaction.response.send_message(embed=error_embed("Too Low", f"Minimum is {fmt(BET_MIN)}."), ephemeral=True)
        await self.db.set_max_bet(amount)
        await interaction.response.send_message(embed=success_embed("Maximum Bet Updated", f"New maximum: **{fmt(amount)}**."))

    async def _create(self, user, channel, amount, raw, send):
        max_bet = await self.db.get_max_bet()
        picks = [p.strip().lower() for p in raw.split(",") if p.strip()]
        if not picks or len(picks) > 10 or any(p not in {"home", "draw", "away"} for p in picks):
            return await send(embed=error_embed("Invalid Slip", "Use 1–10 comma-separated picks: `home,draw,away`."))
        if amount < BET_MIN or amount > max_bet:
            return await send(embed=error_embed("Invalid Stake", f"Stake must be {fmt(BET_MIN)}–{fmt(max_bet)}."))
        user_row = await self.db.get_or_create_user(str(user.id), user.display_name)
        if user_row["wallet"] < amount:
            return await send(embed=error_embed("Insufficient Funds", f"You need {fmt(amount)} in your wallet."))
        games = []
        total_odds = 1.0
        for pick in picks:
            game = make_game()
            game["pick"] = pick
            total_odds *= game["odds"][pick]
            games.append(game)
        potential = int(amount * total_odds * HOUSE_EDGE)
        code = "MC" + secrets.token_hex(4).upper()
        settles_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat(timespec="seconds")
        await self.db.update_wallet(str(user.id), -amount)
        await self.db.create_betting_slip(code, str(user.id), str(channel.id), json.dumps(games), amount, potential, settles_at)
        await self.db.log_transaction(str(user.id), None, amount, "slip_placed", f"Slip {code}")
        await send(embed=self._slip_embed(code, games, amount, potential))

    async def _play_existing(self, user, channel, original, amount, send):
        max_bet = await self.db.get_max_bet()
        if original["status"] != "pending":
            return await send(embed=error_embed("Slip Closed", "That slip has already been settled."))
        if amount < BET_MIN or amount > max_bet:
            return await send(embed=error_embed("Invalid Stake", f"Stake must be {fmt(BET_MIN)}–{fmt(max_bet)}."))
        user_row = await self.db.get_or_create_user(str(user.id), user.display_name)
        if user_row["wallet"] < amount:
            return await send(embed=error_embed("Insufficient Funds", f"You need {fmt(amount)}."))
        games = json.loads(original["selections"])
        total_odds = 1.0
        for game in games:
            total_odds *= game["odds"][game["pick"]]
        potential = int(amount * total_odds * HOUSE_EDGE)
        new_code = "MC" + secrets.token_hex(4).upper()
        settles_at = (datetime.utcnow() + timedelta(minutes=5)).isoformat(timespec="seconds")
        await self.db.update_wallet(str(user.id), -amount)
        await self.db.create_betting_slip(new_code, str(user.id), str(channel.id),
                                          json.dumps(games), amount, potential, settles_at)
        await self.db.log_transaction(str(user.id), None, amount, "slip_placed", f"Copied slip {original['code']}")
        await send(embed=self._slip_embed(new_code, games, amount, potential, copied=original["code"]))

    def _slip_embed(self, code, games, amount, potential, copied=None):
        lines = "\n".join(
            f"**{i}.** {g['home']['name']} vs {g['away']['name']} — `{g['pick']}` @ {g['odds'][g['pick']]}x"
            for i, g in enumerate(games, 1)
        )
        embed = discord.Embed(title="🎟️ Shareable Betting Slip", description=lines, color=COLOR_BET)
        embed.add_field(name="Slip Code", value=f"`{code}`", inline=True)
        embed.add_field(name="Stake", value=fmt(amount), inline=True)
        embed.add_field(name="Potential Win", value=fmt(potential), inline=True)
        embed.set_footer(text="Share the code. Others can use /slip-play or !slipplay with the same games.")
        return embed


async def setup(bot):
    await bot.add_cog(BettingSlips(bot))