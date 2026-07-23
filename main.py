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
