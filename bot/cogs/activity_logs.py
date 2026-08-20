"""General server activity logger for the private general-logs channel."""
import discord
from discord.ext import commands


LOG_CHANNELS = {"general-logs", "metrocity-logs"}


class ActivityLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def channel(self, guild):
        return discord.utils.find(
            lambda c: c.name == "general-logs", guild.text_channels
        ) or discord.utils.find(
            lambda c: c.name == "metrocity-logs", guild.text_channels
        )

    async def write(self, guild, text):
        channel = self.channel(guild)
        if channel:
            try:
                await channel.send(f"📋 {text}")
            except discord.Forbidden:
                pass

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.channel.name in LOG_CHANNELS:
            return
        content = message.content[:500] if message.content else "[no text]"
        await self.write(message.guild, f"💬 **Message** {message.author.mention} in {message.channel.mention}: {content}")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or before.channel.name in LOG_CHANNELS:
            return
        await self.write(before.guild, f"✏️ **Edited** by {before.author.mention} in {before.channel.mention}: `{before.content[:300]}` → `{after.content[:300]}`")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or message.channel.name in LOG_CHANNELS:
            return
        await self.write(message.guild, f"🗑️ **Deleted** from {message.channel.mention} by {message.author}: {message.content[:400]}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.write(member.guild, f"🛬 **Joined** {member} (`{member.id}`)")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self.write(member.guild, f"🚪 **Left** {member} (`{member.id}`)")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        old = {role.name for role in before.roles}
        new = {role.name for role in after.roles}
        if old != new:
            added = ", ".join(sorted(new - old)) or "none"
            removed = ", ".join(sorted(old - new)) or "none"
            await self.write(after.guild, f"🎭 **Roles changed** for {after}: added [{added}], removed [{removed}]")

    @commands.Cog.listener()
    async def on_guild_role_create(self, role):
        await self.write(role.guild, f"🎭 **Role created**: {role.name} (`{role.id}`)")

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        await self.write(role.guild, f"🗑️ **Role deleted**: {role.name} (`{role.id}`)")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        await self.write(channel.guild, f"📁 **Channel created**: {channel.name}")

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        await self.write(channel.guild, f"🗑️ **Channel deleted**: {channel.name}")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await self.write(guild, f"🔨 **Banned** {user} (`{user.id}`)")

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await self.write(guild, f"✅ **Unbanned** {user} (`{user.id}`)")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel:
            return
        old = before.channel.name if before.channel else "none"
        new = after.channel.name if after.channel else "none"
        await self.write(member.guild, f"🔊 **Voice change** {member}: `{old}` → `{new}`")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction, user):
        if user.bot:
            return
        await self.write(reaction.message.guild, f"😀 **Reaction added** by {user} in {reaction.message.channel.mention}: {reaction.emoji}")

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction, user):
        if user.bot:
            return
        await self.write(reaction.message.guild, f"↩️ **Reaction removed** by {user} in {reaction.message.channel.mention}: {reaction.emoji}")

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        await self.write(ctx.guild, f"⚙️ **Prefix command** `{ctx.message.content[:200]}` by {ctx.author}")

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction, command):
        await self.write(interaction.guild, f"⚙️ **Slash command** `/{command.qualified_name}` by {interaction.user}")


async def setup(bot):
    await bot.add_cog(ActivityLogs(bot))