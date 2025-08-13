import discord
from discord.ext import commands
from discord import app_commands
import time
import random

def calculate_luck(streak: int) -> float:
    """Calculates the luck multiplier based on the daily streak."""
    luck_multiplier = 1 + (0.5 * (streak / 7))
    return min(luck_multiplier, 10.0)

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} cog has been loaded.')

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore slash command interactions, bots, and DMs
        if message.interaction is not None or message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        current_time = time.time()
        
        try:
            player = await self.bot.db.get_user_data(user_id, guild_id)
            
            # This dictionary will hold all the data we need to update in a single database call.
            data_to_update = {}
            
            # --- COIN REWARD LOGIC ---
            if current_time - player['last_coin_claim'] > 25:
                luck_multiplier = calculate_luck(player['daily_streak'])
                max_coins = 20 + (player['level'] * 5)
                low_tier_cap = int(max_coins * 0.80)
                high_tier_chance = min(0.05 * luck_multiplier, 1.0)
                
                coins_earned = random.randint(low_tier_cap + 1, max_coins) if random.random() < high_tier_chance else random.randint(1, low_tier_cap)
                
                data_to_update['balance'] = player['balance'] + coins_earned
                data_to_update['last_coin_claim'] = current_time
                print(f"{message.author.name} earned {coins_earned} coins.")

            # --- XP REWARD LOGIC ---
            if current_time - player['last_xp_claim'] > 20:
                luck_multiplier = calculate_luck(player['daily_streak'])
                max_xp = 25 + (player['level'] * 5)
                low_tier_cap = int(max_xp * 0.80)
                high_tier_chance = min(0.20 * luck_multiplier, 1.0)

                xp_earned = random.randint(low_tier_cap + 1, max_xp) if random.random() < high_tier_chance else random.randint(1, low_tier_cap)
                
                new_xp = player['xp'] + xp_earned
                xp_needed = 100 + (player['level'] * 50)
                
                if new_xp >= xp_needed:
                    new_level = player['level'] + 1
                    xp_after_levelup = new_xp - xp_needed
                    data_to_update['xp'] = xp_after_levelup
                    data_to_update['level'] = new_level
                    await message.channel.send(f"🎉 Congratulations {message.author.mention}, you have reached **Level {new_level}**!")
                else:
                    data_to_update['xp'] = new_xp
                
                data_to_update['last_xp_claim'] = current_time
                print(f"{message.author.name} gained {xp_earned} XP.")

            # --- SINGLE DATABASE UPDATE ---
            # If there's anything to update, do it all at once.
            if data_to_update:
                await self.bot.db.update_user_data(user_id, guild_id, data_to_update)

        except Exception as e:
            print(f"Error in on_message economy processing for {message.author.name}: {e}")

    @app_commands.command(name="balance", description="Check your current coin balance.")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
        embed = discord.Embed(
            title="💰 Your Balance",
            description=f"You currently have **{player['balance']:,}** coins.",
            color=discord.Color.gold()
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="lvl", description="Check your current level and XP.")
    async def lvl(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
        level, xp = player['level'], player['xp']
        xp_needed = 100 + (level * 50)
        
        embed = discord.Embed(title="📈 Your Level", color=discord.Color.blue())
        embed.add_field(name="Level", value=f"**{level}**", inline=True)
        embed.add_field(name="XP", value=f"**{xp:,} / {xp_needed:,}**", inline=True)
        
        progress = min(xp / xp_needed, 1.0)
        bar = '🟩' * int(20 * progress) + '⬛' * (20 - int(20 * progress))
        embed.add_field(name="Progress", value=f"`{bar}`", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="droprates", description="View your current drop rates for coins and XP.")
    async def droprates(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
            
            # --- Calculations ---
            level = player['level']
            streak = player['daily_streak']
            
            luck_multiplier = calculate_luck(streak)
            
            # Coin calculations
            max_coins = 20 + (level * 5)
            base_high_tier_chance_coin = 0.05 # 5%
            final_high_tier_chance_coin = min(base_high_tier_chance_coin * luck_multiplier, 1.0)

            # XP calculations
            max_xp = 25 + (level * 5)
            base_high_tier_chance_xp = 0.20 # 20%
            final_high_tier_chance_xp = min(base_high_tier_chance_xp * luck_multiplier, 1.0)
            
            # --- Create Embed ---
            embed = discord.Embed(
                title="💧 Your Drop Rates",
                description=f"Your rewards are based on your **Level {level}** and **{luck_multiplier:.2f}x Luck Multiplier**.",
                color=discord.Color.teal()
            )
            
            embed.add_field(
                name="💰 Coin Drops",
                value=f"**Range:** 1 - {max_coins} coins\n"
                      f"**High-Tier Chance:** {final_high_tier_chance_coin:.1%}",
                inline=True
            )
            
            embed.add_field(
                name="📈 XP Gains",
                value=f"**Range:** 1 - {max_xp} XP\n"
                      f"**High-Tier Chance:** {final_high_tier_chance_xp:.1%}",
                inline=True
            )
            
            embed.set_footer(text="Increase your level and daily streak to improve your rewards!")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"Error in /droprates command: {e}")
            await interaction.followup.send("An error occurred while fetching your drop rates.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCog(bot))
