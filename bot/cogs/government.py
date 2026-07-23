"""
Government commands:
  /salary pay, /treasury, /grant, /fine, /tax-collect,
  /request-allocation, /approve-allocation, /deny-allocation,
  /contract-award, /contracts, /ministries, /ministry-create
"""
import discord
from discord.ext import commands
from discord import app_commands

from bot.config import (
    COLOR_GOLD, COLOR_INFO, FINANCE_ROLES, POLICE_ROLES,
    JUDICIARY_ROLES, GOV_ROLES, JOBS,
)
from bot.utils import (
    fmt, success_embed, error_embed, info_embed, warn_embed,
    has_any_role,
)


def gov_check():
    """Interaction check: caller must have a government role."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if has_any_role(interaction.user, GOV_ROLES):
            return True
        await interaction.response.send_message(
            embed=error_embed("Access Denied", "This command requires a government role."),
            ephemeral=True,
        )
        return False
    return app_commands.check(predicate)


def finance_check():
    async def predicate(interaction: discord.Interaction) -> bool:
        if has_any_role(interaction.user, FINANCE_ROLES):
            return True
        await interaction.response.send_message(
            embed=error_embed("Access Denied", "Requires Minister of Finance / Accountant General / President."),
            ephemeral=True,
        )
        return False
    return app_commands.check(predicate)


class Government(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /treasury ─────────────────────────────────────────────────────────────

    @app_commands.command(name="treasury", description="View the National Treasury balance and stats.")
    async def treasury(self, interaction: discord.Interaction):
        await interaction.response.defer()
        t  = await self.db.get_treasury()
        ms = await self.db.total_money_supply()
        ministries = await self.db.get_all_ministries()

        embed = discord.Embed(title="🏛  Federal Republic of Nigeria — Treasury", color=COLOR_GOLD)
        embed.add_field(name="💰 Treasury Balance", value=fmt(t["balance"]), inline=True)
        embed.add_field(name="💵 Total Money Supply (Citizens)", value=fmt(ms), inline=True)
        embed.add_field(name="📊 Ministries Registered", value=str(len(ministries)), inline=True)

        if ministries:
            total_budget = sum(m["budget"] for m in ministries)
            total_spent  = sum(m["spent"]  for m in ministries)
            embed.add_field(name="🏢 Total Ministry Budgets", value=fmt(total_budget), inline=True)
            embed.add_field(name="💸 Total Ministry Spent",   value=fmt(total_spent),  inline=True)

        embed.set_footer(text=f"Last updated: {t['updated_at'][:16]}")
        await interaction.followup.send(embed=embed)

    # ── /grant ────────────────────────────────────────────────────────────────

    @app_commands.command(name="grant", description="Issue an emergency grant or funding to a citizen or business.")
    @app_commands.describe(recipient="Who receives the grant.", amount="Amount in Naira.", reason="Reason for the grant.")
    @finance_check()
    async def grant(self, interaction: discord.Interaction, recipient: discord.Member, amount: int, reason: str):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))
        treasury = await self.db.get_treasury()
        if treasury["balance"] < amount:
            return await interaction.followup.send(embed=error_embed("Treasury Insufficient", f"Treasury has {fmt(treasury['balance'])} but you need {fmt(amount)}."))

        await self.db.get_or_create_user(str(recipient.id), recipient.display_name)
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(recipient.id), amount)
        await self.db.log_transaction(None, str(recipient.id), amount, "grant", f"Grant: {reason}")

        embed = success_embed(
            "Grant Issued",
            f"**{fmt(amount)}** granted to **{recipient.display_name}**.\n"
            f"Reason: *{reason}*\nAuthorised by: {interaction.user.display_name}"
        )
        await interaction.followup.send(embed=embed)

    # ── /fine (issue) ─────────────────────────────────────────────────────────

    @app_commands.command(name="fine", description="Issue a fine to a citizen (Police/Judiciary/President only).")
    @app_commands.describe(member="Citizen to fine.", amount="Fine amount in Naira.", reason="Offence description.")
    async def fine(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str):
        await interaction.response.defer()
        if not has_any_role(interaction.user, POLICE_ROLES | JUDICIARY_ROLES):
            return await interaction.followup.send(
                embed=error_embed("Access Denied", "Only Police Officers, Judges, or the President can issue fines."))
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.issue_fine(str(member.id), amount, reason, interaction.user.display_name)

        embed = discord.Embed(
            title="⚖️  Fine Issued",
            description=(
                f"**{member.display_name}** has been fined **{fmt(amount)}**.\n"
                f"Offence: *{reason}*\n"
                f"Issued by: {interaction.user.display_name}\n\n"
                f"They can pay with `/payfine <id>`."
            ),
            color=0xCC4400,
        )
        await interaction.followup.send(embed=embed)

    # ── /salary-pay ───────────────────────────────────────────────────────────

    @app_commands.command(name="salary-pay", description="Pay salary to a government employee from the Treasury.")
    @app_commands.describe(employee="Employee to pay.", job="Their government job title.", override="Override amount (optional).")
    @finance_check()
    async def salary_pay(self, interaction: discord.Interaction, employee: discord.Member, job: str, override: int = None):
        await interaction.response.defer()
        job_data = JOBS.get(job)
        if not job_data:
            choices = ", ".join(JOBS.keys())
            return await interaction.followup.send(embed=error_embed("Unknown Job", f"Valid jobs: {choices}"))

        amount = override if override and override > 0 else job_data["monthly"]
        treasury = await self.db.get_treasury()
        if treasury["balance"] < amount:
            return await interaction.followup.send(embed=error_embed("Treasury Insufficient", f"Need {fmt(amount)}, Treasury has {fmt(treasury['balance'])}."))

        await self.db.get_or_create_user(str(employee.id), employee.display_name)
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(employee.id), amount)
        await self.db.log_transaction(None, str(employee.id), amount, "salary", f"Salary payment: {job}")

        embed = success_embed(
            "Salary Disbursed",
            f"**{fmt(amount)}** paid to **{employee.display_name}** as *{job}*.\n"
            f"Authorised by: {interaction.user.display_name}"
        )
        await interaction.followup.send(embed=embed)

    # ── /tax-collect ──────────────────────────────────────────────────────────

    @app_commands.command(name="tax-collect", description="Collect a tax amount from a citizen's wallet.")
    @app_commands.describe(member="Taxpayer.", amount="Tax amount in Naira.", reason="Tax description (e.g. VAT, Income Tax).")
    @finance_check()
    async def tax_collect(self, interaction: discord.Interaction, member: discord.Member, amount: int, reason: str = "Tax"):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        u = await self.db.get_or_create_user(str(member.id), member.display_name)
        if u["wallet"] < amount:
            return await interaction.followup.send(
                embed=error_embed("Insufficient Funds", f"{member.display_name} only has {fmt(u['wallet'])} in wallet."))

        await self.db.update_wallet(str(member.id), -amount)
        await self.db.update_treasury(amount)
        await self.db.log_transaction(str(member.id), None, amount, "tax", reason)

        embed = success_embed(
            "Tax Collected",
            f"**{fmt(amount)}** collected from **{member.display_name}** ({reason}).\n"
            f"Collected by: {interaction.user.display_name}"
        )
        await interaction.followup.send(embed=embed)

    # ── /request-allocation ───────────────────────────────────────────────────

    @app_commands.command(name="request-allocation", description="Submit a budget request on behalf of your Ministry.")
    @app_commands.describe(ministry="Ministry name.", amount="Amount requested.", purpose="What the funds will be used for.")
    @gov_check()
    async def request_allocation(self, interaction: discord.Interaction, ministry: str, amount: int, purpose: str):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        m = await self.db.get_ministry(ministry)
        if not m:
            await self.db.create_ministry(ministry, str(interaction.user.id))
            m = await self.db.get_ministry(ministry)

        alloc_id = await self.db.create_allocation(m["id"], str(interaction.user.id), amount, purpose)

        embed = info_embed(
            "Allocation Request Submitted",
            f"**Allocation #{alloc_id}** — {fmt(amount)}\n"
            f"Ministry: **{ministry}**\n"
            f"Purpose: *{purpose}*\n\n"
            f"Awaiting approval from the Minister of Finance."
        )
        await interaction.followup.send(embed=embed)

    # ── /approve-allocation ───────────────────────────────────────────────────

    @app_commands.command(name="approve-allocation", description="Approve a pending ministry budget allocation.")
    @app_commands.describe(allocation_id="Allocation request ID.")
    @finance_check()
    async def approve_allocation(self, interaction: discord.Interaction, allocation_id: int):
        await interaction.response.defer()
        pending = await self.db.get_pending_allocations()
        alloc = next((a for a in pending if a["id"] == allocation_id), None)

        if not alloc:
            return await interaction.followup.send(embed=error_embed("Not Found", f"No pending allocation #{allocation_id}."))

        treasury = await self.db.get_treasury()
        if treasury["balance"] < alloc["amount"]:
            return await interaction.followup.send(
                embed=error_embed("Treasury Insufficient", f"Need {fmt(alloc['amount'])}, Treasury has {fmt(treasury['balance'])}."))

        await self.db.resolve_allocation(allocation_id, "approved", interaction.user.display_name)
        await self.db.update_treasury(-alloc["amount"])
        await self.db.update_ministry_budget(alloc["ministry_id"], alloc["amount"])
        await self.db.log_transaction(None, None, alloc["amount"], "allocation",
                                      f"Allocation #{allocation_id} — {alloc['ministry_name']}")

        embed = success_embed(
            "Allocation Approved",
            f"**{fmt(alloc['amount'])}** allocated to **{alloc['ministry_name']}**.\n"
            f"Purpose: *{alloc['purpose']}*\nApproved by: {interaction.user.display_name}"
        )
        await interaction.followup.send(embed=embed)

    # ── /deny-allocation ──────────────────────────────────────────────────────

    @app_commands.command(name="deny-allocation", description="Deny a pending ministry budget allocation.")
    @app_commands.describe(allocation_id="Allocation request ID.", reason="Reason for denial.")
    @finance_check()
    async def deny_allocation(self, interaction: discord.Interaction, allocation_id: int, reason: str = "No reason given"):
        await interaction.response.defer()
        pending = await self.db.get_pending_allocations()
        alloc = next((a for a in pending if a["id"] == allocation_id), None)

        if not alloc:
            return await interaction.followup.send(embed=error_embed("Not Found", f"No pending allocation #{allocation_id}."))

        await self.db.resolve_allocation(allocation_id, "denied", interaction.user.display_name)

        embed = warn_embed(
            "Allocation Denied",
            f"Allocation #{allocation_id} for **{alloc['ministry_name']}** denied.\nReason: *{reason}*"
        )
        await interaction.followup.send(embed=embed)

    # ── /allocations ──────────────────────────────────────────────────────────

    @app_commands.command(name="allocations", description="View all pending budget allocation requests.")
    @gov_check()
    async def allocations(self, interaction: discord.Interaction):
        await interaction.response.defer()
        pending = await self.db.get_pending_allocations()

        if not pending:
            return await interaction.followup.send(embed=info_embed("No Pending Allocations", "All clear — no requests waiting for approval."))

        embed = discord.Embed(title="📋  Pending Allocation Requests", color=COLOR_INFO)
        for a in pending:
            embed.add_field(
                name=f"#{a['id']}  {a['ministry_name']}  —  {fmt(a['amount'])}",
                value=f"Purpose: {a['purpose']}\nRequested by: <@{a['requested_by']}> on {a['created_at'][:10]}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── /contract-award ───────────────────────────────────────────────────────

    @app_commands.command(name="contract-award", description="Award a government contract to a business or citizen.")
    @app_commands.describe(
        title="Contract title / description.",
        recipient="Who receives the contract payment.",
        amount="Contract value in Naira.",
        ministry="Awarding ministry (optional).",
    )
    @gov_check()
    async def contract_award(
        self,
        interaction: discord.Interaction,
        title: str,
        recipient: discord.Member,
        amount: int,
        ministry: str = "Federal Government",
    ):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        treasury = await self.db.get_treasury()
        if treasury["balance"] < amount:
            return await interaction.followup.send(
                embed=error_embed("Treasury Insufficient", f"Need {fmt(amount)}, Treasury has {fmt(treasury['balance'])}."))

        await self.db.get_or_create_user(str(recipient.id), recipient.display_name)
        await self.db.award_contract(title, str(recipient.id), amount, ministry, interaction.user.display_name)
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(recipient.id), amount)
        await self.db.log_transaction(None, str(recipient.id), amount, "contract", f"Contract: {title}")

        embed = success_embed(
            "Contract Awarded 📜",
            f"**{title}**\nAwarded to: **{recipient.display_name}**\n"
            f"Value: {fmt(amount)}\nMinistry: {ministry}\nBy: {interaction.user.display_name}"
        )
        await interaction.followup.send(embed=embed)

    # ── /contracts ────────────────────────────────────────────────────────────

    @app_commands.command(name="contracts", description="View recent government contracts.")
    async def contracts(self, interaction: discord.Interaction):
        await interaction.response.defer()
        contracts = await self.db.get_contracts(10)

        if not contracts:
            return await interaction.followup.send(embed=info_embed("No Contracts", "No contracts have been awarded yet."))

        embed = discord.Embed(title="📜  Government Contracts", color=COLOR_INFO)
        for c in contracts:
            embed.add_field(
                name=f"#{c['id']}  {c['title']}  —  {fmt(c['amount'])}",
                value=f"Awardee: <@{c['awarded_to']}> | Ministry: {c['ministry']} | Date: {c['created_at'][:10]}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── /ministries ───────────────────────────────────────────────────────────

    @app_commands.command(name="ministries", description="List all registered ministries and their budgets.")
    async def ministries(self, interaction: discord.Interaction):
        await interaction.response.defer()
        mins = await self.db.get_all_ministries()

        if not mins:
            return await interaction.followup.send(embed=info_embed("No Ministries", "No ministries registered yet. Use /ministry-create."))

        embed = discord.Embed(title="🏢  Federal Ministries", color=COLOR_INFO)
        for m in mins:
            utilisation = (m["spent"] / m["budget"] * 100) if m["budget"] > 0 else 0
            embed.add_field(
                name=f"🏛  {m['name']}",
                value=(
                    f"Budget: {fmt(m['budget'])}  |  Spent: {fmt(m['spent'])}\n"
                    f"Utilisation: {utilisation:.1f}%"
                ),
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── /ministry-create ──────────────────────────────────────────────────────

    @app_commands.command(name="ministry-create", description="Create a new federal ministry.")
    @app_commands.describe(name="Ministry name.", head="Ministry head (optional).")
    @gov_check()
    async def ministry_create(self, interaction: discord.Interaction, name: str, head: discord.Member = None):
        await interaction.response.defer()
        existing = await self.db.get_ministry(name)
        if existing:
            return await interaction.followup.send(embed=warn_embed("Already Exists", f"Ministry **{name}** already exists."))

        await self.db.create_ministry(name, str(head.id) if head else None)
        embed = success_embed("Ministry Created", f"**{name}** has been established.\nHead: {head.display_name if head else 'TBD'}")
        await interaction.followup.send(embed=embed)

    # ── /deposit-treasury ─────────────────────────────────────────────────────

    @app_commands.command(name="deposit-treasury", description="Deposit funds from your wallet into the National Treasury.")
    @app_commands.describe(amount="Amount to deposit.")
    @finance_check()
    async def deposit_treasury(self, interaction: discord.Interaction, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        if u["wallet"] < amount:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"You only have {fmt(u['wallet'])}."))

        await self.db.update_wallet(str(interaction.user.id), -amount)
        await self.db.update_treasury(amount)
        await self.db.log_transaction(str(interaction.user.id), None, amount, "treasury_deposit", "Treasury deposit")

        await interaction.followup.send(embed=success_embed("Treasury Deposit", f"{fmt(amount)} deposited into the National Treasury."))


async def setup(bot):
    await bot.add_cog(Government(bot))
