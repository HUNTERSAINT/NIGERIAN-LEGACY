"""Shareable football betting slips and the interactive bet builder."""
import asyncio
import json
import random
import secrets
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands

from bot.config import FOOTBALL_TEAMS, BET_MIN, HOUSE_EDGE, COLOR_BET, COLOR_ERROR
from bot.utils import fmt, success_embed, error_embed, info_embed, is_admin


MARKET_LABELS = {
    "home": "Home win", "draw": "Draw", "away": "Away win",
    "double_home_draw": "Double chance: Home or Draw",
    "double_draw_away": "Double chance: Draw or Away",
    "double_home_away": "Double chance: Home or Away",
    "over_0_5": "Over 0.5 goals", "under_0_5": "Under 0.5 goals",
    "over_1_5": "Over 1.5 goals", "under_1_5": "Under 1.5 goals",
    "over_2_5": "Over 2.5 goals", "under_2_5": "Under 2.5 goals",
    "over_3_5": "Over 3.5 goals", "under_3_5": "Under 3.5 goals",
    "btts_yes": "Both teams to score: Yes", "btts_no": "Both teams to score: No",
    "home_over_0_5": "Home team over 0.5", "away_over_0_5": "Away team over 0.5",
    "over_8_5_corners": "Over 8.5 corners", "under_8_5_corners": "Under 8.5 corners",
    "over_3_5_cards": "Over 3.5 cards", "under_3_5_cards": "Under 3.5 cards",
}


def make_game():
    home, away = random.sample(FOOTBALL_TEAMS, 2)
    odds = {
        "home": round(random.uniform(1.5, 3.8), 2),
        "draw": round(random.uniform(2.8, 4.2), 2),
        "away": round(random.uniform(1.5, 3.8), 2),
    }
    odds.update({
        key: round(random.uniform(1.25, 2.35), 2)
        for key in MARKET_LABELS if key not in odds
    })
    return {"home": home, "away": away, "odds": odds}


def make_market_games(count: int = 4, featured: dict | None = None) -> list[dict]:
    """Build visible fixtures for the interactive builder."""
    games = []
    if featured:
        games.append(featured)
    while len(games) < count:
        game = make_game()
        if any(
            game["home"]["name"] == existing["home"]["name"]
            and game["away"]["name"] == existing["away"]["name"]
            for existing in games
        ):
            continue
        games.append(game)
    return games


def market_embed(games: list[dict], picks: dict[int, str] | None = None) -> discord.Embed:
    picks = picks or {}
    lines = []
    for index, game in enumerate(games):
        selected = picks.get(index)
        selected_text = f" — **{selected.upper()} selected**" if selected else ""
        lines.append(
            f"**{index + 1}. {game['home']['emoji']} {game['home']['name']} "
            f"vs {game['away']['emoji']} {game['away']['name']}**{selected_text}\n"
            f"   Home `{game['odds']['home']}x` · Draw `{game['odds']['draw']}x` · "
            f"Away `{game['odds']['away']}x`\n"
            f"   Goals: O/U 1.5 `{game['odds']['over_1_5']}x`/`{game['odds']['under_1_5']}x` · "
            f"BTTS `{game['odds']['btts_yes']}x`/`{game['odds']['btts_no']}x`\n"
            f"   Corners: O/U 8.5 `{game['odds']['over_8_5_corners']}x`/`{game['odds']['under_8_5_corners']}x` · "
            f"Cards: O/U 3.5 `{game['odds']['over_3_5_cards']}x`/`{game['odds']['under_3_5_cards']}x`"
        )
    embed = discord.Embed(
        title="⚽ Football Betting Market",
        description=(
            "These are the fixtures currently available for a bet builder. "
            "Choose an outcome from each fixture you want to add, then confirm your stake.\n\n"
            + "\n\n".join(lines)
        ),
        color=COLOR_BET,
    )
    embed.set_footer(text="You can combine up to 4 visible fixtures on one slip.")
    return embed


def resolve_game(game):
    odds = game["odds"]
    result = random.choices(["home", "draw", "away"],
                            weights=[1 / odds["home"], 1 / odds["draw"], 1 / odds["away"]])[0]
    return result


def resolve_market_game(game):
    result = resolve_game(game)
    if result == "home":
        home_goals = random.randint(1, 4)
        away_goals = random.randint(0, home_goals - 1)
    elif result == "away":
        away_goals = random.randint(1, 4)
        home_goals = random.randint(0, away_goals - 1)
    else:
        home_goals = away_goals = random.randint(0, 3)
    corners = random.randint(5, 14)
    cards = random.randint(1, 7)
    return result, home_goals, away_goals, corners, cards


