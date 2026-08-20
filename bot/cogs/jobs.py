"""
Job system commands:
  /jobs, /setjob (admin), /myjob
"""
import discord
from discord.ext import commands
from discord import app_commands

from bot.config import JOBS, GOV_ROLES, COLOR_INFO, COLOR_GOLD
from bot.utils import fmt, success_embed, error_embed, info_embed, has_any_role


async def sync_job_role(member: discord.Member, job: str):
    """Make the Discord role and database job agree."""
    job_role_names = {data["role"] or name for name, data in JOBS.items()}
    roles_to_remove = [role for role in member.roles if role.name in job_role_names]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove, reason="Job role synchronization")
    target_name = JOBS[job]["role"] or job
    target = discord.utils.get(member.guild.roles, name=target_name)
    if target:
        await member.add_roles(target, reason=f"Assigned job: {job}")


class Jobs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── /jobs ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="jobs", description="List all available jobs and their salaries.")
    async def jobs(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="💼  Available Jobs — Federal Republic of Nigeria",
            description="Monthly salaries and per-work earnings for each role.",
            color=COLOR_GOLD,
        )
        for job_name, data in JOBS.items():
            role_req = data["role"] or "None (default)"
            embed.add_field(
                name=f"{'🏛' if data['role'] and data['role'] in GOV_ROLES else '👤'}  {job_name}",
                value=(
                    f"Monthly salary: **{fmt(data['monthly'])}**\n"
                    f"Per /work: **{fmt(data['work'])}**\n"
                    f"Required role: `{role_req}`"
                ),
                inline=True,
            )
        embed.set_footer(text="Jobs are assigned by an Admin using /setjob.")
        await interaction.response.send_message(embed=embed)

    # ── /myjob ────────────────────────────────────────────────────────────────

    @app_commands.command(name="myjob", description="View your current job and salary details.")
    async def myjob(self, interaction: discord.Interaction):
        u = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        job = u["job"]
        data = JOBS.get(job, JOBS["Citizen"])

        embed = discord.Embed(title=f"💼  {interaction.user.display_name}'s Job", color=COLOR_INFO)
        embed.add_field(name="Job Title",       value=job,                         inline=True)
        embed.add_field(name="Monthly Salary",  value=fmt(data["monthly"]),        inline=True)
        embed.add_field(name="Per /work",       value=fmt(data["work"]),           inline=True)
        embed.add_field(name="Role Required",   value=data["role"] or "None",      inline=True)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)

    # ── /setjob ───────────────────────────────────────────────────────────────

    @app_commands.command(name="setjob", description="[Admin/President] Assign a job to a citizen.")
    @app_commands.describe(member="Who to assign.", job="Job title from /jobs list.")
    async def setjob(self, interaction: discord.Interaction, member: discord.Member, job: str):
        await interaction.response.defer()

        # Must be admin or President/Governor
        is_admin = interaction.user.guild_permissions.administrator
        is_president = any(r.name in {"President", "Vice President", "Governor"} for r in interaction.user.roles)

        if not is_admin and not is_president:
            return await interaction.followup.send(
                embed=error_embed("Access Denied", "Server Admins, President, Vice President, or Governor only."),
                ephemeral=True,
            )

        if job not in JOBS:
            return await interaction.followup.send(
                embed=error_embed("Unknown Job", f"Valid jobs: {', '.join(JOBS.keys())}")
            )

        await self.db.get_or_create_user(str(member.id), member.display_name)
        await self.db.set_job(str(member.id), job)
        try:
            await sync_job_role(member, job)
        except discord.Forbidden:
            return await interaction.followup.send(
                embed=error_embed("Role Assignment Failed", "The job was saved, but the bot cannot manage the job role hierarchy.")
            )

        embed = success_embed(
            "Job Assigned",
            f"**{member.display_name}** has been appointed as **{job}**.\n"
            f"Monthly salary: {fmt(JOBS[job]['monthly'])}"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Jobs(bot))
