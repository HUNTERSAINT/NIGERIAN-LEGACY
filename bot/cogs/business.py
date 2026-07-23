"""
Business commands:
  /business-register, /business-info, /business-deposit,
  /business-withdraw, /business-list, /business-top, /business-tax
"""
import discord
from discord.ext import commands
from discord import app_commands

from bot.config import COLOR_INFO, TAX_RATE, FINANCE_ROLES
from bot.utils import fmt, success_embed, error_embed, info_embed, has_any_role

INDUSTRIES = [
    "Agriculture", "Banking", "Construction", "Education", "Energy",
    "Healthcare", "ICT", "Manufacturing", "Media", "Mining",
    "Oil & Gas", "Real Estate", "Retail", "Telecoms", "Transport", "General"
]


class Business(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /business-register ────────────────────────────────────────────────────

    @app_commands.command(name="business-register", description="Register a new business under your name.")
    @app_commands.describe(name="Business name.", industry="Industry sector.")
    async def business_register(self, interaction: discord.Interaction, name: str, industry: str = "General"):
        await interaction.response.defer()
        if len(name) < 3:
            return await interaction.followup.send(embed=error_embed("Name Too Short", "Business name must be at least 3 characters."))

        existing = await self.db.get_business(name)
        if existing:
            return await interaction.followup.send(embed=error_embed("Name Taken", f"A business named **{name}** already exists."))

        # Registration fee
        reg_fee = 50_000
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        if u["wallet"] < reg_fee:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"Registration costs {fmt(reg_fee)}."))

        await self.db.update_wallet(str(interaction.user.id), -reg_fee)
        await self.db.update_treasury(reg_fee)
        await self.db.create_business(str(interaction.user.id), name, industry)
        await self.db.log_transaction(str(interaction.user.id), None, reg_fee, "business_reg", f"Registered: {name}")

        embed = success_embed(
            "Business Registered 🏢",
            f"**{name}** ({industry}) has been incorporated.\n"
            f"Registration fee: {fmt(reg_fee)} paid to CAC.\n\n"
            f"Use `/business-deposit` to fund your business."
        )
        await interaction.followup.send(embed=embed)

    # ── /business-info ────────────────────────────────────────────────────────

    @app_commands.command(name="business-info", description="View details about a registered business.")
    @app_commands.describe(name="Business name.")
    async def business_info(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer()
        biz = await self.db.get_business(name)

        if not biz:
            return await interaction.followup.send(embed=error_embed("Not Found", f"No business named **{name}**."))

        embed = discord.Embed(title=f"🏢  {biz['name']}", color=COLOR_INFO)
        embed.add_field(name="🏭 Industry",    value=biz["industry"],              inline=True)
        embed.add_field(name="💰 Balance",     value=fmt(biz["balance"]),          inline=True)
        embed.add_field(name="📈 Total Revenue", value=fmt(biz["revenue"]),        inline=True)
        embed.add_field(name="🧾 Tax Paid",    value=fmt(biz["tax_paid"]),         inline=True)
        embed.add_field(name="👥 Employees",   value=str(biz["employees"]),        inline=True)
        embed.add_field(name="📅 Registered",  value=biz["registered_at"][:10],   inline=True)
        embed.add_field(name="👤 Owner",       value=f"<@{biz['owner_id']}>",      inline=False)
        await interaction.followup.send(embed=embed)

    # ── /business-deposit ─────────────────────────────────────────────────────

    @app_commands.command(name="business-deposit", description="Fund your business from your wallet.")
    @app_commands.describe(name="Business name.", amount="Amount in Naira.")
    async def business_deposit(self, interaction: discord.Interaction, name: str, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        biz = await self.db.get_business(name)
        if not biz:
            return await interaction.followup.send(embed=error_embed("Not Found", f"No business named **{name}**."))
        if biz["owner_id"] != str(interaction.user.id):
            return await interaction.followup.send(embed=error_embed("Not Your Business"))

        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        if u["wallet"] < amount:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds"))

        await self.db.update_wallet(str(interaction.user.id), -amount)
        await self.db.update_business_balance(biz["id"], amount)
        await self.db.log_transaction(str(interaction.user.id), None, amount, "biz_deposit", f"Funded: {name}")

        await interaction.followup.send(embed=success_embed("Business Funded", f"{fmt(amount)} deposited into **{name}**."))

    # ── /business-withdraw ────────────────────────────────────────────────────

    @app_commands.command(name="business-withdraw", description="Withdraw from your business to your wallet.")
    @app_commands.describe(name="Business name.", amount="Amount in Naira.")
    async def business_withdraw(self, interaction: discord.Interaction, name: str, amount: int):
        await interaction.response.defer()
        if amount <= 0:
            return await interaction.followup.send(embed=error_embed("Invalid Amount"))

        biz = await self.db.get_business(name)
        if not biz:
            return await interaction.followup.send(embed=error_embed("Not Found"))
        if biz["owner_id"] != str(interaction.user.id):
            return await interaction.followup.send(embed=error_embed("Not Your Business"))
        if biz["balance"] < amount:
            return await interaction.followup.send(embed=error_embed("Insufficient Business Funds", f"Business only has {fmt(biz['balance'])}."))

        # Tax on withdrawal
        tax = int(amount * TAX_RATE)
        net = amount - tax

        await self.db.update_business_balance(biz["id"], -amount)
        await self.db.update_wallet(str(interaction.user.id), net)
        await self.db.update_treasury(tax)
        await self.db.execute(
            "UPDATE businesses SET tax_paid=tax_paid+? WHERE id=?", (tax, biz["id"])
        )
        await self.db.log_transaction(None, str(interaction.user.id), net, "biz_withdrawal", f"Withdrew from {name}")

        await interaction.followup.send(embed=success_embed(
            "Withdrawal Complete",
            f"{fmt(net)} withdrawn from **{name}** (after {TAX_RATE*100:.1f}% VAT of {fmt(tax)})."
        ))

    # ── /business-list ────────────────────────────────────────────────────────

    @app_commands.command(name="business-list", description="List your registered businesses.")
    async def business_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        bizs = await self.db.get_user_businesses(str(interaction.user.id))

        if not bizs:
            return await interaction.followup.send(embed=info_embed("No Businesses", "You have not registered any businesses. Use `/business-register`."))

        embed = discord.Embed(title="🏢  Your Businesses", color=COLOR_INFO)
        for b in bizs:
            embed.add_field(
                name=f"{b['name']}  ({b['industry']})",
                value=f"Balance: {fmt(b['balance'])}  |  Tax paid: {fmt(b['tax_paid'])}",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── /business-top ─────────────────────────────────────────────────────────

    @app_commands.command(name="business-top", description="View the top 10 wealthiest businesses in Nigeria.")
    async def business_top(self, interaction: discord.Interaction):
        await interaction.response.defer()
        bizs = await self.db.top_businesses(10)

        if not bizs:
            return await interaction.followup.send(embed=info_embed("No Businesses", "No businesses registered yet."))

        medals = ["🥇", "🥈", "🥉"] + [f"{i}️⃣" for i in range(4, 11)]
        embed = discord.Embed(title="🏆  Top Businesses — Nigeria", color=0xFFD700)
        for i, b in enumerate(bizs):
            embed.add_field(
                name=f"{medals[i]}  {b['name']}  ({b['industry']})",
                value=f"Balance: {fmt(b['balance'])}  |  Owner: <@{b['owner_id']}>",
                inline=False,
            )
        await interaction.followup.send(embed=embed)

    # ── /business-tax ─────────────────────────────────────────────────────────

    @app_commands.command(name="business-tax", description="[Finance] Collect taxes directly from a business.")
    @app_commands.describe(name="Business name.", amount="Tax amount.", reason="Tax type.")
    async def business_tax(self, interaction: discord.Interaction, name: str, amount: int, reason: str = "Corporate Tax"):
        await interaction.response.defer()
        if not has_any_role(interaction.user, FINANCE_ROLES):
            return await interaction.followup.send(embed=error_embed("Access Denied", "Finance roles only."), ephemeral=True)

        biz = await self.db.get_business(name)
        if not biz:
            return await interaction.followup.send(embed=error_embed("Not Found"))
        if biz["balance"] < amount:
            return await interaction.followup.send(embed=error_embed("Insufficient Funds", f"Business only has {fmt(biz['balance'])}."))

        await self.db.update_business_balance(biz["id"], -amount)
        await self.db.update_treasury(amount)
        await self.db.execute(
            "UPDATE businesses SET tax_paid=tax_paid+? WHERE id=?", (amount, biz["id"])
        )
        await self.db.log_transaction(None, None, amount, "business_tax", f"{reason} — {name}")

        await interaction.followup.send(embed=success_embed("Tax Collected", f"{fmt(amount)} collected from **{name}** ({reason})."))


async def setup(bot):
    await bot.add_cog(Business(bot))
