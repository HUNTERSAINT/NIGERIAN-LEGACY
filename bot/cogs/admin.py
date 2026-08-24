"""
Admin commands:
  /economy-stats, /addmoney, /removemoney, /resetuser, /synccommands, /help
"""
import discord
from discord.ext import commands
from discord import app_commands

from bot.config import COLOR_INFO, COLOR_GOLD, JOBS, CURRENCY
from bot.utils import fmt, success_embed, error_embed, info_embed


def admin_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message(
            embed=error_embed("Access Denied", "Server Administrators only."), ephemeral=True
        )
        return False
    return app_commands.check(predicate)


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /economy-stats ────────────────────────────────────────────────────────

    @app_commands.command(name="economy-stats", description="Full national economy dashboard.")
    async def economy_stats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        treasury   = await self.db.get_treasury()
        total_supply = await self.db.total_money_supply()
        ministries = await self.db.get_all_ministries()
        top_users  = await self.db.richest_users(5)
        top_biz    = await self.db.top_businesses(5)

        total_budget = sum(m["budget"] for m in ministries)
        total_spent  = sum(m["spent"]  for m in ministries)

        embed = discord.Embed(
            title="📊  Nigerian Economy Dashboard",
            color=COLOR_GOLD,
        )
        embed.add_field(name="🏛 Treasury",          value=fmt(treasury["balance"]),  inline=True)
        embed.add_field(name="💵 Citizens' Money",   value=fmt(total_supply),         inline=True)
        embed.add_field(name="🏢 Ministries",        value=str(len(ministries)),      inline=True)
        embed.add_field(name="📦 Ministry Budgets",  value=fmt(total_budget),         inline=True)
        embed.add_field(name="💸 Ministry Spending", value=fmt(total_spent),          inline=True)

        if top_users:
            top_str = "\n".join(
                f"{i+1}. {u['username']} — {fmt(u['wallet']+u['bank'])}"
                for i, u in enumerate(top_users)
            )
            embed.add_field(name="🏆 Top 5 Citizens", value=top_str, inline=False)

        if top_biz:
            biz_str = "\n".join(
                f"{i+1}. {b['name']} ({b['industry']}) — {fmt(b['balance'])}"
                for i, b in enumerate(top_biz)
            )
            embed.add_field(name="🏢 Top 5 Businesses", value=biz_str, inline=False)

        embed.set_footer(text="🇳🇬 Federal Republic of Nigeria — Live Economy Data")
        await interaction.followup.send(embed=embed)

    # ── /addmoney ─────────────────────────────────────────────────────────────

    @app_commands.command(name="addmoney", description="[Admin] Add money to a user's wallet.")
    @app_commands.describe(member="Target user.", amount="Amount to add.", reason="Reason.")
    @admin_only()
    async def addmoney(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Admin adjustment"):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.update_wallet(str(member.id), amount)
        await self.db.log_transaction(None, str(member.id), amount, "admin_add", reason)

        await interaction.followup.send(embed=success_embed("Money Added", f"{fmt(amount)} added to {member.display_name}'s wallet.\nReason: {reason}"))

    # ── /removemoney ──────────────────────────────────────────────────────────

    @app_commands.command(name="removemoney", description="[Admin] Remove money from a user's wallet.")
    @app_commands.describe(member="Target user.", amount="Amount to remove.", reason="Reason.")
    @admin_only()
    async def removemoney(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Admin adjustment"):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        u = await self.db.get_or_create_user(str(member.id), member.display_name)
        deduct = min(amount, u["wallet"])
        await self.db.update_wallet(str(member.id), -deduct)
        await self.db.log_transaction(str(member.id), None, deduct, "admin_remove", reason)

        await interaction.followup.send(embed=success_embed("Money Removed", f"{fmt(deduct)} removed from {member.display_name}'s wallet.\nReason: {reason}"))

    # ── /resetuser ────────────────────────────────────────────────────────────

    @app_commands.command(name="resetuser", description="[Admin] Reset a user's account to defaults.")
    @app_commands.describe(member="User to reset.")
    @admin_only()
    async def resetuser(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        await self.db.execute(
            "UPDATE users SET wallet=50000, bank=0, job='Citizen', last_work=NULL, last_daily=NULL WHERE user_id=?",
            (str(member.id),),
        )
        await interaction.followup.send(embed=success_embed("User Reset", f"{member.display_name}'s account has been reset to defaults."))

    # ── /synccommands ─────────────────────────────────────────────────────────

    @app_commands.command(name="synccommands", description="[Admin] Force sync slash commands to this server.")
    @admin_only()
    async def synccommands(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        synced = await self.bot.tree.sync()
        await interaction.followup.send(embed=success_embed("Commands Synced", f"{len(synced)} slash commands synced."))

    # ── /help ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Show all available bot commands.")
    async def help_cmd(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🇳🇬  Nigerian Government RP Economy Bot — Commands",
            description="All amounts are in **₦ Naira**.",
            color=COLOR_INFO,
        )

        embed.add_field(name="👤 Citizen", value=(
            "`/balance` `/pay` `/deposit` `/withdraw`\n"
            "`/work` `/daily` `/history` `/inventory`\n"
            "`/fines` `/payfine` `/leaderboard`"
        ), inline=False)

        embed.add_field(name="💼 Jobs", value=(
            "`/jobs` `/myjob` `/setjob` *(Admin/President)*"
        ), inline=False)

        embed.add_field(name="🏛 Government", value=(
            "`/treasury` `/grant` `/fine` `/salary-pay`\n"
            "`/tax-collect` `/request-allocation` `/approve-allocation`\n"
            "`/deny-allocation` `/allocations`\n"
            "`/contract-award` `/contracts`\n"
            "`/ministries` `/ministry-create` `/deposit-treasury`"
        ), inline=False)

        embed.add_field(name="🏦 Banking (CBN)", value=(
            "`/loan-request` `/loan-status` `/loan-repay`\n"
            "`/interest-rates` `/cbn-print` `/cbn-seize`"
        ), inline=False)

        embed.add_field(name="🏢 Business", value=(
            "`/business-register` `/business-info`\n"
            "`/business-deposit` `/business-withdraw`\n"
            "`/business-list` `/business-top` `/business-tax`"
        ), inline=False)

        embed.add_field(name="⚽ Football Betting", value=(
            "`/bet` — browse fixtures, odds, and build a multi-match slip\n"
            "`/bet home|draw|away <amount>` — place a direct bet\n"
            "`/bet-history` `/bet-stats`\n"
            "`/bet-start` `/bet-stop` `/bet-status` `/bet-cancel` *(Admin)*\n"
            "`/slip-create` `/slip-play` `/slip-info` `/bet-max`"
        ), inline=False)

        embed.add_field(name="🎰 Games & Support", value=(
            "`/roulette` *(#roulette only)* · `/roulette-toggle` *(Admin)*\n"
            "`/rob @player` · `/ticket` · `/ticket-close`"
        ), inline=False)
        
        embed.add_field(name="🏪 Store & Role Income", value=(
            "`/store` `/buy` `/store-add` `/store-remove`\n"
            "`/role-income-create` `/role-income-list` `/role-income-toggle`"
        ), inline=False)

        embed.add_field(name="📊 Admin", value=(
            "`/economy-stats` `/addmoney` `/removemoney`\n"
            "`/resetuser` `/synccommands`"
        ), inline=False)

        embed.set_footer(text="🔐 Government/Finance/CBN commands require the appropriate Discord role.")
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(Admin(bot))
