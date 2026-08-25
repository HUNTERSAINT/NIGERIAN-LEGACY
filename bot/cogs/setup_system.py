"""Nigerian Legacy RP server setup, airport onboarding, visas, and immigration review."""
import secrets
import string

import discord
from discord.ext import commands
from discord import app_commands

from bot.cogs.role_setup import ensure_required_roles
from bot.utils import error_embed, info_embed, is_admin, success_embed

CATEGORY_NAME = "Nigerian Legacy RP"
CHANNELS = {
    "airport": "airport",
    "invite_tracker": "invite-tracker",
    "lounge": "immigration-lounge",
    "office": "immigration-office",
    "welcome": "welcome-and-guide",
    "government": "government",
    "economy": "economy",
    "banking": "banking",
    "business": "businesses",
    "betting": "betting",
    "roulette": "roulette",
    "store": "store",
    "logs": "nigerian-legacy-logs",
    "police": "police-department",
    "jail": "jail",
    "general_logs": "general-logs",
    "law-court": "court-room",
    "law-verdicts": "verdicts",
    "law-legal-aid": "legal-aid",
    "police-reports": "police-reports",
    "finance-treasury": "treasury-office",
    "finance-tax": "tax-office",
    "finance-audit": "finance-audit",
    "government-ministry": "ministries",
    "government-cabinet": "cabinet",
    "government-elections": "elections",
    "health-clinic": "clinic",
    "health-records": "medical-records",
    "business-registry": "business-registry",
    "business-contracts": "contracts",
    "citizen-help": "citizen-help",
    "citizen-jobs": "job-centre",
}
CHANNEL_EMOJIS = {
    "airport": "✈️", "invite_tracker": "📨", "lounge": "🛋️", "office": "🛂",
    "welcome": "👋", "government": "🏛️", "economy": "💰", "banking": "🏦",
    "business": "🏢", "betting": "⚽", "roulette": "🎰", "store": "🛒",
    "logs": "📋", "police": "🚓", "jail": "🔒", "general_logs": "📢",
    "law-court": "⚖️", "law-verdicts": "📜", "law-legal-aid": "🧑‍⚖️",
    "police-reports": "📝", "finance-treasury": "🏛️", "finance-tax": "🧾",
    "finance-audit": "🔍", "government-ministry": "🏢", "government-cabinet": "👔",
    "government-elections": "🗳️", "health-clinic": "🏥", "health-records": "🩺",
    "business-registry": "📇", "business-contracts": "📄", "citizen-help": "🆘",
    "citizen-jobs": "💼",
}
DISPLAY_CHANNELS = {
    key: f"{CHANNEL_EMOJIS[key]}・{name}" for key, name in CHANNELS.items()
}


def channel_matches(channel, key: str) -> bool:
    return channel is not None and channel.name in {CHANNELS[key], DISPLAY_CHANNELS[key]}
