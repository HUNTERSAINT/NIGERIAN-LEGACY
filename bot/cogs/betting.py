"""
🏟️ Virtual Football Betting
- New match every 5 minutes (3-min betting window → result)
- /bet <home|draw|away> <amount>
- Admin: /bet-start, /bet-stop, /bet-status, /bet-cancel
- Results weighted by generated odds; house edge 5%
"""
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import random
import logging

from bot.config import (
    FOOTBALL_TEAMS, BET_MIN, BET_MAX, BET_WINDOW_SECS, BET_WARNING_SECS,
    BET_RESULT_PAUSE, BET_CYCLE_SECS, HOUSE_EDGE,
    COLOR_BET, COLOR_SUCCESS, COLOR_ERROR, COLOR_GOLD, COLOR_WARN,
)
from bot.utils import fmt, success_embed, error_embed, warn_embed, is_admin
from bot.cogs.slips import BetBuilderView, make_market_games, market_embed

log = logging.getLogger("NigeriaRP.Betting")

CHOICES = {"home", "draw", "away"}


# ── helpers ───────────────────────────────────────────────────────────────────

def _generate_odds() -> tuple[float, float, float]:
    """Generate realistic-ish home/draw/away odds that roughly sum to ~2.9 implied prob."""
    home  = round(random.uniform(1.50, 3.80), 2)
    away  = round(random.uniform(1.50, 3.80), 2)
    draw  = round(random.uniform(2.80, 4.20), 2)
    return home, draw, away


def _pick_result(home_odds: float, draw_odds: float, away_odds: float) -> str:
    """Lower odds → higher probability. Convert to implied probs, normalise, pick."""
    h = 1 / home_odds
    d = 1 / draw_odds
    a = 1 / away_odds
    total = h + d + a
    h, d, a = h / total, d / total, a / total
    return random.choices(["home", "draw", "away"], weights=[h, d, a])[0]


def _score_for_result(result: str) -> tuple[int, int]:
    """Generate a plausible scoreline matching the result."""
    if result == "home":
        home = random.randint(1, 4)
        away = random.randint(0, home - 1)
    elif result == "away":
        away = random.randint(1, 4)
        home = random.randint(0, away - 1)
    else:  # draw
        goals = random.randint(0, 3)
        home = away = goals
    return home, away


def _match_embed(home: dict, away: dict, home_odds: float, draw_odds: float,
                 away_odds: float, match_id: int, max_bet: int,
                 status: str = "OPEN") -> discord.Embed:
    colour = COLOR_BET if status == "OPEN" else COLOR_WARN
    embed = discord.Embed(
        title=f"🏟️  VIRTUAL MATCH #{match_id}",
        description=(
            f"**{home['emoji']} {home['name']}**  vs  **{away['emoji']} {away['name']}**\n"
            f"`{home['league']} fixture`"
        ),
        color=colour,
    )
    embed.add_field(name=f"🏠 Home Win\n{home['name']}", value=f"Odds: **{home_odds}x**", inline=True)
    embed.add_field(name="🤝 Draw",                      value=f"Odds: **{draw_odds}x**", inline=True)
    embed.add_field(name=f"✈️ Away Win\n{away['name']}", value=f"Odds: **{away_odds}x**", inline=True)
    embed.add_field(
        name="💰 How to Bet",
        value=(
            f"`/bet home <amount>` — Back {home['name']}\n"
            f"`/bet draw <amount>` — Back the Draw\n"
            f"`/bet away <amount>` — Back {away['name']}\n\n"
            f"Min: {fmt(BET_MIN)}  |  Max: {fmt(max_bet)}"
        ),
        inline=False,
    )
    embed.set_footer(text=f"⏱️ Betting {status} — Results in ~{BET_WINDOW_SECS//60} minutes")
    return embed


# ── Cog ───────────────────────────────────────────────────────────────────────

