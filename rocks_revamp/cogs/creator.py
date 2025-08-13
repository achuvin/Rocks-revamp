import discord
from discord.ext import commands
from discord import app_commands
import database
import config

class CreatorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} cog has been loaded.')

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingRole):
            await interaction.response.send_message("You're not a creator to upload stuff", ephemeral=True)
        else:
            print(f"An unhandled error occurred in CreatorCog: {error}")
            if not interaction.response.is_done():
                await interaction.response.send_message("An unexpected error occurred. Please try again later.", ephemeral=True)
            else:
                await interaction.followup.send("An unexpected error occurred. Please try again later.", ephemeral=True)

    @app_commands.command(name="upd", description="Upload a new item to the shop.")
    @app_commands.describe(
        application="The application this item is for.",
        category="The category of the item.",
        name="The name of the item.",
        price="The price in coins.",
        link="The download link for the item.",
        screenshot="The main screenshot for the product.",
        screenshot_2="A second screenshot (Required for FX and Project Files).",
        screenshot_3="A third screenshot (Required for FX and Project Files)."
    )
    @app_commands.choices(
        application=[
            app_commands.Choice(name="After Effects", value="After Effects"),
            app_commands.Choice(name="Alight Motion", value="Alight Motion"),
            app_commands.Choice(name="Node", value="Node"),
            app_commands.Choice(name="Capcut", value="Capcut"),
            app_commands.Choice(name="Blurr", value="Blurr"),
        ],
        category=[
            app_commands.Choice(name="CC", value="CC"),
            app_commands.Choice(name="FX", value="FX"),
            app_commands.Choice(name="Overlays", value="Overlays"),
            app_commands.Choice(name="Project File", value="Project File"),
        ]
    )
    @app_commands.checks.has_role("Creator")
    async def upload(self, interaction: discord.Interaction, application: app_commands.Choice[str], category: app_commands.Choice[str], name: str, price: int, link: str, screenshot: discord.Attachment, screenshot_2: discord.Attachment = None, screenshot_3: discord.Attachment = None):
        if config.UPLOAD_CHANNEL_ID != 0 and interaction.channel.id != config.UPLOAD_CHANNEL_ID:
            upload_channel = self.bot.get_channel(config.UPLOAD_CHANNEL_ID)
            await interaction.response.send_message(f"You can only use this command in the {upload_channel.mention} channel.", ephemeral=True)
            return

        # Check if required screenshots are provided for specific categories
        if category.value in ["FX", "Project File"] and (not screenshot_2 or not screenshot_3):
            await interaction.response.send_message("For FX and Project Files, you must upload all three screenshots.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        if price < 0:
            await interaction.followup.send("Price must be a positive number.", ephemeral=True)
            return
        
        try:
            # Get URLs for all provided attachments, using None if they don't exist
            screenshot_url = screenshot.url
            screenshot_2_url = screenshot_2.url if screenshot_2 else None
            screenshot_3_url = screenshot_3.url if screenshot_3 else None

            await self.bot.db.add_item_to_shop(
                creator_id=interaction.user.id,
                guild_id=interaction.guild.id,
                item_name=name,
                application=application.value,
                category=category.value,
                price=price,
                product_link=link,
                screenshot_link=screenshot_url,
                screenshot_link_2=screenshot_2_url,
                screenshot_link_3=screenshot_3_url
            )
            await interaction.followup.send("The product is put into the sale successfully.", ephemeral=True)

            # --- New Item Announcement ---
            log_channel = self.bot.get_channel(config.NEW_ITEM_LOG_CHANNEL_ID)
            if log_channel:
                member_role = discord.utils.get(interaction.guild.roles, name="Members")
                mention_text = member_role.mention if member_role else "@everyone"

                embed = discord.Embed(
                    title="🚀 New Item Alert!",
                    description=f"A new item has just been added to the shop by {interaction.user.mention}!",
                    color=discord.Color.green()
                )
                embed.add_field(name="Item Name", value=name, inline=False)
                embed.add_field(name="Application", value=application.value, inline=True)
                embed.add_field(name="Category", value=category.value, inline=True)
                embed.add_field(name="Price", value=f"{price:,} coins", inline=True)
                embed.set_image(url=screenshot_url)

                # Add links to the other screenshots if they exist
                extra_images_text = []
                if screenshot_2_url:
                    extra_images_text.append(f"[Preview 2]({screenshot_2_url})")
                if screenshot_3_url:
                    extra_images_text.append(f"[Preview 3]({screenshot_3_url})")
                
                if extra_images_text:
                    embed.add_field(name="More Previews", value=" | ".join(extra_images_text), inline=False)

                embed.set_footer(text="Use /shop to browse and purchase!")
                
                await log_channel.send(content=mention_text, embed=embed)

        except Exception as e:
            print(f"Error in /upd: {e}")
            await interaction.followup.send("An error occurred while adding the item. Please check the console.", ephemeral=True)

    @app_commands.command(name="myuploads", description="View all the items you have uploaded.")
    @app_commands.checks.has_role("Creator")
    async def myuploads(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            uploads = await self.bot.db.get_creator_uploads(interaction.user.id, interaction.guild.id)
            if not uploads:
                await interaction.followup.send("You haven't uploaded any items yet.", ephemeral=True)
                return
            
            embed = discord.Embed(title="My Uploads", color=discord.Color.blue())
            for item in uploads:
                embed.add_field(
                    name=f"{item['item_name']} (ID: {item['item_id']})",
                    value=f"App: {item['application']} | Category: {item['category']} | Price: {item['price']:,} coins",
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            print(f"Error in /myuploads: {e}")
            await interaction.followup.send("An error occurred while fetching your uploads.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(CreatorCog(bot))
