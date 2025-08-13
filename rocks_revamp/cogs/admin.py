import discord
from discord.ext import commands
from discord import app_commands
import config # Import the config file

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} cog has been loaded.')

    # Custom error handler for this cog
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            # Send a specific message if the user is missing the "Admin" role
            await interaction.response.send_message("This command is for Admins only.", ephemeral=True)
        else:
            print(f"An unhandled error occurred in AdminCog: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
            else:
                await interaction.followup.send("An unexpected error occurred.", ephemeral=True)

    @app_commands.command(name="givecoins", description="[Admin] Give coins to a user.")
    @app_commands.checks.has_role("Admin")
    async def givecoins(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await interaction.response.defer(ephemeral=True)
        if amount <= 0:
            await interaction.followup.send("Amount must be positive.", ephemeral=True)
            return
        
        try:    
            player = await self.bot.db.get_user_data(user.id, interaction.guild.id)
            new_balance = player['balance'] + amount
            await self.bot.db.update_user_data(user.id, interaction.guild.id, {"balance": new_balance})
            await interaction.followup.send(f"Gave {amount:,} coins to {user.mention}. Their new balance is {new_balance:,}.", ephemeral=True)
        except Exception as e:
            print(f"Error in /givecoins: {e}")
            await interaction.followup.send("An error occurred while giving coins.", ephemeral=True)

    @app_commands.command(name="removecoins", description="[Admin] Remove coins from a user.")
    @app_commands.checks.has_role("Admin")
    async def removecoins(self, interaction: discord.Interaction, user: discord.User, amount: int):
        await interaction.response.defer(ephemeral=True)
        if amount <= 0:
            await interaction.followup.send("Amount must be positive.", ephemeral=True)
            return

        try:
            player = await self.bot.db.get_user_data(user.id, interaction.guild.id)
            new_balance = max(0, player['balance'] - amount)
            await self.bot.db.update_user_data(user.id, interaction.guild.id, {"balance": new_balance})
            await interaction.followup.send(f"Removed {amount:,} coins from {user.mention}. Their new balance is {new_balance:,}.", ephemeral=True)
        except Exception as e:
            print(f"Error in /removecoins: {e}")
            await interaction.followup.send("An error occurred while removing coins.", ephemeral=True)

    @app_commands.command(name="setprice", description="[Admin] Set a new price for an item.")
    @app_commands.checks.has_role("Admin")
    async def setprice(self, interaction: discord.Interaction, item_id: int, new_price: int):
        await interaction.response.defer(ephemeral=True)
        if new_price < 0:
            await interaction.followup.send("Price cannot be negative.", ephemeral=True)
            return
        
        try:    
            await self.bot.db.update_item_details(item_id, {"price": new_price})
            await interaction.followup.send(f"Updated price for item ID `{item_id}` to **{new_price:,}** coins.", ephemeral=True)
        except Exception as e:
            print(f"Error in /setprice: {e}")
            await interaction.followup.send("An error occurred while setting the price.", ephemeral=True)

    @app_commands.command(name="removeitem", description="[Admin] Remove an item from the shop.")
    @app_commands.checks.has_role("Admin")
    async def removeitem(self, interaction: discord.Interaction, item_id: int):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.bot.db.delete_item(item_id)
            await interaction.followup.send(f"Successfully removed item ID `{item_id}` from the shop.", ephemeral=True)
        except Exception as e:
            print(f"Error in /removeitem: {e}")
            await interaction.followup.send("An error occurred while removing the item.", ephemeral=True)

    @app_commands.command(name="database", description="[Admin] View the structure of the shop database.")
    @app_commands.checks.has_role("Admin")
    async def database(self, interaction: discord.Interaction):
        # Add the channel check
        if config.DATABASE_VIEW_CHANNEL_ID != 0 and interaction.channel.id != config.DATABASE_VIEW_CHANNEL_ID:
            channel = self.bot.get_channel(config.DATABASE_VIEW_CHANNEL_ID)
            await interaction.response.send_message(f"You can only use this command in the {channel.mention} channel.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            schema = await self.bot.db.get_shop_schema()
            
            embed = discord.Embed(
                title="Shop Database Schema (`items` table)",
                color=discord.Color.dark_grey()
            )
            
            description = "```\n"
            for column in schema:
                description += f"Column: {column['name']}\n"
                description += f"  Type: {column['type']}\n"
                description += f"  Not Null: {'Yes' if column['notnull'] else 'No'}\n"
                description += f"  Primary Key: {'Yes' if column['pk'] else 'No'}\n\n"
            description += "```"
            
            embed.description = description
            await interaction.followup.send(embed=embed)

        except Exception as e:
            print(f"Error in /database command: {e}")
            await interaction.followup.send("An error occurred while fetching the database schema.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