def market_won(pick, result, home_goals, away_goals, corners=0, cards=0):
    total = home_goals + away_goals
    return {
        "home": result == "home", "draw": result == "draw", "away": result == "away",
        "double_home_draw": result in {"home", "draw"},
        "double_draw_away": result in {"draw", "away"},
        "double_home_away": result in {"home", "away"},
        "over_0_5": total > 0, "under_0_5": total < 1,
        "over_1_5": total > 1, "under_1_5": total < 2,
        "over_2_5": total > 2, "under_2_5": total < 3,
        "over_3_5": total > 3, "under_3_5": total < 4,
        "btts_yes": home_goals > 0 and away_goals > 0,
        "btts_no": home_goals == 0 or away_goals == 0,
        "home_over_0_5": home_goals > 0, "away_over_0_5": away_goals > 0,
        "over_8_5_corners": corners > 8, "under_8_5_corners": corners < 9,
        "over_3_5_cards": cards > 3, "under_3_5_cards": cards < 4,
    }.get(pick, False)


class MarketSelect(discord.ui.Select):
    def __init__(self, builder: "BetBuilderView", index: int, game: dict):
        self.builder = builder
        self.index = index
        home = game["home"]["name"]
        away = game["away"]["name"]
        options = [
            discord.SelectOption(
                label=(f"{MARKET_LABELS[key]} — {home}" if key == "home"
                       else f"{MARKET_LABELS[key]} — {away}" if key == "away"
                       else MARKET_LABELS[key])[:100],
                description=f"{game['odds'][key]}x odds",
                value=key,
            )
            for key in MARKET_LABELS
        ]
        super().__init__(
            placeholder=f"Fixture {index + 1}: choose an outcome",
            options=options,
            min_values=0,
            max_values=1,
            row=index,
        )

    async def callback(self, interaction: discord.Interaction):
        self.builder.picks[self.index] = self.values[0] if self.values else None
        if self.builder.picks[self.index] is None:
            self.builder.picks.pop(self.index, None)
        await interaction.response.edit_message(
            embed=market_embed(self.builder.games, self.builder.picks),
            view=self.builder,
        )


