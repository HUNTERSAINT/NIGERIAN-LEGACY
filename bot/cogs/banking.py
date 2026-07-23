"""
Banking commands:
  /loan-request, /loan-repay, /loan-status, /interest-rates
Central Bank commands (CBN role):
  /cbn-print, /cbn-rates
"""
import discord
from discord.ext import commands
from discord import app_commands

from bot.config import INTEREST_RATE, LOAN_MAX_RATIO, CBN_ROLES, COLOR_INFO, COLOR_GOLD
from bot.utils import fmt, success_embed, error_embed, info_embed, warn_embed, has_any_role


class Banking(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /loan-request ──────────────────────────────────────────────────────────

    @app_commands.command(name="loan-request", description="Request a loan from the Central Bank of Nigeria.")
    @app_commands.describe(amount="Loan amount in Naira.")
    async def loan_request(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        max_loan = int((u["wallet"] + u["bank"]) * LOAN_MAX_RATIO)

        if amount > max_loan:
            return await interaction.followup.send(
                embed=error_embed(
                    "Loan Limit Exceeded",
                    f"Maximum loan for your net worth is {fmt(max_loan)} ({LOAN_MAX_RATIO}× net worth)."
                )
            )

        treasury = await self.db.get_treasury()
        if treasury["balance"] < amount:
            return await interaction.followup.send(embed=error_embed("CBN Insufficient Reserves", "The Central Bank cannot service this loan right now."))

        active_loans = await self.db.get_active_loans(str(interaction.user.id))
        if active_loans:
            return await interaction.followup.send(embed=warn_embed("Existing Loan", "Repay your current loan before taking a new one."))

        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(interaction.user.id), amount)
        await self.db.create_loan(str(interaction.user.id), amount, INTEREST_RATE)
        await self.db.log_transaction(None, str(interaction.user.id), amount, "loan_disbursement", "CBN Loan")

        embed = success_embed(
            "Loan Approved — CBN",
            f"**{fmt(amount)}** disbursed to your wallet.\n"
            f"Interest rate: **{INTEREST_RATE*100:.1f}% / 24h**\n"
            f"Repayment due: **30 days**\n\n"
            f"Use `/loan-repay <loan_id> <amount>` to repay."
        )
        await interaction.followup.send(embed=embed)

    # ── /loan-status ──────────────────────────────────────────────────────────

    @app_commands.command(name="loan-status", description="Check your active loans.")
    async def loan_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        loans = await self.db.get_active_loans(str(interaction.user.id))

        if not loans:
            return await interaction.followup.send(embed=info_embed("No Active Loans", "You have no outstanding loans. 🎉"))

        embed = discord.Embed(title="🏛  Active Loans", color=COLOR_INFO)
        for l in loans:
            embed.add_field(
                name=f"Loan #{l['id']}",
                value=(
                    f"Principal: {fmt(l['principal'])}\n"
                    f"Outstanding: {fmt(l['outstanding'])}\n"
                    f"Rate: {l['interest_rate']*100:.1f}%/24h\n"
                    f"Due: {l['due_at'][:10] if l['due_at'] else 'N/A'}"
                ),
                inline=True,
            )
        await interaction.followup.send(embed=embed)

    # ── /loan-repay ───────────────────────────────────────────────────────────

    @app_commands.command(name="loan-repay", description="Repay part or all of a loan.")
    @app_commands.describe(loan_id="Loan ID from /loan-status.", amount="Amount to repay.")
    async def loan_repay(self, interaction: discord.Interaction, loan_id: int, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        loans = await self.db.get_active_loans(str(interaction.user.id))
        loan = next((l for l in loans if l["id"] == loan_id), None)

        if not loan:
            return await interaction.followup.send(embed=error_embed("Loan Not Found", f"No active loan #{loan_id} on your account."))

        pay = min(amount, loan["outstanding"])
        if u["wallet"] < pay:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"You need {fmt(pay)} but only have {fmt(u['wallet'])}."))

        new_outstanding = await self.db.repay_loan(loan_id, pay)
        await self.db.update_wallet(str(interaction.user.id), -pay)
        await self.db.update_treasury(pay)
        await self.db.log_transaction(str(interaction.user.id), None, pay, "loan_repayment", f"Loan #{loan_id} repayment")

        if new_outstanding == 0:
            msg = f"Loan #{loan_id} fully repaid! 🎉"
        else:
            msg = f"Repaid {fmt(pay)}. Remaining: {fmt(new_outstanding)}."

        await interaction.followup.send(embed=success_embed("Loan Repayment", msg))

    # ── /interest-rates ───────────────────────────────────────────────────────

    @app_commands.command(name="interest-rates", description="View current CBN interest rates.")
    async def interest_rates(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📊  CBN Interest Rates", color=COLOR_GOLD)
        embed.add_field(name="Loan Interest Rate", value=f"{INTEREST_RATE*100:.1f}% per 24 hours", inline=False)
        embed.add_field(name="Loan Maximum Ratio", value=f"{LOAN_MAX_RATIO}× your net worth", inline=False)
        embed.add_field(name="Loan Term", value="30 days", inline=False)
        embed.add_field(name="Transfer Fee", value="0.5% (paid to Treasury)", inline=False)
        embed.set_footer(text="Central Bank of Nigeria — Monetary Policy")
        await interaction.response.send_message(embed=embed)

    # ── /cbn-print ────────────────────────────────────────────────────────────

    @app_commands.command(name="cbn-print", description="[CBN Governor] Print new money into the Treasury.")
    @app_commands.describe(amount="Amount to mint.", reason="Justification.")
    async def cbn_print(self, interaction: discord.Interaction, amount: int, reason: str):
        await interaction.response.defer()
        if not has_any_role(interaction.user, CBN_ROLES):
            return await interaction.followup.send(embed=error_embed("Access Denied", "Requires CBN Governor or President."), ephemeral=True)
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        await self.db.update_treasury(amount)
        await self.db.log_transaction(None, None, amount, "money_printing", reason)

        embed = discord.Embed(
            title="🖨️  CBN — Money Printed",
            description=(
                f"**{fmt(amount)}** minted and added to the National Treasury.\n"
                f"Justification: *{reason}*\n"
                f"Authorised by: {interaction.user.display_name}\n\n"
                f"⚠️ Excessive printing causes inflation."
            ),
            color=COLOR_GOLD,
        )
        await interaction.followup.send(embed=embed)

    # ── /cbn-seize ────────────────────────────────────────────────────────────

    @app_commands.command(name="cbn-seize", description="[CBN Governor] Seize funds from a citizen's account.")
    @app_commands.describe(member="Target citizen.", amount="Amount to seize.", reason="Legal basis.")
    async def cbn_seize(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str):
        await interaction.response.defer()
        if not has_any_role(interaction.user, CBN_ROLES):
            return await interaction.followup.send(embed=error_embed("Access Denied", "Requires CBN Governor or President."), ephemeral=True)

        u = await self.db.get_or_create_user(str(member.id), member.display_name)
        available = u["wallet"] + u["bank"]
        seized = min(amount, available)

        # Seize from wallet first, then bank
        from_wallet = min(seized, u["wallet"])
        from_bank   = seized - from_wallet

        if from_wallet > 0:
            await self.db.update_wallet(str(member.id), -from_wallet)
        if from_bank > 0:
            await self.db.update_bank(str(member.id), -from_bank)

        await self.db.update_treasury(seized)
        await self.db.log_transaction(str(member.id), None, seized, "seizure", reason)

        embed = discord.Embed(
            title="🔒  Account Seizure",
            description=(
                f"**{fmt(seized)}** seized from **{member.display_name}**.\n"
                f"Reason: *{reason}*\nBy: {interaction.user.display_name}"
            ),
            color=0x800000,
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Banking(bot))
