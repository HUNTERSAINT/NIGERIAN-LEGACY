"""Admin-managed virtual store and citizen purchases."""
import discord
from discord.ext import commands
from discord import app_commands

from bot.utils import fmt, success_embed, error_embed, info_embed, is_admin


class Store(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @app_commands.command(name="store", description="View the virtual Nigerian Legacy store.")
    async def store(self, interaction: discord.Interaction):
        items = await self.db.get_store_items()
        if not items:
            return await interaction.response.send_message(
                embed=info_embed("Store Empty", "An administrator has not added any items yet.")
            )
        embed = discord.Embed(title="🏪 Nigerian Legacy Store", color=0x008751)
        for item in items:
            stock = "Unlimited" if item["stock"] == -1 else str(item["stock"])
            embed.add_field(
                name=f"#{item['id']} — {item['name']} — {fmt(item['price'])}",
                value=f"{item['description'] or 'No description'}\nStock: **{stock}**",
                inline=False,
            )
        embed.set_footer(text="Use /buy <item_id> [quantity] or !buy <item_id> [quantity]")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the virtual store.")
    @app_commands.describe(item_id="Store item ID.", quantity="How many to buy.")
    async def buy(self, interaction: discord.Interaction, item_id: int, quantity: int = 1):
        await interaction.response.defer()
        if quantity < 1 or quantity > 100:
            return await interaction.followup.send(embed=error_embed("Invalid Quantity", "Choose between 1 and 100."))
        item = await self.db.get_store_item(item_id)
        if not item or not item["active"]:
            return await interaction.followup.send(embed=error_embed("Item Not Found"))
        user = await self.db.get_or_create_user(str(interaction.user.id), interaction.user.display_name)
        total = item["price"] * quantity
        if user["wallet"] < total:
            return await interaction.followup.send(
                embed=error_embed("Insufficient Wallet Funds", f"You need {fmt(total)}.")
            )
        if item["stock"] != -1 and item["stock"] < quantity:
            return await interaction.followup.send(embed=error_embed("Out of Stock"))
        await self.db.update_wallet(str(interaction.user.id), -total)
        await self.db.update_treasury(total)
        await self.db.purchase_store_item(item_id, str(interaction.user.id), quantity)
        await self.db.log_transaction(str(interaction.user.id), None, total, "store_purchase",
                                      f"{quantity}x {item['name']}")
        await interaction.followup.send(embed=success_embed(
            "Purchase Complete", f"{quantity}x **{item['name']}** purchased for **{fmt(total)}**.\n"
            "It has been added to your inventory."
        ))

    @app_commands.command(name="store-add", description="[Admin] Add or restock an item in the store.")
    @app_commands.describe(name="Item name.", price="Price in Naira.", description="Item description.",
                           stock="Stock quantity, or -1 for unlimited.")
    async def store_add(self, interaction: discord.Interaction, name: str, price: int,
                        description: str = "", stock: int = -1):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Admins Only"), ephemeral=True)
        if price <= 0 or stock < -1:
            return await interaction.response.send_message(embed=error_embed("Invalid Price or Stock"), ephemeral=True)
        try:
            await self.db.create_store_item(name, description, price, stock, str(interaction.user.id))
        except Exception:
            return await interaction.response.send_message(
                embed=error_embed("Item Exists", "Use a different name for this store item."), ephemeral=True
            )
        await interaction.response.send_message(embed=success_embed(
            "Store Item Added", f"**{name}** listed for {fmt(price)}. Stock: {'Unlimited' if stock == -1 else stock}."
        ))

    @app_commands.command(name="store-remove", description="[Admin] Hide an item from the store.")
    @app_commands.describe(item_id="Store item ID.")
    async def store_remove(self, interaction: discord.Interaction, item_id: int):
        if not is_admin(interaction.user):
            return await interaction.response.send_message(embed=error_embed("Admins Only"), ephemeral=True)
        await self.db.set_store_item_active(item_id, False)
        await interaction.response.send_message(embed=success_embed("Item Removed", f"Item #{item_id} is no longer for sale."))


async def setup(bot):
    await bot.add_cog(Store(bot))