class Betting(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._task: asyncio.Task | None = None
        self._running  = False
        self._channel: discord.TextChannel | None = None
        self._current_match_id: int | None = None   # DB id of open match
        self._current_home: dict | None = None
        self._current_away: dict | None = None
        self._current_home_odds: float = 0
        self._current_draw_odds: float = 0
        self._current_away_odds: float = 0

    @property
    def db(self):
        return self.bot.db

    # ── background cycle ──────────────────────────────────────────────────────

    async def _cycle(self):
        """Runs forever until self._running is False. Fully manages one 5-min cycle per iteration."""
        log.info("Betting cycle started.")
        while self._running:
            try:
                await self._run_one_match()
                # fill remaining time to hit 5-min total cycle
                elapsed_approx = BET_WINDOW_SECS + BET_WARNING_SECS + BET_RESULT_PAUSE + 10
                remaining = BET_CYCLE_SECS - elapsed_approx
                if remaining > 0 and self._running:
                    await asyncio.sleep(remaining)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Betting cycle error: {e}", exc_info=True)
                await asyncio.sleep(30)   # back off on error
        log.info("Betting cycle stopped.")

    async def _run_one_match(self):
        """Run a single match: announce → betting window → close → result → payouts."""
        if not self._channel or not self._running:
            return

        # Pick two distinct teams
        teams = random.sample(FOOTBALL_TEAMS, 2)
        home, away = teams[0], teams[1]
        home_odds, draw_odds, away_odds = _generate_odds()

        # Save to DB
        match_id = await self.db.create_match(
            home["name"], away["name"],
            home_odds, draw_odds, away_odds,
            str(self._channel.id),
        )
        self._current_match_id = match_id
        self._current_home = home
        self._current_away = away
        self._current_home_odds = home_odds
        self._current_draw_odds = draw_odds
        self._current_away_odds = away_odds

        # Announce
        max_bet = await self.db.get_max_bet()
        embed = _match_embed(
            home, away, home_odds, draw_odds, away_odds, match_id, max_bet, "OPEN"
        )
        try:
            msg = await self._channel.send(
                content="🚨 **NEW VIRTUAL MATCH — Place your bets!**",
                embed=embed,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except Exception as e:
            log.error(f"Failed to send match announcement: {e}")
            return

        # Wait most of the betting window, then warn
        wait_before_warn = BET_WINDOW_SECS - BET_WARNING_SECS
        await asyncio.sleep(wait_before_warn)
        if not self._running:
            return

        # 30-second warning
        try:
            await self._channel.send(
                embed=discord.Embed(
                    title="⏰  30 Seconds Left!",
                    description=f"Betting on **Match #{match_id}** closes in **30 seconds**. Get your bets in!",
                    color=COLOR_WARN,
                )
            )
        except Exception:
            pass

        await asyncio.sleep(BET_WARNING_SECS)
        if not self._running:
            return

        # Close betting
        await self.db.close_match(match_id)
        self._current_match_id = None

        try:
            await self._channel.send(
                embed=discord.Embed(
                    title="🔒  Betting Closed — Match #{} in Progress!".format(match_id),
                    description="No more bets accepted. Calculating result…",
                    color=COLOR_WARN,
                )
            )
        except Exception:
            pass

        await asyncio.sleep(BET_RESULT_PAUSE)

        # Compute result
        result = _pick_result(home_odds, draw_odds, away_odds)
        home_score, away_score = _score_for_result(result)
        await self.db.finish_match(match_id, result, home_score, away_score)

        # Work out winning odds
        winning_odds = {"home": home_odds, "draw": draw_odds, "away": away_odds}[result]
        result_label = {"home": home["name"], "draw": "Draw", "away": away["name"]}[result]
        result_emoji = {"home": "🏠", "draw": "🤝", "away": "✈️"}[result]

        # Settle bets
        bets = await self.db.get_match_bets(match_id)
        winners, losers, total_paid = [], [], 0

        for bet in bets:
            if bet["choice"] == result:
                payout = int(bet["amount"] * winning_odds * HOUSE_EDGE)
                profit = payout - bet["amount"]
                await self.db.settle_bet(bet["id"], payout)
                await self.db.update_wallet(bet["user_id"], payout)
                await self.db.log_transaction(
                    None, bet["user_id"], payout, "bet_win",
                    f"Bet win: Match #{match_id} — {result_label}"
                )
                winners.append((bet["user_id"], bet["amount"], payout, profit))
                total_paid += payout
            else:
                await self.db.settle_bet(bet["id"], 0)
                losers.append((bet["user_id"], bet["amount"]))

        # Result embed
        result_embed = discord.Embed(
            title=f"📣  FULL TIME — Match #{match_id}",
            description=(
                f"**{home['emoji']} {home['name']} {home_score}  —  {away_score} {away['emoji']} {away['name']}**\n\n"
                f"{result_emoji} **Result: {result_label.upper()} WIN** (odds {winning_odds}x)"
            ),
            color=COLOR_SUCCESS if winners else COLOR_ERROR,
        )

        if winners:
            winner_lines = "\n".join(
                f"Player {uid} bet {fmt(amt)} → won **{fmt(payout)}** (+{fmt(profit)})"
                for uid, amt, payout, profit in winners[:10]
            )
            result_embed.add_field(name=f"🏆 Winners ({len(winners)})", value=winner_lines or "—", inline=False)
        else:
            result_embed.add_field(name="🏆 Winners", value="No one picked the right result!", inline=False)

        result_embed.add_field(name="💀 Losers", value=str(len(losers)), inline=True)
        result_embed.add_field(name="💸 Total Paid Out", value=fmt(total_paid), inline=True)
        result_embed.set_footer(text="Next match starting soon… 🎯")

        try:
            await self._channel.send(embed=result_embed)
        except Exception as e:
            log.error(f"Failed to send result embed: {e}")

    # ── slash commands ─────────────────────────────────────────────────────────

    @app_commands.command(name="bet-start", description="[Admin] Start virtual football betting in a channel.")
    @app_commands.describe(channel="Channel to post matches in.")
    async def bet_start(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "Server Administrators only."), ephemeral=True)

        if self._running:
            return await interaction.response.send_message(
                embed=warn_embed("Already Running", f"Betting is already active in {self._channel.mention}.\nUse `/bet-stop` first."))

        self._channel  = channel
        self._running  = True
        await self.db.set_bet_setting(str(channel.id), True)

        self._task = asyncio.create_task(self._cycle())

        embed = discord.Embed(
            title="⚽  Virtual Football Betting — STARTED",
            description=(
                f"Matches will run every **5 minutes** in {channel.mention}.\n\n"
                f"🏠 `/bet home <amount>` — bet on home win\n"
                f"🤝 `/bet draw <amount>` — bet on a draw\n"
                f"✈️ `/bet away <amount>` — bet on away win\n\n"
                f"Min bet: {fmt(BET_MIN)}  |  Max bet: {fmt(await self.db.get_max_bet())}"
            ),
            color=COLOR_SUCCESS,
        )
        embed.set_footer(text="Good luck! 🍀")
        await interaction.response.send_message(embed=embed)
        await channel.send(
            embed=discord.Embed(
                title="🏟️  Virtual Football Betting is NOW OPEN!",
                description=(
                    f"A new virtual match drops every **5 minutes**.\n"
                    f"Use `/bet home|draw|away <amount>` to place wagers.\n"
                    f"Min: {fmt(BET_MIN)}  |  Max: {fmt(await self.db.get_max_bet())}\n\n"
                    f"First match coming up shortly…"
                ),
                color=COLOR_BET,
            )
        )

    @app_commands.command(name="bet-stop", description="[Admin] Stop virtual football betting.")
    async def bet_stop(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "Server Administrators only."), ephemeral=True)

        if not self._running:
            return await interaction.response.send_message(
                embed=warn_embed("Not Running", "Betting is not currently active."))

        self._running = False
        await self.db.set_bet_setting(None, False)

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Cancel any open match
        if self._current_match_id:
            await self.db.cancel_match(self._current_match_id)
            self._current_match_id = None

        if self._channel:
            try:
                await self._channel.send(
                    embed=discord.Embed(
                        title="🛑  Virtual Football Betting — STOPPED",
                        description="Betting has been stopped by an administrator. All open bets have been refunded.",
                        color=COLOR_ERROR,
                    )
                )
            except Exception:
                pass

        self._channel = None
        await interaction.response.send_message(
            embed=success_embed("Betting Stopped", "Virtual football betting has been halted."))

    @app_commands.command(name="bet-status", description="Check the current status of virtual football betting.")
    async def bet_status(self, interaction: discord.Interaction):
        setting = await self.db.get_bet_setting()
        embed = discord.Embed(title="⚽  Betting Status", color=COLOR_BET)

        if self._running and self._channel:
            embed.add_field(name="Status",  value="🟢 **ACTIVE**",             inline=True)
            embed.add_field(name="Channel", value=self._channel.mention,        inline=True)
            if self._current_match_id:
                embed.add_field(name="Current Match", value=f"#{self._current_match_id} — BETTING OPEN", inline=False)
            else:
                embed.add_field(name="Current Match", value="Waiting for next match…", inline=False)
        else:
            embed.add_field(name="Status", value="🔴 **INACTIVE**", inline=True)
            embed.add_field(name="Info", value="An admin can use `/bet-start` to begin.", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="bet", description="Open the football market or place a bet on the current match.")
    @app_commands.describe(
        choice="Leave blank to browse visible fixtures, or choose home, draw, or away.",
        amount="Amount in Naira to bet. Leave blank to browse the market.",
    )
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Home win", value="home"),
            app_commands.Choice(name="Draw", value="draw"),
            app_commands.Choice(name="Away win", value="away"),
        ]
    )
    async def bet(
        self,
        interaction: discord.Interaction,
        choice: str | None = None,
        amount: int | None = None,
    ):
        if choice is None and amount is None:
            slips = self.bot.get_cog("BettingSlips")
            if slips is None:
                return await interaction.response.send_message(
                    embed=error_embed(
                        "Betting Unavailable",
                        "The football betting slip system is not ready yet.",
                    ),
                    ephemeral=True,
                )
            featured = None
            if self._current_match_id and self._current_home and self._current_away:
                featured = {
                    "home": self._current_home,
                    "away": self._current_away,
                    "odds": {
                        "home": self._current_home_odds,
                        "draw": self._current_draw_odds,
                        "away": self._current_away_odds,
                    },
                    "match_id": self._current_match_id,
                }
            games = make_market_games(featured=featured)
            return await interaction.response.send_message(
                embed=market_embed(games),
                view=BetBuilderView(
                    self.bot, slips, interaction.user, interaction.channel, games
                ),
                ephemeral=True,
            )

        if choice is None or amount is None:
            return await interaction.response.send_message(
                embed=error_embed(
                    "Incomplete Bet",
                    "Choose an outcome and enter an amount, or use `/bet` by itself to browse fixtures.",
                ),
                ephemeral=True,
            )
        await interaction.response.defer()
        choice = choice.lower().strip()

        if choice not in CHOICES:
            return await interaction.followup.send(
                embed=error_embed("Invalid Choice", "Use `home`, `draw`, or `away`."))

        if not self._running or self._current_match_id is None:
            return await interaction.followup.send(
                embed=error_embed("No Active Match", "There is no open match to bet on right now. Wait for the next one!"))

        if amount < BET_MIN:
            return await interaction.followup.send(
                embed=error_embed("Bet Too Small", f"Minimum bet is {fmt(BET_MIN)}."))
        max_bet = await self.db.get_max_bet()
        if amount > max_bet:
            return await interaction.followup.send(
                embed=error_embed("Bet Too Large", f"Maximum bet is {fmt(max_bet)}."))

        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        if u["wallet"] < amount:
            return await interaction.followup.send(
                embed=error_embed("Insufficient Funds", f"You only have {fmt(u['wallet'])} in your wallet."))

        # Check for existing bet on this match
        existing = await self.db.get_user_match_bet(str(interaction.user.id), self._current_match_id)
        if existing:
            return await interaction.followup.send(
                embed=warn_embed("Already Bet", f"You already placed a bet on Match #{self._current_match_id}. One bet per match."))

        await self.db.update_wallet(str(interaction.user.id), -amount)
        await self.db.place_bet(self._current_match_id, str(interaction.user.id), choice, amount)
        await self.db.log_transaction(str(interaction.user.id), None, amount, "bet_placed",
                                      f"Bet: Match #{self._current_match_id} — {choice}")

        home  = self._current_home
        away  = self._current_away
        odds  = {"home": self._current_home_odds, "draw": self._current_draw_odds, "away": self._current_away_odds}[choice]
        label = {"home": home["name"], "draw": "Draw", "away": away["name"]}[choice]
        potential = int(amount * odds * HOUSE_EDGE)

        embed = discord.Embed(
            title="🎲  Bet Placed!",
            description=(
                f"**Match #{self._current_match_id}**: {home['name']} vs {away['name']}\n\n"
                f"Your pick: **{label.upper()}** at **{odds}x** odds\n"
                f"Stake: {fmt(amount)}\n"
                f"Potential win: **{fmt(potential)}** (+{fmt(potential - amount)} profit)"
            ),
            color=COLOR_BET,
        )
        embed.set_footer(text="Good luck! 🍀 Results announced after betting closes.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="bet-history", description="View your last 10 bet results.")
    async def bet_history(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        bets = await self.db.get_user_bets(str(interaction.user.id), 10)

        if not bets:
            return await interaction.followup.send(embed=discord.Embed(
                title="No Bet History", description="You haven't placed any bets yet.", color=COLOR_BET))

        embed = discord.Embed(title="🎲  Your Bet History", color=COLOR_BET)
        for b in bets:
            if not b["settled"]:
                status = "⏳ Pending"
            elif b["payout"] and b["payout"] > 0:
                profit = b["payout"] - b["amount"]
                status = f"✅ Won {fmt(b['payout'])} (+{fmt(profit)})"
            else:
                status = f"❌ Lost {fmt(b['amount'])}"

            embed.add_field(
                name=f"Match #{b['match_id']} — {b['choice'].upper()}",
                value=f"Stake: {fmt(b['amount'])}  |  {status}\n{b['created_at'][:16]}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="bet-stats", description="View your overall betting statistics.")
    async def bet_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        stats = await self.db.get_user_bet_stats(str(interaction.user.id))

        embed = discord.Embed(title="📊  Your Betting Stats", color=COLOR_BET)
        embed.add_field(name="🎲 Total Bets",    value=str(stats["total"]),         inline=True)
        embed.add_field(name="✅ Wins",           value=str(stats["wins"]),          inline=True)
        embed.add_field(name="❌ Losses",         value=str(stats["losses"]),        inline=True)
        embed.add_field(name="💰 Total Wagered",  value=fmt(stats["total_wagered"]), inline=True)
        embed.add_field(name="🏆 Total Won",      value=fmt(stats["total_won"]),     inline=True)
        net = stats["total_won"] - stats["total_wagered"]
        embed.add_field(name="📈 Net P&L",        value=fmt(net),                    inline=True)
        win_rate = (stats["wins"] / stats["total"] * 100) if stats["total"] > 0 else 0
        embed.add_field(name="🎯 Win Rate",       value=f"{win_rate:.1f}%",          inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="bet-cancel", description="[Admin] Cancel the current open match and refund all bets.")
    async def bet_cancel(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "Server Administrators only."), ephemeral=True)

        if self._current_match_id is None:
            return await interaction.response.send_message(
                embed=warn_embed("No Open Match", "There is no match currently open to cancel."))

        mid = self._current_match_id
        await interaction.response.defer()

        bets = await self.db.get_match_bets(mid)
        refunded = 0
        for bet in bets:
            if not bet["settled"]:
                await self.db.update_wallet(bet["user_id"], bet["amount"])
                await self.db.log_transaction(None, bet["user_id"], bet["amount"], "bet_refund",
                                              f"Refund: Match #{mid} cancelled")
                refunded += 1

        await self.db.cancel_match(mid)
        self._current_match_id = None

        if self._channel:
            try:
                await self._channel.send(embed=discord.Embed(
                    title=f"🚫  Match #{mid} Cancelled",
                    description=f"Match #{mid} was cancelled by an administrator. **{refunded} bet(s) refunded.**",
                    color=COLOR_ERROR,
                ))
            except Exception:
                pass

        await interaction.followup.send(
            embed=success_embed(f"Match #{mid} Cancelled", f"{refunded} bet(s) refunded to wallets."))


async def setup(bot):
    await bot.add_cog(Betting(bot))
