"""Private support tickets with an administrator-controlled panel."""
import re

import discord
from discord import app_commands
from discord.ext import commands

from bot.utils import error_embed, success_embed, is_admin

TICKET_CATEGORY = "SUPPORT"


class TicketCloseView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Close ticket", style=discord.ButtonStyle.danger)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Admins Only", "Only an administrator can close tickets."),
                ephemeral=True,
            )
        await interaction.response.send_message("Closing this ticket.")
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


class TicketPanelView(discord.ui.View):
    def __init__(self, cog):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Open a ticket", style=discord.ButtonStyle.primary, emoji="🎫")
    async def open(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.cog.open_ticket(
            interaction.guild, interaction.user, "General support", interaction.followup.send
        )


class Tickets(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def existing_ticket(self, guild, user_id):
        return discord.utils.find(
            lambda c: c.name == f"ticket-{user_id}", guild.text_channels
        )

    async def support_role(self, guild):
        row = await self.bot.db.get_support_role(str(guild.id))
        return guild.get_role(int(row["role_id"])) if row and row["role_id"] else None

    async def create_ticket(self, guild, user, subject):
        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY)
        if category is None:
            category = await guild.create_category(
                TICKET_CATEGORY, reason="Nigerian Legacy RP support tickets"
            )
        everyone = guild.default_role
        overwrites = {
            everyone: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
        }
        role = await self.support_role(guild)
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True, read_message_history=True
            )
        return await guild.create_text_channel(
            f"ticket-{user.id}", category=category, overwrites=overwrites,
            topic=f"Support ticket for {user.display_name}: {subject[:900]}",
            reason="Nigerian Legacy RP support ticket",
        )

    async def open_ticket(self, guild, user, subject, send):
        subject = re.sub(r"\s+", " ", subject or "General support").strip()[:900]
        existing = self.existing_ticket(guild, user.id)
        if existing:
            return await send(embed=success_embed(
                "Support Ticket", f"Your existing ticket is open in **{existing.name}**."
            ))
        try:
            channel = await self.create_ticket(guild, user, subject)
        except discord.Forbidden:
            return await send(embed=error_embed(
                "Ticket Unavailable", "The bot needs Manage Channels and Manage Permissions."
            ))
        await channel.send(
            f"Support ticket opened for {user.display_name}.\nSubject: {subject}\n"
            "Only administrators can close tickets.",
            view=TicketCloseView(self),
            allowed_mentions=discord.AllowedMentions.none(),
        )
        role = await self.support_role(guild)
        if role:
            await channel.send(
                f"{role.mention} Support staff have been notified.",
                allowed_mentions=discord.AllowedMentions(roles=True),
            )
        await send(embed=success_embed("Support Ticket", f"Your private ticket is open in **{channel.name}**."))

    @app_commands.command(name="ticket", description="Open a private support ticket.")
    @app_commands.describe(subject="Briefly describe what you need help with.")
    async def ticket_slash(self, interaction: discord.Interaction, subject: str = "General support"):
        if not interaction.guild:
            return await interaction.response.send_message(
                embed=error_embed("Server Only", "Tickets can only be opened inside this server."),
                ephemeral=True,
            )
        await interaction.response.defer(ephemeral=True)
        await self.open_ticket(interaction.guild, interaction.user, subject, interaction.followup.send)

    @app_commands.command(name="ticket-close", description="[Admin] Close the current support ticket.")
    async def ticket_close_slash(self, interaction: discord.Interaction):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Admins Only", "Only an administrator can close tickets."),
                ephemeral=True,
            )
        if not interaction.channel or not interaction.channel.name.startswith("ticket-"):
            return await interaction.response.send_message(
                embed=error_embed("Not a Ticket", "Use this command inside a ticket channel."),
                ephemeral=True,
            )
        await interaction.response.send_message("Closing this ticket.")
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")

    @app_commands.command(name="ticket-role", description="[Admin] Configure the support role.")
    @app_commands.describe(role="Role that can see and receive ticket notifications.")
    async def ticket_role(self, interaction: discord.Interaction, role: discord.Role):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(
                embed=error_embed("Admins Only", "Server Administrators only."), ephemeral=True
            )
        await self.bot.db.set_support_role(str(interaction.guild.id), str(role.id))
        await interaction.response.send_message(
            embed=success_embed("Support Role Set", f"New tickets will include the **{role.name}** role.")
        )

    @commands.command(name="ticket")
    @commands.guild_only()
    async def ticket_prefix(self, ctx, *, subject="General support"):
        await self.open_ticket(ctx.guild, ctx.author, subject, ctx.send)

    @commands.command(name="ticketclose")
    @commands.guild_only()
    async def ticket_close_prefix(self, ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Only an administrator can close tickets."))
        if not ctx.channel.name.startswith("ticket-"):
            return await ctx.send(embed=error_embed("Not a Ticket", "Use this inside a ticket channel."))
        await ctx.send("Closing this ticket.")
        await ctx.channel.delete(reason=f"Ticket closed by {ctx.author}")

    @commands.command(name="ticketrole")
    @commands.guild_only()
    async def ticket_role_prefix(self, ctx, role: discord.Role):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Server Administrators only."))
        await self.bot.db.set_support_role(str(ctx.guild.id), str(role.id))
        await ctx.send(embed=success_embed("Support Role Set", f"New tickets will include the **{role.name}** role."))

    @commands.command(name="panel")
    @commands.guild_only()
    async def panel(self, ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only", "Only an administrator can publish the ticket panel."))
        embed = discord.Embed(
            title="🎫 Nigerian Legacy Support",
            description="Need help? Click the button below to open a private support ticket.",
            color=0x008751,
        )
        await ctx.send(embed=embed, view=TicketPanelView(self))


async def setup(bot):
    await bot.add_cog(Tickets(bot))