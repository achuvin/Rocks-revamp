import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta

def calculate_luck(streak: int) -> float:
    return min(1 + (0.5 * (streak / 7)), 10.0)

# A list of messages for when a user spams the /daily command
SPAM_MESSAGES = [
    "You have already claimed your daily reward today. Come back tomorrow!", # 1st try
    "Hey, I already told you. Once per day.", # 2nd try
    "Seriously? T-o-m-o-r-r-o-w.", # 3rd try
    "Are you even listening? Stop it.", # 4th try
    "Okay, that's it. Don't make me warn you again.", # 5th try (sends DM)
    "You're really pushing your luck.", # 6th try
    "This is getting annoying.", # 7th try
    "....", # 8th try
    "Wammala, from the begininng im seeing you spamming /daily, wammala ill smack your face hmph" # 9th try
]

class StreaksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} cog has been loaded.')

    @app_commands.command(name="daily", description="Claim your daily reward.")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
            today = datetime.now().date()
            last_daily_str = player.get('last_daily')
            
            # --- NEW: Spam Handling Logic ---
            if last_daily_str and datetime.strptime(last_daily_str, '%Y-%m-%d').date() == today:
                spam_count = player.get('daily_spam_count', 0)

                # If they have spammed 10 or more times, ignore them.
                if spam_count >= 9:
                    # We don't send a message, just ignore the command.
                    return

                # Get the correct message from the list
                message_to_send = SPAM_MESSAGES[spam_count]
                await interaction.followup.send(message_to_send, ephemeral=True)

                # If it's the 5th time, send a DM
                if spam_count == 4: # List index is 4, which is the 5th message
                    try:
                        await interaction.user.send("Stop spamming the daily command.")
                    except discord.Forbidden:
                        pass # Can't send DMs, just continue

                # Increment the spam count for next time
                await self.bot.db.update_user_data(interaction.user.id, interaction.guild.id, {"daily_spam_count": spam_count + 1})
                return

            # --- Original Daily Claim Logic ---
            new_streak = player['daily_streak'] + 1 if last_daily_str and datetime.strptime(last_daily_str, '%Y-%m-%d').date() == today - timedelta(days=1) else 1
            
            level_bonus = (player['level'] // 50) * 50
            total_reward = min(50 + level_bonus, 500)
            
            new_balance = player['balance'] + total_reward
            
            # When they successfully claim, reset their spam count.
            await self.bot.db.update_user_data(interaction.user.id, interaction.guild.id, {
                "balance": new_balance,
                "daily_streak": new_streak,
                "last_daily": today.strftime('%Y-%m-%d'),
                "daily_spam_count": 0 
            })
            
            embed = discord.Embed(title="✅ Daily Reward Claimed!", description=f"You received **{total_reward:,}** coins!", color=discord.Color.green())
            embed.add_field(name="New Balance", value=f"{new_balance:,} coins").add_field(name="Current Streak", value=f"🔥 {new_streak} days")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"Error in /daily: {e}")
            await interaction.followup.send("An error occurred while claiming your daily reward.", ephemeral=True)

    @app_commands.command(name="streak", description="Check your current daily streak.")
    async def streak(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
        await interaction.followup.send(f"🔥 Your current daily streak is **{player['daily_streak']}** days.")

    @app_commands.command(name="luck", description="Check your current luck boost from your streak.")
    async def luck(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
        luck = calculate_luck(player['daily_streak'])
        embed = discord.Embed(title="✨ Your Luck Stats", description=f"Your luck multiplier is **{luck:.2f}x** based on your **{player['daily_streak']}-day** streak.", color=discord.Color.purple())
        embed.set_footer(text="This boosts your chances of high-tier chat rewards.")
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(StreaksCog(bot))