CATEGORY_NAMES = {
    "airport": "✈️ AIRPORT & IMMIGRATION",
    "invite_tracker": "✈️ AIRPORT & IMMIGRATION",
    "lounge": "✈️ AIRPORT & IMMIGRATION",
    "office": "✈️ AIRPORT & IMMIGRATION",
    "welcome": "✈️ AIRPORT & IMMIGRATION",
    "government": "🏛️ GOVERNMENT",
    "economy": "💰 ECONOMY & SERVICES",
    "banking": "💰 ECONOMY & SERVICES",
    "business": "💰 ECONOMY & SERVICES",
    "store": "💰 ECONOMY & SERVICES",
    "betting": "🎮 ENTERTAINMENT",
    "roulette": "🎮 ENTERTAINMENT",
    "police": "🚓 POLICE DEPARTMENT",
    "jail": "🚓 POLICE DEPARTMENT",
    "general_logs": "📋 ADMINISTRATION",
    "logs": "📋 ADMINISTRATION",
    "general_logs": "📋 ADMINISTRATION",
    "law-court": "⚖️ LAW & JUDICIARY",
    "law-verdicts": "⚖️ LAW & JUDICIARY",
    "law-legal-aid": "⚖️ LAW & JUDICIARY",
    "police-reports": "🚓 POLICE DEPARTMENT",
    "finance-treasury": "🏦 FINANCE & CBN",
    "finance-tax": "🏦 FINANCE & CBN",
    "finance-audit": "🏦 FINANCE & CBN",
    "government-ministry": "🏛️ GOVERNMENT",
    "government-cabinet": "🏛️ GOVERNMENT",
    "government-elections": "🏛️ GOVERNMENT",
    "health-clinic": "🏥 HEALTH SERVICES",
    "health-records": "🏥 HEALTH SERVICES",
    "business-registry": "🏢 COMMERCE & BUSINESS",
    "business-contracts": "🏢 COMMERCE & BUSINESS",
    "citizen-help": "🧑 CITIZEN SERVICES",
    "citizen-jobs": "🧑 CITIZEN SERVICES",
}
DEPARTMENT_ROLES = {
    "law-court": {"Judge", "Lawyer"},
    "law-verdicts": {"Judge", "Lawyer"},
    "law-legal-aid": {"Judge", "Lawyer"},
    "police-reports": {"Police Officer"},
    "finance-treasury": {"Minister of Finance", "Accountant General", "CBN Governor"},
    "finance-tax": {"Minister of Finance", "Accountant General"},
    "finance-audit": {"Minister of Finance", "Accountant General"},
    "government-ministry": {"President", "Vice President", "Governor", "Minister", "Senator"},
    "government-cabinet": {"President", "Vice President", "Governor", "Minister"},
    "government-elections": {"INEC Chairman"},
    "health-clinic": {"Doctor"},
    "health-records": {"Doctor"},
    "business-registry": {"Business Owner"},
    "business-contracts": {"Business Owner"},
    "citizen-help": {"Citizen"},
    "citizen-jobs": {"Citizen"},
}


def officer_or_admin(member: discord.Member) -> bool:
    return is_admin(member) or any(
        role.name == "Immigration Officer" for role in member.roles
    )


def make_number(prefix: str, length: int) -> str:
    return prefix + "".join(secrets.choice(string.digits) for _ in range(length))


async def send_log(guild: discord.Guild, message: str):
    channel = discord.utils.find(lambda c: channel_matches(c, "logs"), guild.text_channels)
    if channel:
        try:
            await channel.send(f"📝 {message}")
        except discord.Forbidden:
            pass


def setup_overwrites(guild: discord.Guild, key: str):
    """Only airport is visible to unregistered @everyone members."""
    everyone = guild.default_role
    bot_member = guild.me
    citizen = discord.utils.get(guild.roles, name="Citizen")
    visa = discord.utils.get(guild.roles, name="Visa Holder")
    officer = discord.utils.get(guild.roles, name="Immigration Officer")
    police = discord.utils.get(guild.roles, name="Police Officer")
    inmate = discord.utils.get(guild.roles, name="Jail Inmate")
    deny = discord.PermissionOverwrite(view_channel=False)
    allow = discord.PermissionOverwrite(view_channel=True, send_messages=True)
    overwrites = {everyone: deny}

    if key == "airport":
        overwrites[everyone] = allow
    elif key == "lounge" and visa:
        overwrites[visa] = allow
    elif key == "office" and officer:
        overwrites[officer] = allow
    elif key == "jail" and inmate:
        overwrites[inmate] = allow
        if police:
            overwrites[police] = allow
    elif key == "police" and police:
        overwrites[police] = allow
    elif key in DEPARTMENT_ROLES:
        for role_name in DEPARTMENT_ROLES[key]:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                overwrites[role] = allow
    elif key == "logs":
        pass
    elif key == "general_logs":
        pass
    elif citizen:
        overwrites[citizen] = allow

    if bot_member:
        overwrites[bot_member] = allow
    if inmate and key not in {"jail", "police"}:
        overwrites[inmate] = deny
    return overwrites


async def get_or_create_channels(guild: discord.Guild):
    result = {}
    for key, name in CHANNELS.items():
        category_name = CATEGORY_NAMES[key]
        category = discord.utils.get(guild.categories, name=category_name)
        if category is None:
            category = await guild.create_category(
                category_name, reason="Nigerian Legacy RP server setup"
            )
        channel = discord.utils.find(
            lambda c: channel_matches(c, key), guild.text_channels
        )
        overwrites = setup_overwrites(guild, key)
        if channel is None:
            channel = await guild.create_text_channel(
                DISPLAY_CHANNELS[key],
                category=category,
                overwrites=overwrites,
                reason="Nigerian Legacy RP server setup",
            )
        else:
            await channel.edit(
                name=DISPLAY_CHANNELS[key],
                category=category,
                overwrites=overwrites,
                reason="Nigerian Legacy RP permission refresh",
            )
        result[key] = channel
    return result


