"""Prefix (!) commands for the store, role income, bet settings, and slips."""
import discord
from discord.ext import commands
import asyncio

from bot.config import BET_MIN
from bot.utils import fmt, success_embed, error_embed, info_embed, is_admin


class AddonPrefix(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.command(name="store")
    async def store(self, ctx):
        items = await self.db.get_store_items()
        if not items:
            return await ctx.send(embed=info_embed("Store Empty", "No items listed yet."))
        embed = discord.Embed(title="🏪 MetroCity Store", color=0x008751)
        for i in items:
            stock = "Unlimited" if i["stock"] == -1 else i["stock"]
            embed.add_field(name=f"#{i['id']} — {i['name']} — {fmt(i['price'])}",
                            value=f"{i['description'] or 'No description'} | Stock: {stock}", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="buy")
    async def buy(self, ctx, item_id: int, quantity: int = 1):
        item = await self.db.get_store_item(item_id)
        if not item or not item["active"]:
            return await ctx.send(embed=error_embed("Item Not Found"))
        if quantity < 1 or quantity > 100:
            return await ctx.send(embed=error_embed("Invalid Quantity"))
        total = item["price"] * quantity
        user = await self.db.get_or_create_user(str(ctx.author.id), ctx.author.display_name)
        if user["wallet"] < total:
            return await ctx.send(embed=error_embed("Insufficient Funds", f"Need {fmt(total)}."))
        if item["stock"] != -1 and item["stock"] < quantity:
            return await ctx.send(embed=error_embed("Out of Stock"))
        await self.db.update_wallet(str(ctx.author.id), -total)
        await self.db.update_treasury(total)
        await self.db.purchase_store_item(item_id, str(ctx.author.id), quantity)
        await ctx.send(embed=success_embed("Purchase Complete", f"{quantity}x **{item['name']}** for {fmt(total)}."))

    @commands.command(name="storeadd")
    async def storeadd(self, ctx, name: str, price: int, stock: int = -1, *, description: str = ""):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only"))
        try:
            await self.db.create_store_item(name, description, price, stock, str(ctx.author.id))
        except Exception:
            return await ctx.send(embed=error_embed("Item Exists"))
        await ctx.send(embed=success_embed("Store Item Added", f"**{name}** — {fmt(price)}."))

    @commands.command(name="storeremove")
    async def storeremove(self, ctx, item_id: int):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only"))
        await self.db.set_store_item_active(item_id, False)
        await ctx.send(embed=success_embed("Item Removed", f"Item #{item_id} hidden."))

    @commands.command(name="roleincome")
    async def roleincome(self, ctx, interval_hours: float, income: int, *, role_name: str):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only"))
        if interval_hours <= 0 or income <= 0:
            return await ctx.send(embed=error_embed("Income and interval must be positive."))
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if role is None:
            role = await ctx.guild.create_role(name=role_name, reason="MetroCity role income setup")
        await self.db.upsert_role_income(str(ctx.guild.id), str(role.id), role.name, income, interval_hours, str(ctx.author.id))
        await ctx.send(embed=success_embed("Role Income Created",
            f"**{role.name}** receives {fmt(income)} in bank every {interval_hours:g} hours."))

    @commands.command(name="roleincomelist")
    async def roleincomelist(self, ctx):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only"))
        schedules = await self.db.get_role_income(str(ctx.guild.id))
        if not schedules:
            return await ctx.send(embed=info_embed("No Schedules"))
        embed = discord.Embed(title="💼 Role Income", color=0x008751)
        for s in schedules:
            embed.add_field(name=f"#{s['id']} {s['role_name']}",
                            value=f"{fmt(s['income'])} every {s['interval_hours']:g}h — {'ON' if s['enabled'] else 'OFF'}",
                            inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="roleincometoggle")
    async def roleincometoggle(self, ctx, schedule_id: int, enabled: bool):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only"))
        await self.db.set_role_income_enabled(schedule_id, enabled)
        await ctx.send(embed=success_embed("Schedule Updated", f"Schedule #{schedule_id}: {'ON' if enabled else 'OFF'}"))

    @commands.command(name="betmax")
    async def betmax(self, ctx, amount: int):
        if not is_admin(ctx.author):
            return await ctx.send(embed=error_embed("Admins Only"))
        if amount < BET_MIN:
            return await ctx.send(embed=error_embed("Too Low", f"Minimum is {fmt(BET_MIN)}."))
        await self.db.set_max_bet(amount)
        await ctx.send(embed=success_embed("Maximum Bet Updated", f"Maximum bet is now {fmt(amount)}."))

    @commands.command(name="slipcreate")
    async def slipcreate(self, ctx, amount: int, selections: str):
        cog = self.bot.get_cog("BettingSlips")
        if cog:
            await cog._create(ctx.author, ctx.channel, amount, selections, ctx.send)

    @commands.command(name="slipplay")
    async def slipplay(self, ctx, code: str, amount: int):
        cog = self.bot.get_cog("BettingSlips")
        slip = await self.db.get_betting_slip(code.upper())
        if not cog or not slip:
            return await ctx.send(embed=error_embed("Slip Not Found"))
        await cog._play_existing(ctx.author, ctx.channel, slip, amount, ctx.send)

    @commands.command(name="slipinfo")
    async def slipinfo(self, ctx, code: str):
        cog = self.bot.get_cog("BettingSlips")
        slip = await self.db.get_betting_slip(code.upper())
        if not cog or not slip:
            return await ctx.send(embed=error_embed("Slip Not Found"))
        await ctx.send(embed=cog._slip_embed(slip["code"], __import__("json").loads(slip["selections"]),
                                             slip["stake"], slip["potential"]))


async def setup(bot):
    await bot.add_cog(AddonPrefix(bot))