"""
Citizen economy commands: /balance, /pay, /deposit, /withdraw, /work, /daily,
/history, /inventory, /leaderboard, /payfine
"""
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

from bot.config import (
    DAILY_STIPEND, DAILY_COOLDOWN_H, WORK_COOLDOWN_H,
    JOBS, MAX_TRANSFER, BANK_TRANSFER_FEE, COLOR_INFO, COLOR_GOLD,
)
from bot.utils import fmt, success_embed, error_embed, info_embed, warn_embed


class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /balance ──────────────────────────────────────────────────────────────

    @app_commands.command(name="balance", description="View your wallet and bank balance.")
    @app_commands.describe(member="Check another member's balance (optional).")
    async def balance(self, interaction: discord.Interaction, member: discord.Member = None):
        target = member or interaction.user
        u = await self.db.get_or_create_user(str(target.id), target.display_name)

        embed = discord.Embed(
            title=f"💰  {target.display_name}'s Account",
            color=COLOR_GOLD,
        )
        embed.add_field(name="👛 Wallet", value=fmt(u["wallet"]), inline=True)
        embed.add_field(name="🏦 Bank", value=fmt(u["bank"]), inline=True)
        embed.add_field(name="💼 Total Net Worth", value=fmt(u["wallet"] + u["bank"]), inline=False)
        embed.add_field(name="🪪 Job", value=u["job"], inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="🇳🇬 Nigerian Government RP Economy")
        await interaction.response.send_message(embed=embed)

    # ── /pay ──────────────────────────────────────────────────────────────────

    @app_commands.command(name="pay", description="Transfer money from your wallet to another user.")
    @app_commands.describe(recipient="Who to send money to.", amount="Amount in Naira.")
    async def pay(self, interaction: discord.Interaction, recipient: discord.Member, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount", "Amount must be positive."))
        if amount > MAX_TRANSFER:
            return await interaction.followup.send(embed=error_embed("Limit Exceeded", f"Single transfer cap is {fmt(MAX_TRANSFER)}."))
        if recipient.id == interaction.user.id:
            return await interaction.followup.send(embed=error_embed("Self-Transfer", "You cannot pay yourself."))

        sender = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        fee = max(1, int(amount * BANK_TRANSFER_FEE))
        total = amount + fee

        if sender["wallet"] < total:
            return await interaction.followup.send(
                embed=error_embed("Insufficient Funds",
                                  f"You need {fmt(total)} (includes {fmt(fee)} fee) but only have {fmt(sender['wallet'])} in your wallet.")
            )

        await self.db.get_or_create_user(str(recipient.id), recipient.display_name)
        await self.db.update_wallet(str(interaction.user.id), -total)
        await self.db.update_wallet(str(recipient.id), amount)
        # Fee goes to treasury
        await self.db.update_treasury(fee)
        await self.db.log_transaction(
            str(interaction.user.id), str(recipient.id), amount, "transfer",
            f"Transfer fee {fmt(fee)} to treasury"
        )

        embed = success_embed(
            "Transfer Complete",
            f"{fmt(amount)} sent to **{recipient.display_name}**.\n"
            f"Transfer fee: {fmt(fee)} (to National Treasury)."
        )
        await interaction.followup.send(embed=embed)

    # ── /deposit ──────────────────────────────────────────────────────────────

    @app_commands.command(name="deposit", description="Deposit cash from your wallet into the bank.")
    @app_commands.describe(amount="Amount to deposit (or 'all').")
    async def deposit(self, interaction: discord.Interaction, amount: str):
        await interaction.response.defer()
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)

        if amount.lower() == "all":
            amt = u["wallet"]
        else:
            try:
                amt = int(amount)
            except ValueError:
                return await interaction.followup.send(embed=error_embed("Invalid Amount", "Enter a number or 'all'."))

        if amt <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount", "Must be positive."))
        if u["wallet"] < amt:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"You only have {fmt(u['wallet'])} in your wallet."))

        await self.db.update_wallet(str(interaction.user.id), -amt)
        await self.db.update_bank(str(interaction.user.id), amt)
        await self.db.log_transaction(str(interaction.user.id), None, amt, "deposit")

        await interaction.followup.send(embed=success_embed("Deposit Successful", f"{fmt(amt)} moved from wallet to bank."))

    # ── /withdraw ─────────────────────────────────────────────────────────────

    @app_commands.command(name="withdraw", description="Withdraw cash from your bank to your wallet.")
    @app_commands.describe(amount="Amount to withdraw (or 'all').")
    async def withdraw(self, interaction: discord.Interaction, amount: str):
        await interaction.response.defer()
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)

        if amount.lower() == "all":
            amt = u["bank"]
        else:
            try:
                amt = int(amount)
            except ValueError:
                return await interaction.followup.send(embed=error_embed("Invalid Amount", "Enter a number or 'all'."))

        if amt <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount", "Must be positive."))
        if u["bank"] < amt:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"You only have {fmt(u['bank'])} in your bank."))

        await self.db.update_bank(str(interaction.user.id), -amt)
        await self.db.update_wallet(str(interaction.user.id), amt)
        await self.db.log_transaction(None, str(interaction.user.id), amt, "withdrawal")

        await interaction.followup.send(embed=success_embed("Withdrawal Successful", f"{fmt(amt)} moved from bank to wallet."))

    # ── /work ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="work", description="Work your job to earn income.")
    async def work(self, interaction: discord.Interaction):
        await interaction.response.defer()
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)

        if u["last_work"]:
            last = datetime.fromisoformat(u["last_work"])
            cooldown_end = last + timedelta(hours=WORK_COOLDOWN_H)
            if datetime.utcnow() < cooldown_end:
                remaining = cooldown_end - datetime.utcnow()
                hrs, rem = divmod(int(remaining.total_seconds()), 3600)
                mins = rem // 60
                return await interaction.followup.send(
                    embed=warn_embed("Cooldown Active", f"You can work again in **{hrs}h {mins}m**."))

        job = u["job"]
        earnings = JOBS.get(job, JOBS["Citizen"])["work"]

        await self.db.update_wallet(str(interaction.user.id), earnings)
        await self.db.set_last_work(str(interaction.user.id))
        await self.db.log_transaction(None, str(interaction.user.id), earnings, "work", f"Work income: {job}")

        embed = success_embed(
            f"Work Complete — {job}",
            f"You worked as a **{job}** and earned **{fmt(earnings)}**.\n"
            f"Next work available in **{WORK_COOLDOWN_H} hours**."
        )
        await interaction.followup.send(embed=embed)

    # ── /daily ────────────────────────────────────────────────────────────────

    @app_commands.command(name="daily", description="Claim your daily government stipend.")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer()
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)

        if u["last_daily"]:
            last = datetime.fromisoformat(u["last_daily"])
            cooldown_end = last + timedelta(hours=DAILY_COOLDOWN_H)
            if datetime.utcnow() < cooldown_end:
                remaining = cooldown_end - datetime.utcnow()
                hrs, rem = divmod(int(remaining.total_seconds()), 3600)
                mins = rem // 60
                return await interaction.followup.send(
                    embed=warn_embed("Already Claimed", f"Come back in **{hrs}h {mins}m**."))

        await self.db.update_wallet(str(interaction.user.id), DAILY_STIPEND)
        await self.db.set_last_daily(str(interaction.user.id))
        await self.db.log_transaction(None, str(interaction.user.id), DAILY_STIPEND, "daily", "Daily stipend")

        embed = success_embed(
            "Daily Stipend Claimed",
            f"You received **{fmt(DAILY_STIPEND)}** from the government.\n"
            f"Come back in {DAILY_COOLDOWN_H} hours for your next stipend."
        )
        await interaction.followup.send(embed=embed)

    # ── /history ──────────────────────────────────────────────────────────────

    @app_commands.command(name="history", description="View your last 10 transactions.")
    async def history(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        txs = await self.db.get_user_transactions(str(interaction.user.id), 10)

        if not txs:
            return await interaction.followup.send(embed=info_embed("No Transactions", "You have no transaction history yet."))

        embed = discord.Embed(title="📋  Transaction History", color=COLOR_INFO)
        uid = str(interaction.user.id)
        for tx in txs:
            direction = "→ OUT" if tx["from_id"] == uid else "← IN"
            note = f" — {tx['note']}" if tx["note"] else ""
            embed.add_field(
                name=f"{direction}  {fmt(tx['amount'])}  [{tx['type'].upper()}]",
                value=f"{tx['created_at']}{note}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── /inventory ────────────────────────────────────────────────────────────

    @app_commands.command(name="inventory", description="View your profile, job, and financial summary.")
    async def inventory(self, interaction: discord.Interaction):
        await interaction.response.defer()
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        fines = await self.db.get_unpaid_fines(str(interaction.user.id))
        loans = await self.db.get_active_loans(str(interaction.user.id))
        bizs  = await self.db.get_user_businesses(str(interaction.user.id))

        embed = discord.Embed(title=f"🗂  {interaction.user.display_name}'s Profile", color=COLOR_INFO)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="💼 Job",       value=u["job"],            inline=True)
        embed.add_field(name="👛 Wallet",    value=fmt(u["wallet"]),    inline=True)
        embed.add_field(name="🏦 Bank",      value=fmt(u["bank"]),      inline=True)
        embed.add_field(name="💰 Net Worth", value=fmt(u["wallet"]+u["bank"]), inline=True)

        fine_total = sum(f["amount"] for f in fines)
        embed.add_field(name="⚖️ Unpaid Fines",  value=fmt(fine_total) if fine_total else "None", inline=True)

        loan_total = sum(l["outstanding"] for l in loans)
        embed.add_field(name="🏛 Active Loans",  value=fmt(loan_total) if loan_total else "None", inline=True)

        if bizs:
            biz_names = ", ".join(b["name"] for b in bizs)
            embed.add_field(name="🏢 Businesses", value=biz_names, inline=False)

        embed.set_footer(text=f"Account created: {u['created_at'][:10]}")
        await interaction.followup.send(embed=embed)

    # ── /leaderboard ──────────────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="View the richest citizens in Nigeria.")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        users = await self.db.richest_users(10)
        total_supply = await self.db.total_money_supply()
        treasury = await self.db.get_treasury()

        embed = discord.Embed(title="🏆  Richest Citizens — Nigeria", color=COLOR_GOLD)
        medals = ["🥇", "🥈", "🥉"] + ["4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        for i, u in enumerate(users):
            embed.add_field(
                name=f"{medals[i]}  {u['username']}",
                value=f"{fmt(u['wallet']+u['bank'])}  |  Job: {u['job']}",
                inline=False,
            )
        embed.add_field(name="💰 Total Money Supply", value=fmt(total_supply), inline=True)
        embed.add_field(name="🏛 Treasury",           value=fmt(treasury["balance"]), inline=True)
        await interaction.followup.send(embed=embed)

    # ── /payfine ──────────────────────────────────────────────────────────────

    @app_commands.command(name="payfine", description="Pay an outstanding fine.")
    @app_commands.describe(fine_id="Fine ID from /fines list.")
    async def payfine(self, interaction: discord.Interaction, fine_id: int):
        await interaction.response.defer()
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        fines = await self.db.get_unpaid_fines(str(interaction.user.id))
        fine = next((f for f in fines if f["id"] == fine_id), None)

        if not fine:
            return await interaction.followup.send(embed=error_embed("Fine Not Found", "No unpaid fine with that ID found on your account."))
        if u["wallet"] < fine["amount"]:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"You need {fmt(fine['amount'])} but only have {fmt(u['wallet'])}."))

        await self.db.update_wallet(str(interaction.user.id), -fine["amount"])
        await self.db.update_treasury(fine["amount"])
        await self.db.pay_fine(fine_id)
        await self.db.log_transaction(str(interaction.user.id), None, fine["amount"], "fine_payment", f"Fine #{fine_id}: {fine['reason']}")

        await interaction.followup.send(embed=success_embed("Fine Paid", f"Fine of {fmt(fine['amount'])} for *{fine['reason']}* has been paid."))

    # ── /fines ────────────────────────────────────────────────────────────────

    @app_commands.command(name="fines", description="View your unpaid fines.")
    async def fines(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.db.ensure_user(str(interaction.user.id), interaction.user.display_name)
        fines = await self.db.get_unpaid_fines(str(interaction.user.id))

        if not fines:
            return await interaction.followup.send(embed=success_embed("No Fines", "You have no outstanding fines. 🎉"))

        embed = discord.Embed(title="⚖️  Unpaid Fines", color=0xCC4400)
        for f in fines:
            embed.add_field(
                name=f"Fine #{f['id']} — {fmt(f['amount'])}",
                value=f"Reason: {f['reason']}\nIssued by: {f['issued_by']}\nDate: {f['created_at'][:10]}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Economy(bot))