async def ensure_roulette_channel(guild: discord.Guild):
    """Create the public roulette channel once the bot connects to a guild."""
    category_name = CATEGORY_NAMES["roulette"]
    category = discord.utils.get(guild.categories, name=category_name)
    if category is None:
        category = await guild.create_category(
            category_name, reason="Nigerian Legacy RP roulette channel"
        )

    channel = discord.utils.find(
        lambda c: channel_matches(c, "roulette"), guild.text_channels
    )
    if channel is not None:
        return channel, False

    everyone = guild.default_role
    bot_member = guild.me
    overwrites = {
        everyone: discord.PermissionOverwrite(
            view_channel=True, send_messages=True
        )
    }
    if bot_member:
        overwrites[bot_member] = discord.PermissionOverwrite(
            view_channel=True, send_messages=True, embed_links=True
        )
    channel = await guild.create_text_channel(
        DISPLAY_CHANNELS["roulette"],
        category=category,
        overwrites=overwrites,
        reason="Nigerian Legacy RP roulette channel",
    )
    return channel, True


async def approve_application(bot, interaction, guild_id: str, user_id: str):
    guild = interaction.guild
    member = guild.get_member(int(user_id))
    application = await bot.db.get_immigration(guild_id, user_id)
    if not member or not application:
        return await interaction.followup.send(
            embed=error_embed("Application Not Found"), ephemeral=True
        )
    if application["status"] == "approved":
        return await interaction.followup.send(
            embed=info_embed(
                "Already Approved",
                f"National ID: `{application['national_id']}`\nTIN: `{application['tin']}`",
            ),
            ephemeral=True,
        )
    national_id = make_number("NG", 10)
    tin = make_number("TIN", 9)
    await bot.db.approve_immigration(
        guild_id, user_id, national_id, tin, str(interaction.user.id)
    )
    citizen = discord.utils.get(guild.roles, name="Citizen")
    visa = discord.utils.get(guild.roles, name="Visa Holder")
    try:
        if visa and visa in member.roles:
            await member.remove_roles(visa, reason="Immigration approved")
        if citizen and citizen not in member.roles:
            await member.add_roles(citizen, reason="Immigration approved")
    except discord.Forbidden:
        pass
    await send_log(
        guild,
        f"Citizenship approved: {member} by {interaction.user}. "
        f"NID={national_id}, TIN={tin}",
    )
    await interaction.followup.send(
        embed=success_embed(
            "Citizenship Approved",
            f"{member.mention} is now a registered citizen.\n"
            f"National ID: `{national_id}`\nTIN: `{tin}`",
        ),
        ephemeral=True,
    )


async def grant_manual_citizenship(bot, guild: discord.Guild, officer: discord.Member,
                                   member: discord.Member, full_name: str, age: int,
                                   state: str, send):
    """Issue citizenship directly to a player from an officer/admin command."""
    if not officer_or_admin(officer):
        return await send(embed=error_embed(
            "Access Denied", "Immigration Officers or Administrators only."
        ))
    if age < 18 or age > 100 or len(full_name.strip()) < 3 or len(state.strip()) < 2:
        return await send(embed=error_embed(
            "Invalid Citizenship Details",
            "Use a full name, an age from 18 to 100, and a valid state.",
        ))

    guild_id = str(guild.id)
    user_id = str(member.id)
    application = await bot.db.get_immigration(guild_id, user_id)
    if application and application["status"] == "approved":
        return await send(embed=info_embed(
            "Already a Citizen",
            f"{member.mention} already has citizenship.\n"
            f"National ID: `{application['national_id']}`\n"
            f"TIN: `{application['tin']}`",
        ))

    await bot.db.register_immigration(guild_id, user_id, full_name.strip(), age, state.strip())
    national_id = make_number("NG", 10)
    tin = make_number("TIN", 9)
    await bot.db.approve_immigration(guild_id, user_id, national_id, tin, str(officer.id))

    citizen = discord.utils.get(guild.roles, name="Citizen")
    visa = discord.utils.get(guild.roles, name="Visa Holder")
    try:
        if visa and visa in member.roles:
            await member.remove_roles(visa, reason="Manual citizenship granted")
        if citizen and citizen not in member.roles:
            await member.add_roles(citizen, reason="Manual citizenship granted")
    except discord.Forbidden:
        return await send(embed=error_embed(
            "Role Permission Error",
            "Citizenship was recorded, but Discord refused the role change. "
            "Move the bot role above Citizen and Visa Holder, then run the command again.",
        ))

    await send_log(
        guild,
        f"Manual citizenship granted: {member} by {officer}. "
        f"NID={national_id}, TIN={tin}",
    )
    return await send(embed=success_embed(
        "Citizenship Granted",
        f"{member.mention} is now a registered citizen.\n"
        f"National ID: `{national_id}`\nTIN: `{tin}`\n"
        f"Granted manually by {officer.mention}.",
    ))


