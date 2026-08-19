"""Server setup, welcome guidance, and the MetroCity immigration office."""
import secrets
import string
import discord
from discord.ext import commands
from discord import app_commands

from bot.cogs.role_setup import ensure_required_roles
from bot.utils import error_embed, info_embed, is_admin, success_embed

CATEGORY_NAME = "MetroCity RP"
CHANNELS = {
    "welcome": "welcome-and-guide",
    "immigration": "immigration",
    "immigration-office": "immigration-office",
    "government": "government",
    "economy": "economy",
    "banking": "banking",
    "business": "businesses",
    "betting": "betting",
    "store": "store",
    "logs": "metrocity-logs",
}


def officer_or_admin(member: discord.Member) -> bool:
    return is_admin(member) or any(
        role.name == "Immigration Officer" for role in member.roles
    )


async def get_or_create_channels(guild: discord.Guild):
    category = discord.utils.get(guild.categories, name=CATEGORY_NAME)
    if category is None:
        category = await guild.create_category(
            CATEGORY_NAME, reason="MetroCity RP server setup"
        )

    result = {}
    for key, name in CHANNELS.items():
        channel = discord.utils.get(guild.text_channels, name=name)
        if channel is None:
            overwrites = {}
            if key == "logs":
                overwrites[guild.default_role] = discord.PermissionOverwrite(
                    view_channel=False
                )
                overwrites[guild.me] = discord.PermissionOverwrite(
                    view_channel=True, send_messages=True
                )
            elif key == "immigration-office":
                officer_role = discord.utils.get(
                    guild.roles, name="Immigration Officer"
                )
                if officer_role:
                    overwrites[guild.default_role] = discord.PermissionOverwrite(
                        view_channel=False
                    )
                    overwrites[officer_role] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True
                    )
                    overwrites[guild.me] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True
                    )
            channel = await guild.create_text_channel(
                name, category=category, overwrites=overwrites,
                reason="MetroCity RP server setup",
            )
        result[key] = channel
    return result


async def send_log(guild: discord.Guild, message: str):
    channel = discord.utils.get(guild.text_channels, name=CHANNELS["logs"])
    if channel:
        try:
            await channel.send(f"📝 {message}")
        except discord.Forbidden:
            pass


def make_number(prefix: str, length: int) -> str:
    alphabet = string.digits
    return prefix + "".join(secrets.choice(alphabet) for _ in range(length))


class SetupSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return
        await self.bot.db.ensure_user(str(member.id), str(member))
        channel = discord.utils.get(
            member.guild.text_channels, name=CHANNELS["welcome"]
        )
        guide = (
            f"Welcome {member.mention} to **MetroCity RP** 🇳🇬\n\n"
            "Start your citizenship journey:\n"
            "1. Go to **#immigration** and use `!register Your Full Name, Age, State`.\n"
            "2. An Immigration Officer reviews your application in **#immigration-office**.\n"
            "3. After approval, use `!idcard` to view your National ID and TIN.\n"
            "4. Use `!cmds` to explore jobs, banking, businesses, government, betting, and the store.\n\n"
            "Please follow the server rules and keep roleplay respectful."
        )
        if channel:
            try:
                await channel.send(guide)
            except discord.Forbidden:
                pass
        await send_log(member.guild, f"New member joined: {member} ({member.id})")

    async def run_setup(self, guild: discord.Guild, actor: discord.Member):
        if not is_admin(actor):
            return None, "Admins only."
        if not guild.me.guild_permissions.manage_channels:
            return None, "The bot needs **Manage Channels** and **Manage Roles** permissions."
        await ensure_required_roles(guild)
        channels = await get_or_create_channels(guild)
        await channels["welcome"].send(
            "🇳🇬 **MetroCity RP Welcome Centre**\n"
            "New citizens: go to #immigration and use "
            "`!register Your Full Name, Age, State` to apply for citizenship.\n"
            "Officers: review applications in #immigration-office."
        )
        await send_log(guild, f"Server setup completed by {actor} ({actor.id}).")
        return channels, None

    @app_commands.command(
        name="setup",
        description="[Admin] Create MetroCity categories, channels, and roles.",
    )
    async def setup_slash(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        channels, error = await self.run_setup(interaction.guild, interaction.user)
        if error:
            return await interaction.edit_original_response(
                embed=error_embed("Setup Failed", error)
            )
        await interaction.edit_original_response(
            embed=success_embed(
                "MetroCity Setup Complete",
                f"Created or reused **{len(channels)}** channels and all standard roles.\n"
                "The welcome guide and private logs channel are ready.",
            )
        )

    @commands.command(name="setup")
    @commands.guild_only()
    async def setup_prefix(self, ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Server Administrators only."))
        try:
            channels, error = await self.run_setup(ctx.guild, ctx.author)
        except discord.Forbidden:
            return await ctx.send(embed=error_embed(
                "Setup Failed", "Discord rejected channel or role creation. Check Manage Channels, Manage Roles, and role hierarchy."
            ))
        if error:
            return await ctx.send(embed=error_embed("Setup Failed", error))
        await ctx.send(embed=success_embed(
            "MetroCity Setup Complete",
            f"Created or reused **{len(channels)}** channels and all standard roles.",
        ))

    @app_commands.command(name="register", description="Apply for MetroCity citizenship.")
    @app_commands.describe(full_name="Your roleplay legal name", age="Your roleplay age", state="Your Nigerian state")
    async def register_slash(self, interaction: discord.Interaction, full_name: str, age: int, state: str):
        await interaction.response.defer(ephemeral=True)
        if age < 18 or age > 100 or len(full_name.strip()) < 3:
            return await interaction.edit_original_response(
                embed=error_embed("Invalid Application", "Use a full name and an age from 18 to 100.")
            )
        await self.bot.db.get_or_create_user(str(interaction.user.id), str(interaction.user))
        application = await self.bot.db.register_immigration(
            str(interaction.guild_id), str(interaction.user.id), full_name.strip(), age, state.strip()
        )
        await send_log(interaction.guild, f"Immigration application submitted by {interaction.user}: {full_name}, {age}, {state}")
        await interaction.edit_original_response(embed=success_embed(
            "Application Submitted",
            "Your citizenship application is pending review by an Immigration Officer.",
        ))

    @commands.command(name="register")
    @commands.guild_only()
    async def register_prefix(self, ctx, *, details: str):
        parts = [part.strip() for part in details.split(",")]
        if len(parts) != 3:
            return await ctx.send(embed=error_embed(
                "Usage", "`!register Full Name, Age, State`"
            ))
        try:
            age = int(parts[1])
        except ValueError:
            age = 0
        if age < 18 or age > 100 or len(parts[0]) < 3:
            return await ctx.send(embed=error_embed("Invalid Application", "Use a full name and an age from 18 to 100."))
        await self.bot.db.get_or_create_user(str(ctx.author.id), str(ctx.author))
        await self.bot.db.register_immigration(str(ctx.guild.id), str(ctx.author.id), parts[0], age, parts[2])
        await send_log(ctx.guild, f"Immigration application submitted by {ctx.author}: {parts[0]}, {age}, {parts[2]}")
        await ctx.send(embed=success_embed("Application Submitted", "An Immigration Officer will review your application."))

    @commands.command(name="immigration-pending", aliases=["immigrationlist"])
    @commands.guild_only()
    async def pending_prefix(self, ctx):
        if not officer_or_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Immigration Officers or Administrators only."))
        rows = await self.bot.db.get_pending_immigration(str(ctx.guild.id))
        if not rows:
            return await ctx.send(embed=info_embed("Immigration Queue", "No pending applications."))
        lines = [f"`{row['user_id']}` — **{row['full_name']}**, age {row['age']}, {row['state']}" for row in rows]
        await ctx.send(embed=info_embed("Pending Applications", "\n".join(lines)))

    @commands.command(name="immigration-approve", aliases=["approveimmigration"])
    @commands.guild_only()
    async def approve_prefix(self, ctx, member: discord.Member):
        if not officer_or_admin(ctx.author):
            return await ctx.send(embed=error_embed("Access Denied", "Immigration Officers or Administrators only."))
        application = await self.bot.db.get_immigration(str(ctx.guild.id), str(member.id))
        if not application:
            return await ctx.send(embed=error_embed("Not Found", "That player has not submitted an application."))
        if application["status"] == "approved":
            return await ctx.send(embed=info_embed("Already Approved", f"National ID: `{application['national_id']}`\nTIN: `{application['tin']}`"))
        national_id = make_number("NG", 10)
        tin = make_number("TIN", 9)
        approved = await self.bot.db.approve_immigration(
            str(ctx.guild.id), str(member.id), national_id, tin, str(ctx.author.id)
        )
        citizen = discord.utils.get(ctx.guild.roles, name="Citizen")
        if citizen and citizen not in member.roles:
            try:
                await member.add_roles(citizen, reason="Immigration application approved")
            except discord.Forbidden:
                pass
        await send_log(ctx.guild, f"Citizenship approved: {member} by {ctx.author}. NID={national_id}, TIN={tin}")
        await ctx.send(embed=success_embed(
            "Citizenship Approved",
            f"{member.mention} is now a registered citizen.\n\n"
            f"**National ID:** `{national_id}`\n**Tax Identification Number:** `{tin}`",
        ))

    @commands.command(name="idcard", aliases=["nationalid", "tin"])
    @commands.guild_only()
    async def idcard_prefix(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        application = await self.bot.db.get_immigration(str(ctx.guild.id), str(member.id))
        if not application or application["status"] != "approved":
            return await ctx.send(embed=error_embed("No ID Card", "This player has not been approved by Immigration."))
        embed = discord.Embed(title="🇳🇬 Federal Republic of Nigeria", description="**METROCITY NATIONAL IDENTITY CARD**", color=0x008751)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Holder", value=application["full_name"], inline=False)
        embed.add_field(name="National ID", value=f"`{application['national_id']}`", inline=True)
        embed.add_field(name="TIN", value=f"`{application['tin']}`", inline=True)
        embed.add_field(name="State", value=application["state"], inline=True)
        embed.add_field(name="Status", value="✅ Verified Citizen", inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(SetupSystem(bot))