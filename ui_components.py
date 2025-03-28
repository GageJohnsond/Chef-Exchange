"""
UI components module for Stock Exchange Discord Bot
Contains all Discord UI components like buttons, views, etc.
"""
import logging
from typing import Dict, List, Any, Tuple

import discord
from discord.ui import Button, View

import config
from user_manager import UserManager
from stock_manager import StockManager

logger = logging.getLogger('stock_exchange.ui')

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
        
        # Market condition indicator - add crash warning
        market_indicator = ""
        if StockManager.market_condition == "crash":
            market_indicator = "🔥 CRASH! "
        
        # Determine color based on price (highlight danger when close to bankruptcy)
        if price <= 10:
            if price <= 5:
                # Critical range
                color = config.COLOR_ERROR
                title_prefix = f"⚠️ CRITICAL - {market_indicator}"
            else:
                # Warning range
                color = discord.Color.orange()
                title_prefix = f"⚠️ WARNING - {market_indicator}"
        else:
            # Normal range
            color = config.COLOR_INFO
            title_prefix = f"{market_indicator}"
        
        # Create embed with market condition info
        embed = discord.Embed(
            title=f"{title_prefix}{self.symbol} | Price - ${price:.2f} {config.UOM}{change_str}",
            color=color
        )
        embed.set_image(url="attachment://chart.png")
        
        # Add bankruptcy warning for stocks with low prices
        if price <= 10:
            embed.add_field(
                name="Bankruptcy Risk",
                value=(f"This stock is at risk of bankruptcy. If the price reaches $0 or below, "
                    f"the stock will be **delisted** and all shares will be **permanently lost**."),
                inline=False
            )
        
        # Add market crash warning if applicable
        if StockManager.market_condition == "crash":
            embed.add_field(
                name="🔥 MARKET CRASH WARNING",
                value="The market is currently experiencing a severe crash. All stocks are facing strong downward pressure.",
                inline=False
            )
        
        if len(price_history) > 1:
            # Add price info and market info to footer
            start_price = price_history[0]
            overall_change = ((price - start_price) / start_price) * 100
            
            embed.set_footer(
                text=f"Starting: ${start_price:.2f} | Overall: {overall_change:.1f}%"
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
                f"⚠️ {interaction.user.mention}, not enough ${config.UOM} to buy {self.symbol}.", 
                ephemeral=True
            )
            return
        
        UserManager.update_balance(user_id, -price)
        UserManager.add_item(user_id, self.symbol)
        
        # Update stock price - now tracks purchase date
        StockManager.buy_stock(self.symbol, user_id)
        
        # Add warning about same-day selling fee
        await interaction.response.send_message(
            f"✅ {interaction.user.mention} bought a share of {self.symbol} for ${price:.2f} {config.UOM}.\n"
            f"⚠️ *Note: Selling this stock today will incur a ${config.SELLING_FEE:.2f} {config.UOM} day trading fee.*", 
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
        
        # Get selling price and update stock - now includes bankruptcy_triggered flag
        base_price = StockManager.stock_prices[self.symbol]
        # Pass the bot instance to handle bankruptcy if needed
        final_price, same_day_sale, bankruptcy_triggered = await StockManager.sell_stock(
            self.symbol, user_id, interaction.client
        )
        
        # Process sale
        UserManager.update_balance(user_id, final_price)
        UserManager.remove_item(user_id, self.symbol)
        
        # Create message based on whether fee was applied
        if same_day_sale:
            fee = base_price - final_price
            message = (f"💰 {interaction.user.mention} sold a share of {self.symbol} for "
                    f"${final_price:.2f} {config.UOM} (day trading fee: ${fee:.2f}).")
        else:
            message = f"💰 {interaction.user.mention} sold a share of {self.symbol} for ${final_price:.2f} {config.UOM}."
        
        # Add bankruptcy notice if triggered
        if bankruptcy_triggered:
            message += f"\n\n⚠️ **BANKRUPTCY ALERT**: Your sale has caused {self.symbol} to go bankrupt! The stock has been delisted from the exchange."
        
        await interaction.response.send_message(message, ephemeral=True)
        
        # Only update chart if bankruptcy wasn't triggered (otherwise the chart will be deleted)
        if not bankruptcy_triggered:
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
            desc += f"{prefix}{name}: **${total:.2f} {config.UOM}**\n"
        
        if not desc:
            desc = "No users found in the database."
        
        # Create embed
        embed = discord.Embed(
            title=f"🏆 ${config.UOM} Total Worth Leaderboard",
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
        # Get all symbols and their prices from StockManager
        all_symbols = StockManager.get_all_symbols()
        stock_prices = {}
        
        for symbol in all_symbols:
            if symbol in StockManager.stock_prices:
                stock_prices[symbol] = StockManager.stock_prices[symbol]
        
        # Sort stocks by price (highest first)
        sorted_stocks = sorted(stock_prices.items(), key=lambda x: x[1], reverse=True)
        
        # Create description
        desc = ""
        for i, (symbol, price) in enumerate(sorted_stocks):
            change = ""
            if len(StockManager.price_history[symbol]) > 1:
                prev_price = StockManager.price_history[symbol][-2]
                pct_change = ((price - prev_price) / prev_price) * 100
                emoji = "📈" if pct_change >= 0 else "📉"
                change = f" {emoji} {pct_change:.1f}%"
            
            desc += f"{i+1}. {symbol}: **${price:.2f} {config.UOM}**{change}\n"
        
        if not desc:
            desc = "No active stocks found."
        
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

class HelpView(View):
    """Command help view"""
    
    def __init__(self):
        super().__init__(timeout=120)
    
    def get_embed(self):
        """Get the help embed"""
        embed = discord.Embed(
            title=f"{config.NAME} Exchange Commands",
            color=config.COLOR_INFO
        )
        
        # Add Economy commands
        embed.add_field(
            name="💰 Economy Commands",
            value=(
                f"`!balance` or `!bal` - Check your ${config.UOM} balance\n"
                "`!daily` - Claim daily reward and dividends\n"
                f"`!gift <@user> <amount>` - Gift ${config.UOM} to another user\n"
                f"`!dividends` or `!div` - Check your dividend status"
            ),
            inline=False
        )
        
        # Add Stock commands
        embed.add_field(
            name="📈 Stock Market Commands",
            value=(
                "`!portfolio` or `!port` - View your stock portfolio\n"
                f"`!rebrand <symbol>` or `!rename <symbol>` - Rebrand your stock (costs ${config.REBRAND_FEE} {config.UOM})\n"
                f"`!createstock <symbol>` or `!ipo <symbol>` - Create your own stock (costs ${config.IPO_COST} {config.UOM})\n"
                "`!decayrisk` or `!stockrisk` - Check which stocks are at risk of decay"
            ),
            inline=False
        )
        
        # Add Info commands
        embed.add_field(
            name="ℹ️ Info Commands",
            value=(
                "`!about` - About this bot\n"
                "`!help` - Show this command menu"
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
        
        # Add dividend info
        embed.add_field(
            name="💰 Dividend System",
            value=(
                f"• Top {config.TOP_SHAREHOLDERS_COUNT} shareholders in each stock receive daily dividends\n"
                f"• Stock owners earn dividends based on shares held by others\n"
                f"• Use `!dividends` to check your dividend status"
            ),
            inline=False
        )
        
        # Add decay info
        embed.add_field(
            name="📉 Stock Decay System",
            value=(
                f"• When there are more than {config.STOCK_DECAY_THRESHOLD} stocks, the least popular ones decay\n"
                f"• Decaying stocks lose value overtime. Get more investors to stay safe from decay.\n"
                f"• Use `!decayrisk` to check which stocks are at risk"
            ),
            inline=False
        )
        
        return embed