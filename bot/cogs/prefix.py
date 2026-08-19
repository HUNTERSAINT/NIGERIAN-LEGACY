"""
Prefix (!) command mirror of all slash commands.
Every slash command has a matching !command equivalent.
Also provides !cmds for admins to see all commands.
"""
import discord
from discord.ext import commands
from datetime import datetime, timedelta

from bot.config import (
    DAILY_STIPEND, DAILY_COOLDOWN_H, WORK_COOLDOWN_H,
    JOBS, MAX_TRANSFER, BANK_TRANSFER_FEE,
    INTEREST_RATE, LOAN_MAX_RATIO, CBN_ROLES,
    FINANCE_ROLES, POLICE_ROLES, JUDICIARY_ROLES, GOV_ROLES,
    TAX_RATE, BET_MIN, BET_MAX, COLOR_INFO, COLOR_GOLD, COLOR_BET,
)
from bot.utils import (
    fmt, success_embed, error_embed, info_embed, warn_embed,
    has_any_role, is_admin,
)


def admin_only(ctx):
    return is_admin(ctx.author)


def finance_only(ctx):
    return is_admin(ctx.author) or has_any_role(ctx.author, FINANCE_ROLES)


def gov_only(ctx):
    return is_admin(ctx.author) or has_any_role(ctx.author, GOV_ROLES)


def police_or_judge(ctx):
    return is_admin(ctx.author) or has_any_role(ctx.author, POLICE_ROLES | JUDICIARY_ROLES)


def cbn_only(ctx):
    return is_admin(ctx.author) or has_any_role(ctx.author, CBN_ROLES)


# ── helpers ───────────────────────────────────────────────────────────────────

async def _deny(ctx, msg="You don't have permission to use this command."):
    await ctx.send(embed=error_embed("Access Denied", msg))


# ─────────────────────────────────────────────────────────────────────────────

class Prefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── !cmds ─────────────────────────────────────────────────────────────────

    @commands.command(name="cmds", aliases=["commands", "cmdlist"])
    @commands.check(admin_only)
    async def cmds(self, ctx):
        """[Admin] Show all bot commands with ! prefix."""
        embed = discord.Embed(
            title="🇳🇬  MetroCity Economy Bot — All Commands",
            description="Use `!` prefix OR `/` slash commands — both work.\nAll amounts are in **₦ Naira**.",
            color=COLOR_INFO,
        )

        embed.add_field(name="👤 Citizen", value=(
            "`!balance [@user]`\n"
            "`!pay @user <amount>`\n"
            "`!deposit <amount/all>`\n"
            "`!withdraw <amount/all>`\n"
            "`!work` · `!daily`\n"
            "`!history` · `!inventory`\n"
            "`!fines` · `!payfine <id>`\n"
            "`!leaderboard`"
        ), inline=True)

        embed.add_field(name="💼 Jobs", value=(
            "`!jobs`\n"
            "`!myjob`\n"
            "`!setjob @user <job>`\n"
            "*(Admin/President/Gov)*"
        ), inline=True)

        embed.add_field(name="🏛 Government", value=(
            "`!treasury`\n"
            "`!grant @user <amt> <reason>`\n"
            "`!fine @user <amt> <reason>`\n"
            "`!salarypay @user <job> [amt]`\n"
            "`!taxcollect @user <amt> [reason]`\n"
            "`!reqalloc <ministry> <amt> <purpose>`\n"
            "`!approvealloc <id>`\n"
            "`!denyalloc <id> [reason]`\n"
            "`!allocations`\n"
            "`!contract @user <amt> <title>`\n"
            "`!contracts` · `!ministries`\n"
            "`!newministry <name> [@head]`\n"
            "`!deposittreasury <amount>`"
        ), inline=False)

        embed.add_field(name="🏦 Banking / CBN", value=(
            "`!loan <amount>`\n"
            "`!loanstatus`\n"
            "`!loanrepay <id> <amount>`\n"
            "`!rates`\n"
            "`!cbnprint <amount> <reason>` *(CBN/Admin)*\n"
            "`!cbnseize @user <amount> <reason>` *(CBN/Admin)*"
        ), inline=True)

        embed.add_field(name="🏢 Business", value=(
            "`!bizreg <name> [industry]`\n"
            "`!bizinfo <name>`\n"
            "`!bizdeposit <name> <amount>`\n"
            "`!bizwithdraw <name> <amount>`\n"
            "`!mybiz`\n"
            "`!biztop`\n"
            "`!biztax <name> <amount>` *(Finance)*"
        ), inline=True)

        embed.add_field(name="⚽ Betting", value=(
            "`!bet <home/draw/away> <amount>`\n"
            "`!bethistory` · `!betstats`\n"
            "`!betstart #channel` *(Admin)*\n"
            "`!betstop` *(Admin)*\n"
            "`!betstatus`\n"
            "`!betcancel` *(Admin)*\n"
            "`!slipcreate <amount> home,draw,away` · `!slipplay <code> <amount>`\n"
            "`!slipinfo <code>` · `!betmax <amount>` *(Admin)*"
        ), inline=False)

        embed.add_field(name="🏪 Store & Role Income", value=(
            "`!store` · `!buy <id> [qty]`\n"
            "`!storeadd <name> <price> [stock] [description]` *(Admin)*\n"
            "`!storeremove <id>` *(Admin)*\n"
            "`!roleincome <hours> <income> <role name>` *(Admin)*\n"
            "`!roleincomelist` · `!roleincometoggle <id> <true/false>` *(Admin)*"
        ), inline=False)

        embed.add_field(name="📊 Admin Only", value=(
            "`!cmds` — this list\n"
            "`!economystats`\n"
            "`!addmoney @user <amount> [reason]`\n"
            "`!removemoney @user <amount> [reason]`\n"
            "`!resetuser @user`\n"
            "`!sync`"
        ), inline=False)

        embed.set_footer(text="🔐 Commands marked (Admin) require Server Administrator permission.")
        await ctx.send(embed=embed)

    @cmds.error
    async def cmds_error(self, ctx, error):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=error_embed("Access Denied", "Server Administrators only."), delete_after=5)

    # ── ECONOMY ───────────────────────────────────────────────────────────────

    @commands.command(name="balance", aliases=["bal", "money", "wallet"])
    async def balance(self, ctx, member: discord.Member = None):
        """View your balance or another member's."""
        target = member or ctx.author
        u = await self.db.get_or_create_user(str(target.id), target.display_name)
        embed = discord.Embed(title=f"💰  {target.display_name}'s Account", color=COLOR_GOLD)
        embed.add_field(name="👛 Wallet",        value=fmt(u["wallet"]),             inline=True)
        embed.add_field(name="🏦 Bank",          value=fmt(u["bank"]),               inline=True)
        embed.add_field(name="💼 Net Worth",     value=fmt(u["wallet"] + u["bank"]), inline=False)
        embed.add_field(name="🪪 Job",           value=u["job"],                     inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.command(name="pay", aliases=["send", "transfer"])
    async def pay(self, ctx, recipient: discord.Member, amount: int):
        """Transfer money from your wallet to another user."""
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount", "Amount must be positive."))
        if amount > MAX_TRANSFER:
            return await ctx.send(embed=error_embed("Limit Exceeded", f"Cap is {fmt(MAX_TRANSFER)}."))
        if recipient.id == ctx.author.id:
            return await ctx.send(embed=error_embed("Self-Transfer", "You can't pay yourself."))

        sender = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        fee = max(1, int(amount * BANK_TRANSFER_FEE))
        total = amount + fee

        if sender["wallet"] < total:
            return await ctx.send(embed=error_embed("Insufficient Funds",
                f"You need {fmt(total)} (incl. {fmt(fee)} fee) but have {fmt(sender['wallet'])}."))

        await self.db.get_or_create_user(str(recipient.id), recipient.display_name)
        await self.db.update_wallet(str(ctx.author.id), -total)
        await self.db.update_wallet(str(recipient.id), amount)
        await self.db.update_treasury(fee)
        await self.db.log_transaction(str(ctx.author.id), str(recipient.id), amount, "transfer")
        await ctx.send(embed=success_embed("Transfer Complete",
            f"{fmt(amount)} → **{recipient.display_name}**\nFee: {fmt(fee)} to Treasury."))

    @commands.command(name="deposit", aliases=["dep"])
    async def deposit(self, ctx, amount: str):
        """Deposit cash from wallet into bank."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        amt = u["wallet"] if amount.lower() == "all" else int(amount)
        if amt <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        if u["wallet"] < amt:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"You have {fmt(u['wallet'])}."))
        await self.db.update_wallet(str(ctx.author.id), -amt)
        await self.db.update_bank(str(ctx.author.id), amt)
        await self.db.log_transaction(str(ctx.author.id), None, amt, "deposit")
        await ctx.send(embed=success_embed("Deposited", f"{fmt(amt)} moved to your bank."))

    @commands.command(name="withdraw", aliases=["wd", "wtd"])
    async def withdraw(self, ctx, amount: str):
        """Withdraw cash from bank to wallet."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        amt = u["bank"] if amount.lower() == "all" else int(amount)
        if amt <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        if u["bank"] < amt:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"Bank has {fmt(u['bank'])}."))
        await self.db.update_bank(str(ctx.author.id), -amt)
        await self.db.update_wallet(str(ctx.author.id), amt)
        await self.db.log_transaction(None, str(ctx.author.id), amt, "withdrawal")
        await ctx.send(embed=success_embed("Withdrawn", f"{fmt(amt)} moved to your wallet."))

    @commands.command(name="work")
    async def work(self, ctx):
        """Work your job to earn income."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if u["last_work"]:
            last = datetime.fromisoformat(u["last_work"])
            end  = last + timedelta(hours=WORK_COOLDOWN_H)
            if datetime.utcnow() < end:
                rem = end - datetime.utcnow()
                h, m = divmod(int(rem.total_seconds()), 3600)
                return await ctx.send(embed=warn_embed("Cooldown", f"Work again in **{h}h {m//60}m**."))
        earnings = JOBS.get(u["job"], JOBS["Citizen"])["work"]
        await self.db.update_wallet(str(ctx.author.id), earnings)
        await self.db.set_last_work(str(ctx.author.id))
        await self.db.log_transaction(None, str(ctx.author.id), earnings, "work", u["job"])
        await ctx.send(embed=success_embed(f"Work Done — {u['job']}", f"Earned **{fmt(earnings)}**."))

    @commands.command(name="daily")
    async def daily(self, ctx):
        """Claim your daily government stipend."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if u["last_daily"]:
            last = datetime.fromisoformat(u["last_daily"])
            end  = last + timedelta(hours=DAILY_COOLDOWN_H)
            if datetime.utcnow() < end:
                rem = end - datetime.utcnow()
                h, m = divmod(int(rem.total_seconds()), 3600)
                return await ctx.send(embed=warn_embed("Already Claimed", f"Come back in **{h}h {m//60}m**."))
        await self.db.update_wallet(str(ctx.author.id), DAILY_STIPEND)
        await self.db.set_last_daily(str(ctx.author.id))
        await self.db.log_transaction(None, str(ctx.author.id), DAILY_STIPEND, "daily")
        await ctx.send(embed=success_embed("Daily Claimed", f"Received **{fmt(DAILY_STIPEND)}** stipend."))

    @commands.command(name="history", aliases=["txns", "transactions"])
    async def history(self, ctx):
        """View your last 10 transactions."""
        await self.db.ensure_user(str(ctx.author.id), ctx.author.display_name)
        txs = await self.db.get_user_transactions(str(ctx.author.id), 10)
        if not txs:
            return await ctx.send(embed=info_embed("No Transactions", "No history yet."))
        embed = discord.Embed(title="📋  Transaction History", color=COLOR_INFO)
        uid = str(ctx.author.id)
        for tx in txs:
            d = "→ OUT" if tx["from_id"] == uid else "← IN"
            embed.add_field(name=f"{d}  {fmt(tx['amount'])}  [{tx['type'].upper()}]",
                            value=tx["created_at"][:16], inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="inventory", aliases=["profile", "inv"])
    async def inventory(self, ctx):
        """View your full profile."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        fines = await self.db.get_unpaid_fines(str(ctx.author.id))
        loans = await self.db.get_active_loans(str(ctx.author.id))
        bizs  = await self.db.get_user_businesses(str(ctx.author.id))
        embed = discord.Embed(title=f"🗂  {ctx.author.display_name}'s Profile", color=COLOR_INFO)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name="💼 Job",        value=u["job"],                      inline=True)
        embed.add_field(name="👛 Wallet",     value=fmt(u["wallet"]),              inline=True)
        embed.add_field(name="🏦 Bank",       value=fmt(u["bank"]),                inline=True)
        embed.add_field(name="💰 Net Worth",  value=fmt(u["wallet"]+u["bank"]),    inline=True)
        embed.add_field(name="⚖️ Fines",      value=fmt(sum(f["amount"] for f in fines)) if fines else "None", inline=True)
        embed.add_field(name="🏛 Loans",      value=fmt(sum(l["outstanding"] for l in loans)) if loans else "None", inline=True)
        if bizs:
            embed.add_field(name="🏢 Businesses", value=", ".join(b["name"] for b in bizs), inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="fines")
    async def fines(self, ctx):
        """View your unpaid fines."""
        await self.db.ensure_user(str(ctx.author.id), ctx.author.display_name)
        fines = await self.db.get_unpaid_fines(str(ctx.author.id))
        if not fines:
            return await ctx.send(embed=success_embed("No Fines", "You're clean! 🎉"))
        embed = discord.Embed(title="⚖️  Unpaid Fines", color=0xCC4400)
        for f in fines:
            embed.add_field(name=f"#{f['id']} — {fmt(f['amount'])}",
                value=f"{f['reason']} | By: {f['issued_by']} | {f['created_at'][:10]}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="payfine")
    async def payfine(self, ctx, fine_id: int):
        """Pay an outstanding fine by ID."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        fines = await self.db.get_unpaid_fines(str(ctx.author.id))
        fine = next((f for f in fines if f["id"] == fine_id), None)
        if not fine:
            return await ctx.send(embed=error_embed("Not Found", f"No unpaid fine #{fine_id}."))
        if u["wallet"] < fine["amount"]:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"Need {fmt(fine['amount'])}."))
        await self.db.update_wallet(str(ctx.author.id), -fine["amount"])
        await self.db.update_treasury(fine["amount"])
        await self.db.pay_fine(fine_id)
        await ctx.send(embed=success_embed("Fine Paid", f"Paid {fmt(fine['amount'])} for: *{fine['reason']}*"))

    @commands.command(name="leaderboard", aliases=["lb", "top", "richest"])
    async def leaderboard(self, ctx):
        """Top 10 richest citizens."""
        users = await self.db.richest_users(10)
        total = await self.db.total_money_supply()
        trs   = await self.db.get_treasury()
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        embed = discord.Embed(title="🏆  Richest Citizens — Nigeria", color=COLOR_GOLD)
        for i, u in enumerate(users):
            embed.add_field(name=f"{medals[i]}  {u['username']}",
                value=f"{fmt(u['wallet']+u['bank'])} | {u['job']}", inline=False)
        embed.add_field(name="💰 Money Supply", value=fmt(total), inline=True)
        embed.add_field(name="🏛 Treasury",     value=fmt(trs["balance"]), inline=True)
        await ctx.send(embed=embed)

    # ── JOBS ──────────────────────────────────────────────────────────────────

    @commands.command(name="jobs")
    async def jobs(self, ctx):
        """List all jobs and salaries."""
        embed = discord.Embed(title="💼  Jobs — Federal Republic of Nigeria", color=COLOR_GOLD)
        for name, data in JOBS.items():
            embed.add_field(name=name,
                value=f"Monthly: {fmt(data['monthly'])}\n/work: {fmt(data['work'])}", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="myjob", aliases=["job"])
    async def myjob(self, ctx):
        """View your current job."""
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        data = JOBS.get(u["job"], JOBS["Citizen"])
        embed = discord.Embed(title=f"💼  {ctx.author.display_name}'s Job", color=COLOR_INFO)
        embed.add_field(name="Job",            value=u["job"],              inline=True)
        embed.add_field(name="Monthly Salary", value=fmt(data["monthly"]), inline=True)
        embed.add_field(name="Per !work",      value=fmt(data["work"]),    inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="setjob")
    async def setjob(self, ctx, member: discord.Member, *, job: str):
        """[Admin/President] Assign a job to a member."""
        if not (is_admin(ctx.author) or
                any(r.name in {"President","Vice President","Governor"} for r in ctx.author.roles)):
            return await _deny(ctx)
        if job not in JOBS:
            return await ctx.send(embed=error_embed("Unknown Job", f"Valid: {', '.join(JOBS.keys())}"))
        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.set_job(str(member.id), job)
        await ctx.send(embed=success_embed("Job Assigned",
            f"**{member.display_name}** → **{job}** | Salary: {fmt(JOBS[job]['monthly'])}/mo"))

    # ── GOVERNMENT ────────────────────────────────────────────────────────────

    @commands.command(name="treasury", aliases=["treas"])
    async def treasury(self, ctx):
        """View the National Treasury."""
        t  = await self.db.get_treasury()
        ms = await self.db.total_money_supply()
        mins = await self.db.get_all_ministries()
        embed = discord.Embed(title="🏛  National Treasury", color=COLOR_GOLD)
        embed.add_field(name="💰 Balance",   value=fmt(t["balance"]),       inline=True)
        embed.add_field(name="💵 Citizens",  value=fmt(ms),                 inline=True)
        embed.add_field(name="🏢 Ministries",value=str(len(mins)),          inline=True)
        embed.set_footer(text=f"Updated: {t['updated_at'][:16]}")
        await ctx.send(embed=embed)

    @commands.command(name="grant")
    async def grant(self, ctx, member: discord.Member, amount: int, *, reason: str):
        """[Finance/Admin] Grant money from Treasury to a citizen."""
        if not finance_only(ctx):
            return await _deny(ctx, "Requires Minister of Finance or Admin.")
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        t = await self.db.get_treasury()
        if t["balance"] < amount:
            return await ctx.send(embed=error_embed("Treasury Low", f"Only {fmt(t['balance'])} available."))
        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(member.id), amount)
        await self.db.log_transaction(None, str(member.id), amount, "grant", reason)
        await ctx.send(embed=success_embed("Grant Issued",
            f"{fmt(amount)} → **{member.display_name}**\nReason: *{reason}*"))

    @commands.command(name="fine")
    async def fine(self, ctx, member: discord.Member, amount: int, *, reason: str):
        """[Police/Judge/Admin] Issue a fine."""
        if not police_or_judge(ctx):
            return await _deny(ctx, "Police, Judges, or Admins only.")
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.issue_fine(str(member.id), amount, reason, ctx.author.display_name)
        embed = discord.Embed(title="⚖️  Fine Issued", color=0xCC4400,
            description=f"**{member.display_name}** fined **{fmt(amount)}**\nOffence: *{reason}*\nBy: {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @commands.command(name="salarypay", aliases=["salary"])
    async def salarypay(self, ctx, employee: discord.Member, job: str, override: int = None):
        """[Finance/Admin] Pay salary from Treasury."""
        if not finance_only(ctx):
            return await _deny(ctx, "Finance role or Admin required.")
        jd = JOBS.get(job)
        if not jd:
            return await ctx.send(embed=error_embed("Unknown Job", f"Valid: {', '.join(JOBS.keys())}"))
        amount = override if override and override > 0 else jd["monthly"]
        t = await self.db.get_treasury()
        if t["balance"] < amount:
            return await ctx.send(embed=error_embed("Treasury Low"))
        await self.db.get_or_create_user(str(employee.id), employee.display_name)
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(employee.id), amount)
        await self.db.log_transaction(None, str(employee.id), amount, "salary", job)
        await ctx.send(embed=success_embed("Salary Paid",
            f"{fmt(amount)} → **{employee.display_name}** as *{job}*"))

    @commands.command(name="taxcollect", aliases=["tax"])
    async def taxcollect(self, ctx, member: discord.Member, amount: int, *, reason: str = "Tax"):
        """[Finance/Admin] Collect tax from a citizen."""
        if not finance_only(ctx):
            return await _deny(ctx, "Finance role or Admin required.")
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        u = await self.db.get_or_create_user(str(member.id), member.display_name)
        if u["wallet"] < amount:
            return await ctx.send(embed=error_embed("Insufficient Funds",
                f"{member.display_name} only has {fmt(u['wallet'])}."))
        await self.db.update_wallet(str(member.id), -amount)
        await self.db.update_treasury(amount)
        await self.db.log_transaction(str(member.id), None, amount, "tax", reason)
        await ctx.send(embed=success_embed("Tax Collected",
            f"{fmt(amount)} from **{member.display_name}** ({reason})"))

    @commands.command(name="reqalloc", aliases=["requestalloc"])
    async def reqalloc(self, ctx, ministry: str, amount: int, *, purpose: str):
        """[Gov/Admin] Submit a ministry budget request."""
        if not gov_only(ctx):
            return await _deny(ctx, "Government role required.")
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        m = await self.db.get_ministry(ministry)
        if not m:
            await self.db.create_ministry(ministry, str(ctx.author.id))
            m = await self.db.get_ministry(ministry)
        alloc_id = await self.db.create_allocation(m["id"], str(ctx.author.id), amount, purpose)
        await ctx.send(embed=info_embed("Allocation Submitted",
            f"**#{alloc_id}** — {fmt(amount)} for *{ministry}*\nPurpose: {purpose}"))

    @commands.command(name="approvealloc", aliases=["appralloc"])
    async def approvealloc(self, ctx, alloc_id: int):
        """[Finance/Admin] Approve a budget allocation."""
        if not finance_only(ctx):
            return await _deny(ctx, "Finance role or Admin required.")
        pending = await self.db.get_pending_allocations()
        alloc = next((a for a in pending if a["id"] == alloc_id), None)
        if not alloc:
            return await ctx.send(embed=error_embed("Not Found", f"No pending allocation #{alloc_id}."))
        t = await self.db.get_treasury()
        if t["balance"] < alloc["amount"]:
            return await ctx.send(embed=error_embed("Treasury Low"))
        await self.db.resolve_allocation(alloc_id, "approved", ctx.author.display_name)
        await self.db.update_treasury(-alloc["amount"])
        await self.db.update_ministry_budget(alloc["ministry_id"], alloc["amount"])
        await ctx.send(embed=success_embed("Allocation Approved",
            f"{fmt(alloc['amount'])} allocated to **{alloc['ministry_name']}**\nPurpose: {alloc['purpose']}"))

    @commands.command(name="denyalloc", aliases=["denyallocation"])
    async def denyalloc(self, ctx, alloc_id: int, *, reason: str = "No reason given"):
        """[Finance/Admin] Deny a budget allocation."""
        if not finance_only(ctx):
            return await _deny(ctx, "Finance role or Admin required.")
        pending = await self.db.get_pending_allocations()
        alloc = next((a for a in pending if a["id"] == alloc_id), None)
        if not alloc:
            return await ctx.send(embed=error_embed("Not Found", f"No pending allocation #{alloc_id}."))
        await self.db.resolve_allocation(alloc_id, "denied", ctx.author.display_name)
        await ctx.send(embed=warn_embed("Allocation Denied",
            f"#{alloc_id} for *{alloc['ministry_name']}* denied.\nReason: {reason}"))

    @commands.command(name="allocations", aliases=["allocs"])
    async def allocations(self, ctx):
        """[Gov/Admin] List pending allocation requests."""
        if not gov_only(ctx):
            return await _deny(ctx)
        pending = await self.db.get_pending_allocations()
        if not pending:
            return await ctx.send(embed=info_embed("No Pending Allocations", "All clear."))
        embed = discord.Embed(title="📋  Pending Allocations", color=COLOR_INFO)
        for a in pending:
            embed.add_field(name=f"#{a['id']}  {a['ministry_name']}  — {fmt(a['amount'])}",
                value=f"{a['purpose']} | <@{a['requested_by']}> | {a['created_at'][:10]}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="contract", aliases=["awardcontract"])
    async def contract(self, ctx, recipient: discord.Member, amount: int, *, title: str):
        """[Gov/Admin] Award a government contract."""
        if not gov_only(ctx):
            return await _deny(ctx)
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        t = await self.db.get_treasury()
        if t["balance"] < amount:
            return await ctx.send(embed=error_embed("Treasury Low"))
        await self.db.get_or_create_user(str(recipient.id), recipient.display_name)
        await self.db.award_contract(title, str(recipient.id), amount, "Federal Government", ctx.author.display_name)
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(recipient.id), amount)
        await ctx.send(embed=success_embed("Contract Awarded 📜",
            f"**{title}**\nTo: **{recipient.display_name}** — {fmt(amount)}"))

    @commands.command(name="contracts")
    async def contracts(self, ctx):
        """View recent government contracts."""
        cs = await self.db.get_contracts(10)
        if not cs:
            return await ctx.send(embed=info_embed("No Contracts", "None awarded yet."))
        embed = discord.Embed(title="📜  Government Contracts", color=COLOR_INFO)
        for c in cs:
            embed.add_field(name=f"#{c['id']}  {c['title']} — {fmt(c['amount'])}",
                value=f"<@{c['awarded_to']}> | {c['ministry']} | {c['created_at'][:10]}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="ministries", aliases=["mins"])
    async def ministries(self, ctx):
        """List all ministries."""
        mins = await self.db.get_all_ministries()
        if not mins:
            return await ctx.send(embed=info_embed("No Ministries", "Use !newministry to create one."))
        embed = discord.Embed(title="🏢  Federal Ministries", color=COLOR_INFO)
        for m in mins:
            u = (m["spent"]/m["budget"]*100) if m["budget"] > 0 else 0
            embed.add_field(name=f"🏛  {m['name']}",
                value=f"Budget: {fmt(m['budget'])} | Spent: {fmt(m['spent'])} | {u:.1f}%", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="newministry", aliases=["createministry"])
    async def newministry(self, ctx, name: str, head: discord.Member = None):
        """[Gov/Admin] Create a new ministry."""
        if not gov_only(ctx):
            return await _deny(ctx)
        existing = await self.db.get_ministry(name)
        if existing:
            return await ctx.send(embed=warn_embed("Exists", f"**{name}** already exists."))
        await self.db.create_ministry(name, str(head.id) if head else None)
        await ctx.send(embed=success_embed("Ministry Created",
            f"**{name}** established. Head: {head.display_name if head else 'TBD'}"))

    @commands.command(name="deposittreasury", aliases=["deptreasury"])
    async def deposittreasury(self, ctx, amount: int):
        """[Finance/Admin] Deposit personal funds into Treasury."""
        if not finance_only(ctx):
            return await _deny(ctx, "Finance role or Admin required.")
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if u["wallet"] < amount:
            return await ctx.send(embed=error_embed("Insufficient Funds"))
        await self.db.update_wallet(str(ctx.author.id), -amount)
        await self.db.update_treasury(amount)
        await ctx.send(embed=success_embed("Treasury Deposit", f"{fmt(amount)} deposited into the National Treasury."))

    # ── BANKING ───────────────────────────────────────────────────────────────

    @commands.command(name="loan")
    async def loan(self, ctx, amount: int):
        """Request a CBN loan."""
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        max_loan = int((u["wallet"]+u["bank"]) * LOAN_MAX_RATIO)
        if amount > max_loan:
            return await ctx.send(embed=error_embed("Loan Limit", f"Max is {fmt(max_loan)}."))
        t = await self.db.get_treasury()
        if t["balance"] < amount:
            return await ctx.send(embed=error_embed("CBN Low Reserves"))
        active = await self.db.get_active_loans(str(ctx.author.id))
        if active:
            return await ctx.send(embed=warn_embed("Existing Loan", "Repay your current loan first."))
        await self.db.update_treasury(-amount)
        await self.db.update_wallet(str(ctx.author.id), amount)
        await self.db.create_loan(str(ctx.author.id), amount, INTEREST_RATE)
        await ctx.send(embed=success_embed("Loan Approved",
            f"{fmt(amount)} added to wallet.\nRate: {INTEREST_RATE*100:.1f}%/day | Due in 30 days."))

    @commands.command(name="loanstatus", aliases=["loans"])
    async def loanstatus(self, ctx):
        """Check your active loans."""
        loans = await self.db.get_active_loans(str(ctx.author.id))
        if not loans:
            return await ctx.send(embed=info_embed("No Loans", "You have no active loans. 🎉"))
        embed = discord.Embed(title="🏛  Active Loans", color=COLOR_INFO)
        for l in loans:
            embed.add_field(name=f"Loan #{l['id']}",
                value=f"Outstanding: {fmt(l['outstanding'])}\nDue: {l['due_at'][:10] if l['due_at'] else 'N/A'}",
                inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="loanrepay", aliases=["repay"])
    async def loanrepay(self, ctx, loan_id: int, amount: int):
        """Repay a loan."""
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        loans = await self.db.get_active_loans(str(ctx.author.id))
        loan = next((l for l in loans if l["id"] == loan_id), None)
        if not loan:
            return await ctx.send(embed=error_embed("Not Found", f"No active loan #{loan_id}."))
        pay = min(amount, loan["outstanding"])
        if u["wallet"] < pay:
            return await ctx.send(embed=error_embed("Insufficient Funds"))
        remaining = await self.db.repay_loan(loan_id, pay)
        await self.db.update_wallet(str(ctx.author.id), -pay)
        await self.db.update_treasury(pay)
        msg = f"Loan #{loan_id} fully repaid! 🎉" if remaining == 0 else f"Paid {fmt(pay)}. Left: {fmt(remaining)}."
        await ctx.send(embed=success_embed("Loan Repayment", msg))

    @commands.command(name="rates", aliases=["interestrates"])
    async def rates(self, ctx):
        """View CBN rates."""
        embed = discord.Embed(title="📊  CBN Interest Rates", color=COLOR_GOLD)
        embed.add_field(name="Loan Rate",  value=f"{INTEREST_RATE*100:.1f}%/24h", inline=True)
        embed.add_field(name="Max Loan",   value=f"{LOAN_MAX_RATIO}× net worth", inline=True)
        embed.add_field(name="Term",       value="30 days", inline=True)
        embed.add_field(name="xfer Fee",   value="0.5% → Treasury", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="cbnprint")
    async def cbnprint(self, ctx, amount: int, *, reason: str):
        """[CBN/Admin] Mint money into the Treasury."""
        if not cbn_only(ctx):
            return await _deny(ctx, "CBN Governor or Admin only.")
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        await self.db.update_treasury(amount)
        await self.db.log_transaction(None, None, amount, "money_printing", reason)
        await ctx.send(embed=discord.Embed(title="🖨️  Money Printed",
            description=f"{fmt(amount)} minted into Treasury.\nBy: {ctx.author.display_name}\n⚠️ Excessive printing causes inflation.",
            color=COLOR_GOLD))

    @commands.command(name="cbnseize", aliases=["seize"])
    async def cbnseize(self, ctx, member: discord.Member, amount: int, *, reason: str):
        """[CBN/Admin] Seize funds from a citizen."""
        if not cbn_only(ctx):
            return await _deny(ctx, "CBN Governor or Admin only.")
        u = await self.db.get_or_create_user(str(member.id), member.display_name)
        seized = min(amount, u["wallet"]+u["bank"])
        fw = min(seized, u["wallet"]); fb = seized - fw
        if fw > 0: await self.db.update_wallet(str(member.id), -fw)
        if fb > 0: await self.db.update_bank(str(member.id), -fb)
        await self.db.update_treasury(seized)
        await self.db.log_transaction(str(member.id), None, seized, "seizure", reason)
        await ctx.send(embed=discord.Embed(title="🔒  Account Seized",
            description=f"{fmt(seized)} seized from **{member.display_name}**\nReason: *{reason}*",
            color=0x800000))

    # ── BUSINESS ──────────────────────────────────────────────────────────────

    @commands.command(name="bizreg", aliases=["registerbiz", "newbiz"])
    async def bizreg(self, ctx, name: str, industry: str = "General"):
        """Register a new business (₦50,000 fee)."""
        reg_fee = 50_000
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if u["wallet"] < reg_fee:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"Registration costs {fmt(reg_fee)}."))
        if await self.db.get_business(name):
            return await ctx.send(embed=error_embed("Name Taken", f"**{name}** already exists."))
        await self.db.update_wallet(str(ctx.author.id), -reg_fee)
        await self.db.update_treasury(reg_fee)
        await self.db.create_business(str(ctx.author.id), name, industry)
        await ctx.send(embed=success_embed("Business Registered 🏢",
            f"**{name}** ({industry}) incorporated.\nFee: {fmt(reg_fee)} paid to CAC."))

    @commands.command(name="bizinfo")
    async def bizinfo(self, ctx, *, name: str):
        """View a business's details."""
        biz = await self.db.get_business(name)
        if not biz:
            return await ctx.send(embed=error_embed("Not Found", f"No business **{name}**."))
        embed = discord.Embed(title=f"🏢  {biz['name']}", color=COLOR_INFO)
        embed.add_field(name="Industry",  value=biz["industry"],           inline=True)
        embed.add_field(name="Balance",   value=fmt(biz["balance"]),       inline=True)
        embed.add_field(name="Tax Paid",  value=fmt(biz["tax_paid"]),      inline=True)
        embed.add_field(name="Owner",     value=f"<@{biz['owner_id']}>",   inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="bizdeposit")
    async def bizdeposit(self, ctx, name: str, amount: int):
        """Fund your business from your wallet."""
        biz = await self.db.get_business(name)
        if not biz or biz["owner_id"] != str(ctx.author.id):
            return await ctx.send(embed=error_embed("Not Found / Not Owner"))
        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if u["wallet"] < amount:
            return await ctx.send(embed=error_embed("Insufficient Funds"))
        await self.db.update_wallet(str(ctx.author.id), -amount)
        await self.db.update_business_balance(biz["id"], amount)
        await ctx.send(embed=success_embed("Business Funded", f"{fmt(amount)} deposited into **{name}**."))

    @commands.command(name="bizwithdraw")
    async def bizwithdraw(self, ctx, name: str, amount: int):
        """Withdraw from your business (7.5% VAT)."""
        biz = await self.db.get_business(name)
        if not biz or biz["owner_id"] != str(ctx.author.id):
            return await ctx.send(embed=error_embed("Not Found / Not Owner"))
        if biz["balance"] < amount:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"Business has {fmt(biz['balance'])}."))
        tax = int(amount * TAX_RATE); net = amount - tax
        await self.db.update_business_balance(biz["id"], -amount)
        await self.db.update_wallet(str(ctx.author.id), net)
        await self.db.update_treasury(tax)
        await self.db.execute("UPDATE businesses SET tax_paid=tax_paid+? WHERE id=?", (tax, biz["id"]))
        await ctx.send(embed=success_embed("Withdrawn",
            f"{fmt(net)} to wallet (VAT {fmt(tax)} paid to Treasury)."))

    @commands.command(name="mybiz", aliases=["mybusiness", "mybusinesses"])
    async def mybiz(self, ctx):
        """List your businesses."""
        bizs = await self.db.get_user_businesses(str(ctx.author.id))
        if not bizs:
            return await ctx.send(embed=info_embed("No Businesses", "Use !bizreg to register one."))
        embed = discord.Embed(title="🏢  Your Businesses", color=COLOR_INFO)
        for b in bizs:
            embed.add_field(name=f"{b['name']} ({b['industry']})",
                value=f"Balance: {fmt(b['balance'])} | Tax paid: {fmt(b['tax_paid'])}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="biztop", aliases=["topbiz"])
    async def biztop(self, ctx):
        """Top 10 wealthiest businesses."""
        bizs = await self.db.top_businesses(10)
        if not bizs:
            return await ctx.send(embed=info_embed("No Businesses", "None registered yet."))
        embed = discord.Embed(title="🏆  Top Businesses", color=COLOR_GOLD)
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, b in enumerate(bizs):
            embed.add_field(name=f"{medals[i]}  {b['name']} ({b['industry']})",
                value=f"Balance: {fmt(b['balance'])} | Owner: <@{b['owner_id']}>", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="biztax")
    async def biztax(self, ctx, name: str, amount: int, *, reason: str = "Corporate Tax"):
        """[Finance/Admin] Collect corporate tax from a business."""
        if not finance_only(ctx):
            return await _deny(ctx, "Finance role or Admin required.")
        biz = await self.db.get_business(name)
        if not biz:
            return await ctx.send(embed=error_embed("Not Found"))
        if biz["balance"] < amount:
            return await ctx.send(embed=error_embed("Insufficient Funds",
                f"Business only has {fmt(biz['balance'])}."))
        await self.db.update_business_balance(biz["id"], -amount)
        await self.db.update_treasury(amount)
        await self.db.execute("UPDATE businesses SET tax_paid=tax_paid+? WHERE id=?", (amount, biz["id"]))
        await ctx.send(embed=success_embed("Tax Collected",
            f"{fmt(amount)} from **{name}** ({reason})"))

    # ── BETTING ───────────────────────────────────────────────────────────────

    @commands.command(name="bet")
    async def bet(self, ctx, choice: str, amount: int):
        """Place a bet on the current match. !bet <home/draw/away> <amount>"""
        bet_cog = self.bot.get_cog("Betting")
        if not bet_cog:
            return await ctx.send(embed=error_embed("Betting Unavailable"))

        choice = choice.lower()
        if choice not in {"home", "draw", "away"}:
            return await ctx.send(embed=error_embed("Invalid Choice", "Use `home`, `draw`, or `away`."))
        if not bet_cog._running or bet_cog._current_match_id is None:
            return await ctx.send(embed=error_embed("No Active Match", "Wait for the next match announcement."))
        if amount < BET_MIN:
            return await ctx.send(embed=error_embed("Bet Too Small", f"Min: {fmt(BET_MIN)}."))
        max_bet = await self.db.get_max_bet()
        if amount > max_bet:
            return await ctx.send(embed=error_embed("Bet Too Large", f"Max: {fmt(max_bet)}."))

        u = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if u["wallet"] < amount:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"You have {fmt(u['wallet'])}."))

        existing = await self.db.get_user_match_bet(str(ctx.author.id), bet_cog._current_match_id)
        if existing:
            return await ctx.send(embed=warn_embed("Already Bet", "One bet per match only."))

        odds  = {"home": bet_cog._current_home_odds,
                 "draw": bet_cog._current_draw_odds,
                 "away": bet_cog._current_away_odds}[choice]
        label = {"home": bet_cog._current_home["name"],
                 "draw": "Draw",
                 "away": bet_cog._current_away["name"]}[choice]

        await self.db.update_wallet(str(ctx.author.id), -amount)
        await self.db.place_bet(bet_cog._current_match_id, str(ctx.author.id), choice, amount)
        await self.db.log_transaction(str(ctx.author.id), None, amount, "bet_placed",
                                      f"Bet: Match #{bet_cog._current_match_id} — {choice}")

        potential = int(amount * odds * 0.95)
        embed = discord.Embed(title="🎲  Bet Placed!", color=COLOR_BET,
            description=(
                f"Match #{bet_cog._current_match_id}: "
                f"{bet_cog._current_home['name']} vs {bet_cog._current_away['name']}\n\n"
                f"Your pick: **{label.upper()}** at **{odds}x**\n"
                f"Stake: {fmt(amount)} | Potential: **{fmt(potential)}**"
            ))
        await ctx.send(embed=embed)

    @commands.command(name="betstart")
    async def betstart(self, ctx, channel: discord.TextChannel = None):
        """[Admin] Start football betting in a channel."""
        if not is_admin(ctx.author):
            return await _deny(ctx)
        bet_cog = self.bot.get_cog("Betting")
        if not bet_cog:
            return await ctx.send(embed=error_embed("Betting cog not loaded."))
        channel = channel or ctx.channel
        # Delegate to slash cog internals
        if bet_cog._running:
            return await ctx.send(embed=warn_embed("Already Running",
                f"Betting active in {bet_cog._channel.mention}. Use !betstop first."))
        import asyncio
        bet_cog._channel = channel
        bet_cog._running = True
        await self.db.set_bet_setting(str(channel.id), True)
        bet_cog._task = asyncio.create_task(bet_cog._cycle())
        await ctx.send(embed=success_embed("Betting Started ⚽",
            f"Matches every 5 min in {channel.mention}.\nMin: {fmt(BET_MIN)} | Max: {fmt(BET_MAX)}"))

    @commands.command(name="betstop")
    async def betstop(self, ctx):
        """[Admin] Stop football betting."""
        if not is_admin(ctx.author):
            return await _deny(ctx)
        import asyncio
        bet_cog = self.bot.get_cog("Betting")
        if not bet_cog or not bet_cog._running:
            return await ctx.send(embed=warn_embed("Not Running"))
        bet_cog._running = False
        await self.db.set_bet_setting(None, False)
        if bet_cog._task and not bet_cog._task.done():
            bet_cog._task.cancel()
            try: await bet_cog._task
            except asyncio.CancelledError: pass
        if bet_cog._current_match_id:
            await self.db.cancel_match(bet_cog._current_match_id)
            bet_cog._current_match_id = None
        bet_cog._channel = None
        await ctx.send(embed=success_embed("Betting Stopped", "All open bets refunded."))

    @commands.command(name="betstatus")
    async def betstatus(self, ctx):
        """Check betting status."""
        bet_cog = self.bot.get_cog("Betting")
        embed = discord.Embed(title="⚽  Betting Status", color=COLOR_BET)
        if bet_cog and bet_cog._running and bet_cog._channel:
            embed.add_field(name="Status",  value="🟢 **ACTIVE**",             inline=True)
            embed.add_field(name="Channel", value=bet_cog._channel.mention,     inline=True)
            mid = bet_cog._current_match_id
            embed.add_field(name="Match",
                value=f"#{mid} OPEN" if mid else "Waiting…", inline=False)
        else:
            embed.add_field(name="Status", value="🔴 **INACTIVE**", inline=True)
        await ctx.send(embed=embed)

    @commands.command(name="betcancel")
    async def betcancel(self, ctx):
        """[Admin] Cancel the current match and refund bets."""
        if not is_admin(ctx.author):
            return await _deny(ctx)
        bet_cog = self.bot.get_cog("Betting")
        if not bet_cog or bet_cog._current_match_id is None:
            return await ctx.send(embed=warn_embed("No Open Match"))
        mid = bet_cog._current_match_id
        bets = await self.db.get_match_bets(mid)
        refunded = 0
        for b in bets:
            if not b["settled"]:
                await self.db.update_wallet(b["user_id"], b["amount"])
                refunded += 1
        await self.db.cancel_match(mid)
        bet_cog._current_match_id = None
        await ctx.send(embed=success_embed(f"Match #{mid} Cancelled",
            f"{refunded} bet(s) refunded."))

    @commands.command(name="bethistory", aliases=["mybets"])
    async def bethistory(self, ctx):
        """View your last 10 bet results."""
        await self.db.ensure_user(str(ctx.author.id), ctx.author.display_name)
        bets = await self.db.get_user_bets(str(ctx.author.id), 10)
        if not bets:
            return await ctx.send(embed=discord.Embed(title="No Bet History",
                description="No bets placed yet.", color=COLOR_BET))
        embed = discord.Embed(title="🎲  Bet History", color=COLOR_BET)
        for b in bets:
            if not b["settled"]: s = "⏳ Pending"
            elif b["payout"] and b["payout"] > 0:
                s = f"✅ Won {fmt(b['payout'])} (+{fmt(b['payout']-b['amount'])})"
            else: s = f"❌ Lost {fmt(b['amount'])}"
            embed.add_field(name=f"Match #{b['match_id']} — {b['choice'].upper()}",
                value=f"Stake: {fmt(b['amount'])} | {s}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="betstats")
    async def betstats(self, ctx):
        """View your betting statistics."""
        await self.db.ensure_user(str(ctx.author.id), ctx.author.display_name)
        s = await self.db.get_user_bet_stats(str(ctx.author.id))
        embed = discord.Embed(title="📊  Betting Stats", color=COLOR_BET)
        embed.add_field(name="Total Bets",    value=str(s["total"]),         inline=True)
        embed.add_field(name="✅ Wins",        value=str(s["wins"]),          inline=True)
        embed.add_field(name="❌ Losses",      value=str(s["losses"]),        inline=True)
        embed.add_field(name="Wagered",       value=fmt(s["total_wagered"]), inline=True)
        embed.add_field(name="Won",           value=fmt(s["total_won"]),     inline=True)
        net = s["total_won"] - s["total_wagered"]
        embed.add_field(name="Net P&L",       value=fmt(net),                inline=True)
        wr = (s["wins"]/s["total"]*100) if s["total"] > 0 else 0
        embed.add_field(name="Win Rate",      value=f"{wr:.1f}%",            inline=True)
        await ctx.send(embed=embed)

    # ── ADMIN ─────────────────────────────────────────────────────────────────

    @commands.command(name="economystats", aliases=["ecostats", "economy"])
    @commands.check(admin_only)
    async def economystats(self, ctx):
        """[Admin] Full economy dashboard."""
        t   = await self.db.get_treasury()
        ms  = await self.db.total_money_supply()
        mins= await self.db.get_all_ministries()
        top = await self.db.richest_users(5)
        biz = await self.db.top_businesses(5)
        embed = discord.Embed(title="📊  Nigerian Economy Dashboard", color=COLOR_GOLD)
        embed.add_field(name="🏛 Treasury",    value=fmt(t["balance"]), inline=True)
        embed.add_field(name="💵 Citizens",    value=fmt(ms),           inline=True)
        embed.add_field(name="🏢 Ministries",  value=str(len(mins)),    inline=True)
        if top:
            embed.add_field(name="🏆 Top Citizens",
                value="\n".join(f"{i+1}. {u['username']} — {fmt(u['wallet']+u['bank'])}"
                    for i,u in enumerate(top)), inline=False)
        if biz:
            embed.add_field(name="🏢 Top Businesses",
                value="\n".join(f"{i+1}. {b['name']} — {fmt(b['balance'])}"
                    for i,b in enumerate(biz)), inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="addmoney", aliases=["givemoney"])
    @commands.check(admin_only)
    async def addmoney(self, ctx, member: discord.Member, amount: int, *, reason: str = "Admin"):
        """[Admin] Add money to a user's wallet."""
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.update_wallet(str(member.id), amount)
        await self.db.log_transaction(None, str(member.id), amount, "admin_add", reason)
        await ctx.send(embed=success_embed("Money Added",
            f"{fmt(amount)} added to **{member.display_name}**. Reason: {reason}"))

    @commands.command(name="removemoney", aliases=["takemoney"])
    @commands.check(admin_only)
    async def removemoney(self, ctx, member: discord.Member, amount: int, *, reason: str = "Admin"):
        """[Admin] Remove money from a user's wallet."""
        if amount <= 0:
            return await ctx.send(embed=error_embed("Invalid Amount"))
        u = await self.db.get_or_create_user(str(member.id), member.display_name)
        deduct = min(amount, u["wallet"])
        await self.db.update_wallet(str(member.id), -deduct)
        await self.db.log_transaction(str(member.id), None, deduct, "admin_remove", reason)
        await ctx.send(embed=success_embed("Money Removed",
            f"{fmt(deduct)} removed from **{member.display_name}**. Reason: {reason}"))

    @commands.command(name="resetuser")
    @commands.check(admin_only)
    async def resetuser(self, ctx, member: discord.Member):
        """[Admin] Reset a user's account to defaults."""
        await self.db.execute(
            "UPDATE users SET wallet=50000, bank=0, job='Citizen', last_work=NULL, last_daily=NULL WHERE user_id=?",
            (str(member.id),))
        await ctx.send(embed=success_embed("User Reset",
            f"**{member.display_name}**'s account reset to defaults."))

    @commands.command(name="sync")
    @commands.check(admin_only)
    async def sync(self, ctx):
        """[Admin] Sync slash commands."""
        synced = await self.bot.tree.sync()
        await ctx.send(embed=success_embed("Synced", f"{len(synced)} slash commands synced."))

    # ── global error handler for this cog ─────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Only handle errors for this bot's prefix commands
        if isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=error_embed("Member Not Found", str(error)), delete_after=8)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=error_embed("Missing Argument",
                f"`{error.param.name}` is required. Check `!cmds` for usage."), delete_after=8)
        elif isinstance(error, commands.BadArgument):
            await ctx.send(embed=error_embed("Bad Argument", str(error)), delete_after=8)
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(embed=error_embed("Access Denied"), delete_after=5)
        elif isinstance(error, commands.CommandNotFound):
            pass  # silently ignore unknown commands


async def setup(bot):
    await bot.add_cog(Prefix(bot))
