"""
UI components module for CH3F Exchange Discord Bot
Contains all Discord UI components like buttons, views, etc.
"""
import logging
from typing import Dict, List, Any, Tuple

import discord
from discord.ui import Button, View

import config
from user_manager import UserManager
from stock_manager import StockManager

logger = logging.getLogger('ch3f_exchange.ui')

class ChartView(View):
    """View for stock charts with buy/sell buttons"""
    
    def __init__(self, symbol: str):
        super().__init__(timeout=None)  # Persistent buttons
        self.symbol = symbol.upper()
        self.message = None  # Store message reference
    
    async def get_embed(self) -> Tuple[discord.File, discord.Embed]:
        """Generate the stock chart and return an updated embed"""
        buf = StockManager.generate_stock_chart(self.symbol)
        file = discord.File(buf, filename="chart.png")
        
        # Get current price and format
        price = StockManager.stock_prices[self.symbol]
        
        # Check if we have history for percent change
        price_history = StockManager.price_history[self.symbol]
        change_str = ""
        
        if len(price_history) > 1:
            prev_price = price_history[-2]
            pct_change = ((price - prev_price) / prev_price) * 100
            emoji = "📈" if pct_change >= 0 else "📉"
            change_str = f" {emoji} {pct_change:.1f}%"
        
        # Create embed with market condition info
        embed = discord.Embed(
            title=f"{self.symbol} | Price - ${price:.2f} CCD{change_str}",
            color=config.COLOR_INFO
        )
        embed.set_image(url="attachment://chart.png")
        
        # Add market condition footer
        market_emoji = {
            "bull": "📈",
            "bear": "📉",
            "volatile": "⚠️",
            "stable": "🔄"
        }.get(StockManager.market_condition, "🔄")
        
        if len(price_history) > 1:
            # Add price info and market info to footer
            start_price = price_history[0]
            overall_change = ((price - start_price) / start_price) * 100
            
            embed.set_footer(
                text=f"Starting: ${start_price:.2f} | Overall: {overall_change:.1f}% | "
                f"Market: {market_emoji} {StockManager.market_condition.upper()}"
            )
        else:
            embed.set_footer(
                text=f"Market: {market_emoji} {StockManager.market_condition.upper()}"
            )
        
        return file, embed
    
    async def update_chart(self) -> None:
        """Edit the existing message with an updated stock chart"""
        if not self.message:
            return
        
        file, embed = await self.get_embed()
        await self.message.edit(embed=embed, attachments=[file], view=self)
    
    async def buy_stock(self, interaction: discord.Interaction) -> None:
        """Handle buying a stock and update the price/history"""
        user_id = str(interaction.user.id)
        from data_manager import DataManager
        DataManager.ensure_user(user_id)
        
        price = StockManager.stock_prices[self.symbol]
        bal = UserManager.get_balance(user_id)
        
        if bal < price:
            await interaction.response.send_message(
                f"⚠️ {interaction.user.mention}, not enough $CCD to buy {self.symbol}.", 
                ephemeral=True
            )
            return
        
        UserManager.update_balance(user_id, -price)
        UserManager.add_item(user_id, self.symbol)
        
        # Update stock price - now tracks purchase date
        StockManager.buy_stock(self.symbol, user_id)
        
        # Add warning about same-day selling fee
        await interaction.response.send_message(
            f"✅ {interaction.user.mention} bought a share of {self.symbol} for ${price:.2f} CCD.\n"
            f"⚠️ *Note: Selling this stock today will incur a ${config.SELLING_FEE:.2f} CCD day trading fee.*", 
            ephemeral=True
        )
        await self.update_chart()
    
    async def sell_stock(self, interaction: discord.Interaction) -> None:
        """Handle selling a stock and update price/history"""
        user_id = str(interaction.user.id)
        from data_manager import DataManager
        DataManager.ensure_user(user_id)
        
        inv = UserManager.user_inventory(user_id)
        if self.symbol not in inv:
            await interaction.response.send_message(
                f"⚠️ {interaction.user.mention}, you do not own any shares of {self.symbol}.", 
                ephemeral=True
            )
            return
        
        # Get selling price and update stock - now includes same_day_sale flag
        base_price = StockManager.stock_prices[self.symbol]
        final_price, same_day_sale = StockManager.sell_stock(self.symbol, user_id)
        
        # Process sale
        UserManager.update_balance(user_id, final_price)
        UserManager.remove_item(user_id, self.symbol)
        
        # Create message based on whether fee was applied
        if same_day_sale:
            fee = base_price - final_price
            message = (f"💰 {interaction.user.mention} sold a share of {self.symbol} for "
                      f"${final_price:.2f} CCD (day trading fee: ${fee:.2f}).")
        else:
            message = f"💰 {interaction.user.mention} sold a share of {self.symbol} for ${final_price:.2f} CCD."
        
        await interaction.response.send_message(message, ephemeral=True)
        await self.update_chart()
    
    @discord.ui.button(label="Buy", style=discord.ButtonStyle.primary)
    async def buy_btn(self, interaction: discord.Interaction, button: Button):
        await self.buy_stock(interaction)
    
    @discord.ui.button(label="Sell", style=discord.ButtonStyle.danger)
    async def sell_btn(self, interaction: discord.Interaction, button: Button):
        await self.sell_stock(interaction)


