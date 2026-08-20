import discord
from discord.ext import commands
import asyncio
import os
import logging
from dotenv import load_dotenv
from bot.database import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("NigeriaRP")

COGS = [
    "bot.cogs.economy",
    "bot.cogs.government",
    "bot.cogs.banking",
    "bot.cogs.business",
    "bot.cogs.jobs",
    "bot.cogs.admin",
    "bot.cogs.betting",
    "bot.cogs.prefix",
    "bot.cogs.store",
    "bot.cogs.role_income",
    "bot.cogs.slips",
    "bot.cogs.addons",
    "bot.cogs.role_setup",
    "bot.cogs.role_setup_prefix",
    "bot.cogs.setup_system",
    "bot.cogs.police",
    "bot.cogs.activity_logs",
]


class NigeriaBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            description="🇳🇬 Nigerian Government RP Economy Bot",
        )
        self.db: Database = None

    async def before_invoke(self, ctx):
        """Stop jailed citizens from using financial/gameplay prefix commands."""
        if not ctx.guild or not self.db:
            return
        record = await self.db.get_jail_record(str(ctx.guild.id), str(ctx.author.id))
        if not record:
            return
        allowed = {
            "help", "cmds", "commands", "cmdlist", "setup", "setuproles",
            "createroles", "claimvisa", "visa", "idcard", "nationalid",
            "tin", "police", "jail", "unjail", "release", "immigration-pending",
            "immigrationlist", "immigration-approve", "approveimmigration",
        }
        if ctx.command and ctx.command.name not in allowed:
            await ctx.send("🚓 You are currently jailed and cannot use economy, betting, loan, or business commands.")
            raise commands.CheckFailure("Jailed users cannot use financial commands")

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Equivalent guard for slash commands."""
        if not interaction.guild or not self.db or not interaction.command:
            return True
        record = await self.db.get_jail_record(str(interaction.guild.id), str(interaction.user.id))
        if not record:
            return True
        allowed = {
            "help", "setup", "setup-roles", "claim-visa", "register",
            "idcard", "nationalid", "tin", "police", "jail", "unjail",
            "release", "immigration-pending", "immigration-approve",
        }
        if interaction.command.name not in allowed:
            await interaction.response.send_message(
                "🚓 You are currently jailed and cannot use economy, betting, loan, or business commands.",
                ephemeral=True,
            )
            return False
        return True

    async def setup_hook(self):
        self.db = Database()
        await self.db.initialize()
        logger.info("Database initialized.")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load cog {cog}: {e}", exc_info=True)

        # Apply the jailed-user guard to every slash command as well as
        # prefix commands handled by before_invoke.
        self.tree.interaction_check = self.interaction_check
        await self.tree.sync()
        logger.info("Slash commands synced.")

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="🇳🇬 Nigerian Economy | /help",
            )
        )


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error(
            "DISCORD_TOKEN not set. Add it as a secret named DISCORD_TOKEN."
        )
        return

    bot = NigeriaBot()
    async with bot:
        await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
