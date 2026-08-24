"""Focused audit logging for server events and financial activity.

This intentionally does not mirror normal chat messages, edits, deletes, or
reactions into the logs channel.
"""
import discord
from discord.ext import commands

from bot.cogs.setup_system import channel_matches
from bot.utils import fmt


class ActivityLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def channel(self, guild):
        if not guild:
            return None
        return discord.utils.find(lambda c: channel_matches(c, "logs"), guild.text_channels)

    async def write(self, guild, text):
        channel = self.channel(guild)
        if channel:
            try:
                await channel.send(f"📋 {text}")
            except discord.Forbidden:
                pass

    def user_label(self, user_id):
        if not user_id:
            return "System"
        user = self.bot.get_user(int(user_id))
        return f"{user.display_name} (ID {user_id})" if user else f"User ID {user_id}"

    @commands.Cog.listener()
    async def on_financial_activity(self, from_id, to_id, amount, tx_type, note):
        text = (
            f"💰 **Financial activity** `{tx_type}` — {fmt(amount)} | "
            f"from: {self.user_label(from_id)} | to: {self.user_label(to_id)}"
            + (f" | {note}" if note else "")
        )
        for guild in self.bot.guilds:
            await self.write(guild, text)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.write(member.guild, f"🛬 **Member joined** {member.display_name} (ID {member.id})")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.write(member.guild, f"🚪 **Member left** {member.display_name} (ID {member.id})")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        old = {role.name for role in before.roles}
        new = {role.name for role in after.roles}
        if old != new:
            added = ", ".join(sorted(new - old)) or "none"
            removed = ", ".join(sorted(old - new)) or "none"
            await self.write(
                after.guild,
                f"🎭 **Roles changed** for {after.display_name}: added [{added}], removed [{removed}]",
            )

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.write(role.guild, f"🎭 **Role created**: {role.name} (ID {role.id})")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.write(role.guild, f"🗑️ **Role deleted**: {role.name} (ID {role.id})")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.write(channel.guild, f"📁 **Channel created**: {channel.name}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.write(channel.guild, f"🗑️ **Channel deleted**: {channel.name}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.write(guild, f"🔨 **Banned** {user} (ID {user.id})")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.write(guild, f"✅ **Unbanned** {user} (ID {user.id})")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        old = before.channel.name if before.channel else "none"
        new = after.channel.name if after.channel else "none"
        await self.write(
            member.guild,
            f"🔊 **Voice change** {member.display_name}: `{old}` → `{new}`",
        )


async def setup(bot):
    await bot.add_cog(ActivityLogs(bot))