class BalanceLeaderboardView(View):
    """View for the balance leaderboard"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.message = None
    
    def get_embed(self, guild):
        """Generate the balance leaderboard embed with portfolio values"""
        from data_manager import DataManager
        data = DataManager.load_data(config.USER_DATA_FILE)
        
        # Collect user balances and portfolio values
        user_totals = []
        for uid, udata in data.items():
            # Calculate portfolio value
            portfolio_value = 0
            inventory = udata.get("inventory", {})
            for stock, quantity in inventory.items():
                if stock in StockManager.stock_prices:
                    stock_value = StockManager.stock_prices[stock] * quantity
                    portfolio_value += stock_value
            
            # Calculate total worth (cash + portfolio)
            total_worth = udata["balance"] + portfolio_value
            
            user_totals.append((
                int(uid), 
                udata["balance"],  # Cash balance
                portfolio_value,   # Portfolio value
                total_worth        # Total worth
            ))
        
        # Sort by total worth (highest first)
        user_totals.sort(key=lambda x: x[3], reverse=True)
        
        # Create leaderboard content
        desc = ""
        rank_emoji = ["🥇", "🥈", "🥉"]
        
        # Show all users
        for i, (uid, balance, portfolio, total) in enumerate(user_totals):
            # Get member object for nickname support if guild is available
            name = f"User {uid}"
            if guild:
                member = guild.get_member(uid)
                if member:
                    name = member.display_name
            
            # Add emoji for top 3
            prefix = f"{rank_emoji[i]} " if i < 3 else f"{i+1}. "
            
            # Format with cash + portfolio = total
            desc += f"{prefix}{name}: **${total:.2f} CCD**\n"
        
        if not desc:
            desc = "No users found in the database."
        
        # Create embed
        embed = discord.Embed(
            title="🏆 $CCD Total Worth Leaderboard",
            description=desc,
            color=config.COLOR_WARNING
        )
        
        # Add timestamp
        embed.set_footer(text=f"Last updated | Cash + Portfolio = Total Worth")
        embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    async def update(self, guild):
        """Update the leaderboard message"""
        if not self.message:
            return
        
        embed = self.get_embed(guild)
        await self.message.edit(embed=embed, view=self)


class StockLeaderboardView(View):
    """View for the stock price leaderboard"""
    
    def __init__(self):
        super().__init__(timeout=None)  # Persistent view
        self.message = None
    
    def get_embed(self):
        """Generate the stock leaderboard embed"""
        # Sort stocks by price (highest first)
        sorted_stocks = sorted(StockManager.stock_prices.items(), key=lambda x: x[1], reverse=True)
        
        # Create description
        desc = ""
        for i, (symbol, price) in enumerate(sorted_stocks):
            change = ""
            if len(StockManager.price_history[symbol]) > 1:
                prev_price = StockManager.price_history[symbol][-2]
                pct_change = ((price - prev_price) / prev_price) * 100
                emoji = "📈" if pct_change >= 0 else "📉"
                change = f" {emoji} {pct_change:.1f}%"
            
            desc += f"{i+1}. {symbol}: **${price:.2f} CCD**{change}\n"
        
        # Create embed
        embed = discord.Embed(
            title="📊 Stock Price Leaderboard",
            description=desc,
            color=config.COLOR_INFO
        )
        
        # Add timestamp
        embed.set_footer(text="Last updated")
        embed.timestamp = discord.utils.utcnow()
        
        return embed
    
    async def update(self):
        """Update the leaderboard message"""
        if not self.message:
            return
        
        embed = self.get_embed()
        await self.message.edit(embed=embed, view=self)

class WhatView(View):
    """Command help view"""
    
    def __init__(self):
        super().__init__(timeout=120)
    
    def get_embed(self):
        """Get the help embed"""
        embed = discord.Embed(
            title="CH3F Exchange Commands",
            color=config.COLOR_INFO
        )
        
        # Add Economy commands
        embed.add_field(
            name="💰 Economy Commands",
            value=(
                "`!balance` or `!bal` - Check your $CCD balance\n"
                "`!daily` - Claim daily reward\n"
                "`!gift <@user> <amount>` - Gift $CCD to another user"
            ),
            inline=False
        )
        
        # Add Stock commands
        embed.add_field(
            name="📈 Stock Market Commands",
            value=(
                "`!mystocks` or `!portfolio` - View your stock portfolio\n"
                "`!stock <symbol>` - Check a specific stock"
            ),
            inline=False
        )
        
        # Add Info commands
        embed.add_field(
            name="ℹ️ Info Commands",
            value=(
                "`!about` - About this bot\n"
                "`!what` - Show this command menu"
            ),
            inline=False
        )
        
        # Add info about leaderboards
        channel_id = config.LEADERBOARD_CHANNEL_ID
        embed.add_field(
            name="📊 Leaderboards",
            value=f"Check out <#{channel_id}> for live leaderboards!",
            inline=False
        )
        
        return embed