class BetBuilderStakeModal(discord.ui.Modal):
    def __init__(self, builder: "BetBuilderView", games: list[dict]):
        super().__init__(title="Confirm Bet Builder")
        self.builder = builder
        self.games = games
        self.stake = discord.ui.TextInput(
            label="Stake in Naira",
            placeholder=f"Minimum {BET_MIN:,}",
            required=True,
            max_length=12,
        )
        self.add_item(self.stake)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(str(self.stake.value).replace(",", "").strip())
        except ValueError:
            return await interaction.response.send_message(
                embed=error_embed("Invalid Stake", "Enter a whole number in Naira."),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        await self.builder.slips._create_from_games(
            self.builder.owner,
            self.builder.channel,
            amount,
            self.games,
            interaction.followup.send,
        )


class BetBuilderView(discord.ui.View):
    """Interactive market embedded in the existing football betting flow."""

    def __init__(self, bot, slips, owner, channel, games: list[dict]):
        super().__init__(timeout=300)
        self.bot = bot
        self.slips = slips
        self.owner = owner
        self.owner_id = owner.id
        self.channel = channel
        self.games = games
        self.picks: dict[int, str] = {}
        for index, game in enumerate(games):
            self.add_item(MarketSelect(self, index, game))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This bet builder belongs to the player who opened it.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(
        label="Confirm selections",
        style=discord.ButtonStyle.success,
        row=4,
    )
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.picks:
            return await interaction.response.send_message(
                embed=error_embed(
                    "No Fixtures Selected",
                    "Choose at least one visible fixture before confirming.",
                ),
                ephemeral=True,
            )
        selected_games = []
        for index, pick in sorted(self.picks.items()):
            game = dict(self.games[index])
            game["pick"] = pick
            selected_games.append(game)
        await interaction.response.send_modal(
            BetBuilderStakeModal(self, selected_games)
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.secondary,
        row=4,
    )
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)


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
                result, home_goals, away_goals, corners, cards = resolve_market_game(game)
                pick = game["pick"]
                results.append(result)
                total_odds *= game["odds"][pick]
                if not market_won(pick, result, home_goals, away_goals, corners, cards):
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

    async def matches_message(self):
        games = make_market_games(count=10)
        embed = market_embed(games)
        embed.title = "⚽ Next 10 Shareable Slip Matches"
        embed.set_footer(text="Use /bet to choose selections and create a shareable slip.")
        return embed

    @commands.command(name="matches")
    @commands.guild_only()
    async def matches_prefix(self, ctx):
        if not await self.db.get_matches_enabled():
            return await ctx.send(embed=error_embed(
                "Matches Disabled", "An administrator has disabled the public match list."
            ))
        await ctx.send(embed=await self.matches_message())

    @app_commands.command(name="matches", description="Show the next 10 matches for shareable slips.")
    async def matches_slash(self, interaction: discord.Interaction):
        if not await self.db.get_matches_enabled():
            return await interaction.response.send_message(
                embed=error_embed("Matches Disabled", "An administrator has disabled the public match list."),
                ephemeral=True,
            )
        await interaction.response.send_message(embed=await self.matches_message(), ephemeral=True)

    @app_commands.command(name="matches-toggle", description="[Admin] Enable or disable the public match list.")
    async def matches_toggle(self, interaction: discord.Interaction, enabled: bool):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Admins Only", "Server Administrators only."), ephemeral=True
            )
        await self.db.set_matches_enabled(enabled)
        await interaction.response.send_message(embed=success_embed(
            "Match List Updated", f"Public matches are now **{'ON' if enabled else 'OFF'}**."
        ))

    @commands.command(name="matchestoggle")
    @commands.guild_only()
    async def matches_toggle_prefix(self, ctx, state: str):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Server Administrators only."))
        if state.lower() not in {"on", "off"}:
            return await ctx.send(embed=error_embed("Invalid State", "Use `on` or `off`."))
        enabled = state.lower() == "on"
        await self.db.set_matches_enabled(enabled)
        await ctx.send(embed=success_embed(
            "Match List Updated", f"Public matches are now **{'ON' if enabled else 'OFF'}**."
        ))

    @app_commands.command(name="slip-create", description="Create a shareable slip from the visible football market.")
    @app_commands.describe(
        amount="Stake in Naira. Leave blank to enter it after choosing fixtures.",
        selections="Optional legacy picks: home,draw,away (up to 10).",
    )
    async def slip_create(
        self,
        interaction: discord.Interaction,
        amount: int | None = None,
        selections: str | None = None,
    ):
        if selections is None:
            games = make_market_games()
            return await interaction.response.send_message(
                embed=market_embed(games),
                view=BetBuilderView(
                    self.bot, self, interaction.user, interaction.channel, games
                ),
                ephemeral=True,
            )
        await interaction.response.defer()
        if amount is None:
            return await interaction.followup.send(
                embed=error_embed("Stake Required", "Enter a stake when using legacy picks.")
            )
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
        picks = [p.strip().lower() for p in raw.split(",") if p.strip()]
        if not picks or len(picks) > 10 or any(p not in {"home", "draw", "away"} for p in picks):
            return await send(embed=error_embed("Invalid Slip", "Use 1–10 comma-separated picks: `home,draw,away`."))
        games = []
        for pick in picks:
            game = make_game()
            game["pick"] = pick
            games.append(game)
        await self._create_from_games(user, channel, amount, games, send)

    async def _create_from_games(self, user, channel, amount, games, send):
        max_bet = await self.db.get_max_bet()
        if not games or len(games) > 10:
            return await send(embed=error_embed("Invalid Slip", "Choose 1–10 fixtures."))
        if amount < BET_MIN or amount > max_bet:
            return await send(embed=error_embed("Invalid Stake", f"Stake must be {fmt(BET_MIN)}–{fmt(max_bet)}."))
        user_row = await self.db.get_or_create_user(str(user.id), user.display_name)
        if user_row["wallet"] < amount:
            return await send(embed=error_embed("Insufficient Funds", f"You need {fmt(amount)} in your wallet."))
        total_odds = 1.0
        for game in games:
            if game.get("pick") not in {"home", "draw", "away"}:
                return await send(embed=error_embed("Invalid Selection", "Every fixture needs a valid home, draw, or away pick."))
            total_odds *= game["odds"][game["pick"]]
        potential = int(amount * total_odds * HOUSE_EDGE)
        code = "NL" + secrets.token_hex(4).upper()
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
        new_code = "NL" + secrets.token_hex(4).upper()
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
        embed.set_footer(text="Share the code. Others can use /slip-play with the same games.")
        return embed


async def setup(bot):
    await bot.add_cog(BettingSlips(bot))