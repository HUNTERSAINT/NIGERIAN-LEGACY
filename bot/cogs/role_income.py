"""Recurring bank income attached to Discord roles."""
import asyncio
from datetime import datetime, timedelta

import discord
from discord.ext import commands, tasks
from discord import app_commands

from bot.utils import fmt, success_embed, error_embed, info_embed, is_admin


class RoleIncome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.payout_loop.start()

    def cog_unload(self):
        self.payout_loop.cancel()

    @property
    def db(self):
        return self.bot.db

    @tasks.loop(seconds=60)
    async def payout_loop(self):
        for guild in self.bot.guilds:
            schedules = await self.db.get_due_role_income(str(guild.id))
            for schedule in schedules:
                role = guild.get_role(int(schedule["role_id"]))
                if not role:
                    continue
                for member in role.members:
                    last = await self.db.get_last_role_payment(schedule["id"], str(member.id))
                    if last:
                        due = datetime.fromisoformat(last["paid_at"]) + timedelta(
                            hours=float(schedule["interval_hours"])
                        )
                        if datetime.utcnow() < due:
                            continue
                    await self.db.get_or_create_user(str(member.id), member.display_name)
                    await self.db.update_bank(str(member.id), schedule["income"])
                    await self.db.record_role_payment(
                        schedule["id"], str(guild.id), str(member.id), schedule["income"]
                    )
                    await self.db.log_transaction(
                        None, str(member.id), schedule["income"], "role_income",
                        f"{schedule['role_name']} income"
                    )

    @payout_loop.before_loop
    async def before_payout_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="role-income-create", description="[Admin] Create a Discord role with recurring bank income.")
    @app_commands.describe(role_name="Role to create.", income="Amount paid into bank.", interval_hours="Hours between payments.")
    async def role_income_create(self, interaction: discord.Interaction, role_name: str,
                                 income: int, interval_hours: float):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Admins Only"), ephemeral=True)
        if income <= 0 or interval_hours <= 0:
            return await interaction.response.send_message(embed=error_embed("Income and interval must be positive."), ephemeral=True)
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if role is None:
            role = await interaction.guild.create_role(name=role_name, reason="Nigerian Legacy role income setup")
        await self.db.upsert_role_income(
            str(interaction.guild.id), str(role.id), role.name, income, interval_hours, str(interaction.user.id)
        )
        await interaction.response.send_message(embed=success_embed(
            "Role Income Created",
            f"Role: **{role.name}**\nIncome: **{fmt(income)}** paid to bank every **{interval_hours:g} hours**."
        ))

    @app_commands.command(name="role-income-list", description="[Admin] List recurring role income schedules.")
    async def role_income_list(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Admins Only"), ephemeral=True)
        schedules = await self.db.get_role_income(str(interaction.guild.id))
        if not schedules:
            return await interaction.response.send_message(embed=info_embed("No Role Income", "Create one with /role-income-create."))
        embed = discord.Embed(title="💼 Role Income Schedules", color=0x008751)
        for s in schedules:
            state = "ON" if s["enabled"] else "OFF"
            embed.add_field(name=f"#{s['id']} — {s['role_name']} [{state}]",
                            value=f"{fmt(s['income'])} every {s['interval_hours']:g}h", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="role-income-toggle", description="[Admin] Enable or disable a role income schedule.")
    @app_commands.describe(schedule_id="Schedule ID.", enabled="True to enable, false to disable.")
    async def role_income_toggle(self, interaction: discord.Interaction, schedule_id: int, enabled: bool):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Admins Only"), ephemeral=True)
        await self.db.set_role_income_enabled(schedule_id, enabled)
        await interaction.response.send_message(embed=success_embed(
            "Role Income Updated", f"Schedule #{schedule_id} is now {'enabled' if enabled else 'disabled'}."
        ))

async def setup(bot):
    await bot.add_cog(RoleIncome(bot))