class ImmigrationReviewView(discord.ui.View):
    """Persistent buttons for immigration-office application messages."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        custom_id="nigerian-legacy:immigration:approve",
    )
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not officer_or_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "Immigration Officers or Administrators only."),
                ephemeral=True,
            )
        footer = interaction.message.embeds[0].footer.text
        guild_id, user_id = footer.replace("Nigerian Legacy Application | ", "").split(":")
        await interaction.response.defer(ephemeral=True)
        await approve_application(self.bot, interaction, guild_id, user_id)
        await interaction.message.edit(view=None)

    @discord.ui.button(
        label="Decline",
        style=discord.ButtonStyle.danger,
        custom_id="nigerian-legacy:immigration:decline",
    )
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not officer_or_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Access Denied", "Immigration Officers or Administrators only."),
                ephemeral=True,
            )
        footer = interaction.message.embeds[0].footer.text
        guild_id, user_id = footer.replace("Nigerian Legacy Application | ", "").split(":")
        await interaction.response.defer(ephemeral=True)
        await self.bot.db.decline_immigration(guild_id, user_id, str(interaction.user.id))
        await send_log(
            interaction.guild,
            f"Immigration application declined for <@{user_id}> by {interaction.user}.",
        )
        await interaction.followup.send(
            embed=info_embed("Application Declined", f"<@{user_id}> was not approved."),
            ephemeral=True,
        )
        await interaction.message.edit(view=None)


class SetupSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.bot.db.ensure_user(str(member.id), str(member))
        airport = discord.utils.find(
            lambda c: channel_matches(c, "airport"), member.guild.text_channels
        )
        ticket = make_number("MC-TKT-", 8)
        message = (
            f"🛬 **Welcome to Nigerian Legacy RP, {member.mention}!**\n\n"
            f"Your flight has landed at the Nigerian Legacy Airport.\n"
            f"**Flight ticket:** `{ticket}`\n\n"
            "You can currently see only this airport. Use `!claimvisa` to claim your "
            "arrival visa. Your visa will unlock the Immigration Lounge, where you "
            "can submit your citizenship registration."
        )
        if airport:
            try:
                await airport.send(message)
            except discord.Forbidden:
                pass
        tracker = discord.utils.find(
            lambda c: channel_matches(c, "invite_tracker"), member.guild.text_channels
        )
        if tracker:
            try:
                await tracker.send(
                    f"✈️ New arrival: {member.mention} | Ticket `{ticket}` | ID `{member.id}`"
                )
            except discord.Forbidden:
                pass
        await send_log(member.guild, f"New arrival: {member} ({member.id}), ticket {ticket}")

    async def run_setup(self, guild: discord.Guild, actor: discord.Member):
        if not is_admin(actor):
            return None, "Admins only."
        permissions = guild.me.guild_permissions
        if not permissions.manage_channels or not permissions.manage_roles:
            return None, "The bot needs **Manage Channels** and **Manage Roles** permissions."
        restored = await self.bot.db.sync_players_from_text()
        await self.bot.db.sync_players_to_text()
        await ensure_required_roles(guild)
        channels = await get_or_create_channels(guild)
        await channels["airport"].send(
            "🛬 **Nigerian Legacy Airport**\nNew arrivals see this channel first. "
            "They must use `!claimvisa` before they can access the Immigration Lounge."
        )
        await channels["lounge"].send(
            "🛂 **Immigration Lounge**\nVisa holders submit citizenship applications here with:\n"
            "`!register Full Name, Age, State`"
        )
        await send_log(guild, f"Server setup completed by {actor} ({actor.id}).")
        return channels, restored

    @app_commands.command(name="setup", description="[Admin] Create Nigerian Legacy RP server channels and roles.")
    async def setup_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channels, result = await self.run_setup(interaction.guild, interaction.user)
        if isinstance(result, str):
            return await interaction.edit_original_response(embed=error_embed("Setup Failed", result))
        await interaction.edit_original_response(
            embed=success_embed(
                "Nigerian Legacy RP Setup Complete",
                f"Created or refreshed **{len(channels)}** channels and roles.\n"
                f"Player text backup synced; restored **{result}** missing account(s).",
            )
        )

    @commands.command(name="setup")
    @commands.guild_only()
    async def setup_prefix(self, ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Server Administrators only."))
        try:
            channels, result = await self.run_setup(ctx.guild, ctx.author)
        except discord.Forbidden:
            return await ctx.send(embed=error_embed("Setup Failed", "Check Manage Channels, Manage Roles, and role hierarchy."))
        if isinstance(result, str):
            return await ctx.send(embed=error_embed("Setup Failed", result))
        await ctx.send(embed=success_embed(
            "Nigerian Legacy RP Setup Complete",
            f"Created or refreshed **{len(channels)}** channels and roles.\n"
            f"Player text backup synced; restored **{result}** missing account(s).",
        ))

    @commands.command(name="claimvisa", aliases=["claim-visa", "visa"])
    @commands.guild_only()
    async def claim_visa(self, ctx):
        visa = discord.utils.get(ctx.guild.roles, name="Visa Holder")
        if not visa:
            return await ctx.send(embed=error_embed("Setup Required", "An administrator must run `!setup` first."))
        if visa in ctx.author.roles:
            return await ctx.send(embed=info_embed("Visa Already Claimed", "Your Immigration Lounge access is active."))
        try:
            await ctx.author.add_roles(visa, reason="New arrival claimed visa")
        except discord.Forbidden:
            return await ctx.send(embed=error_embed("Permission Error", "The bot cannot assign the Visa Holder role."))
        await send_log(ctx.guild, f"Visa claimed by {ctx.author} ({ctx.author.id}).")
        await ctx.send(embed=success_embed("Arrival Visa Issued", "You can now enter #immigration-lounge and submit `!register Full Name, Age, State`."))

    def can_register_here(self, ctx_or_interaction):
        channel = ctx_or_interaction.channel
        user = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
        return channel_matches(channel, "lounge") and any(
            role.name == "Visa Holder" for role in user.roles
        )

    async def submit_application(self, guild, user, full_name, age, state, send):
        if not self.can_register_here(send.__self__ if hasattr(send, "__self__") else user):
            return await send(embed=error_embed("Immigration Lounge Only", "Claim your visa and submit registration inside #immigration-lounge."))
        if age < 18 or age > 100 or len(full_name.strip()) < 3:
            return await send(embed=error_embed("Invalid Application", "Use a full name and an age from 18 to 100."))
        await self.bot.db.get_or_create_user(str(user.id), str(user))
        application = await self.bot.db.register_immigration(str(guild.id), str(user.id), full_name.strip(), age, state.strip())
        office = discord.utils.find(lambda c: channel_matches(c, "office"), guild.text_channels)
        if office:
            embed = discord.Embed(title="🛂 New Immigration Application", color=0xF2C94C)
            embed.add_field(name="Applicant", value=f"{user.mention} (`{user.id}`)", inline=False)
            embed.add_field(name="Full Name", value=application["full_name"], inline=True)
            embed.add_field(name="Age", value=str(application["age"]), inline=True)
            embed.add_field(name="State", value=application["state"], inline=True)
            embed.set_footer(text=f"Nigerian Legacy Application | {guild.id}:{user.id}")
            await office.send(embed=embed, view=ImmigrationReviewView(self.bot))
        await send_log(guild, f"Immigration application submitted by {user}: {full_name}, {age}, {state}")
        return await send(embed=success_embed("Application Submitted", "Your request was sent to the private Immigration Office for approval."))

    @commands.command(name="register")
    @commands.guild_only()
    async def register_prefix(self, ctx, *, details: str):
        parts = [part.strip() for part in details.split(",")]
        if len(parts) != 3:
            return await ctx.send(embed=error_embed("Usage", "`!register Full Name, Age, State`"))
        try:
            age = int(parts[1])
        except ValueError:
            age = 0
        return await self.submit_application(ctx.guild, ctx.author, parts[0], age, parts[2], ctx.send)

    @app_commands.command(name="register", description="Submit a citizenship application from the Immigration Lounge.")
    async def register_slash(self, interaction: discord.Interaction, full_name: str, age: int, state: str):
        await interaction.response.defer(ephemeral=True)
        if not self.can_register_here(interaction):
            return await interaction.edit_original_response(embed=error_embed("Immigration Lounge Only", "Claim your visa and use this command inside #immigration-lounge."))
        return await self.submit_application(interaction.guild, interaction.user, full_name, age, state, interaction.edit_original_response)

    @commands.command(name="immigration-pending", aliases=["immigrationlist"])
    @commands.guild_only()
    async def pending_prefix(self, ctx):
        if not officer_or_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Immigration Officers or Administrators only."))
        rows = await self.bot.db.get_pending_immigration(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=info_embed("Immigration Queue", "No pending applications."))
        await ctx.send(embed=info_embed("Pending Applications", "\n".join(
            f"`{row['user_id']}` — **{row['full_name']}**, age {row['age']}, {row['state']}" for row in rows
        )))

    @commands.command(
        name="grantcitizenship",
        aliases=["givecitizenship", "citizenship"],
    )
    @commands.guild_only()
    async def grant_citizenship_prefix(self, ctx, member: discord.Member, *, details: str):
        """[Immigration Officer/Admin] Grant citizenship without a pending application."""
        if not officer_or_admin(ctx.author):
            return await ctx.send(embed=error_embed(
                "Access Denied", "Immigration Officers or Administrators only."
            ))
        parts = [part.strip() for part in details.split(",")]
        if len(parts) != 3:
            return await ctx.send(embed=error_embed(
                "Usage",
                "`!grantcitizenship @player Full Name, Age, State`",
            ))
        try:
            age = int(parts[1])
        except ValueError:
            age = 0
        return await grant_manual_citizenship(
            self.bot, ctx.guild, ctx.author, member, parts[0], age, parts[2], ctx.send
        )

    @app_commands.command(
        name="grant-citizenship",
        description="[Officer/Admin] Give a player citizenship manually.",
    )
    @app_commands.describe(
        member="Player receiving citizenship.",
        full_name="The player's registered full name.",
        age="The player's age (18–100).",
        state="The player's Nigerian state.",
    )
    async def grant_citizenship_slash(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        full_name: str,
        age: int,
        state: str,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                embed=error_embed("Server Only", "This command can only be used inside a server."),
                ephemeral=True,
            )
        if not officer_or_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed(
                    "Access Denied", "Immigration Officers or Administrators only."
                ),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        return await grant_manual_citizenship(
            self.bot,
            interaction.guild,
            interaction.user,
            member,
            full_name,
            age,
            state,
            interaction.followup.send,
        )

    @commands.command(name="idcard", aliases=["nationalid", "tin"])
    @commands.guild_only()
    async def idcard_prefix(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        application = await self.bot.db.get_immigration(str(ctx.guild.id), str(member.id))
        if not application or application["status"] != "approved":
            return await ctx.send(embed=error_embed("No ID Card", "This player has not been approved by Immigration."))
        embed = discord.Embed(title="🇳🇬 Federal Republic of Nigeria", description="**NIGERIAN LEGACY NATIONAL IDENTITY CARD**", color=0x008751)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Holder", value=application["full_name"], inline=False)
        embed.add_field(name="National ID", value=f"`{application['national_id']}`", inline=True)
        embed.add_field(name="TIN", value=f"`{application['tin']}`", inline=True)
        embed.add_field(name="State", value=application["state"], inline=True)
        embed.add_field(name="Status", value="✅ Verified Citizen", inline=True)
        await ctx.send(embed=embed)

    async def cog_load(self):
        self.bot.add_view(ImmigrationReviewView(self.bot))


async def setup(bot):
    await bot.add_cog(SetupSystem(bot))