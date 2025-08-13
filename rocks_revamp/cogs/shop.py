import discord
from discord.ext import commands
from discord import app_commands, ui
import database
import config # Import our new config file

# --- UI Views ---
# The new architecture uses interconnected views that can call each other.

# --- Forward declarations for type hinting ---
class CategorySelectView: pass
class ItemSelectView: pass
class ApplicationSelectView: pass

# View 4: Final Confirmation with "Buy Now" button.
class PurchaseView(ui.View):
    def __init__(self, bot: commands.Bot, item_id: int, application: str, category: str):
        # Set timeout to 30 seconds
        super().__init__(timeout=30)
        self.bot = bot
        self.item_id = item_id
        self.application = application
        self.category = category

    @ui.button(label="Buy Now", style=discord.ButtonStyle.green, custom_id="confirm_buy")
    async def buy_button(self, interaction: discord.Interaction, button: ui.Button):
        # Defer with thinking=True as this process involves multiple steps
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            item = await self.bot.db.get_item_details(self.item_id)
            player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)

            if not item:
                await interaction.followup.send(content="This item seems to have been removed from the shop.", ephemeral=True)
                return

            if player['balance'] < item['price']:
                await interaction.followup.send(content=f"You don't have enough coins! You need {item['price']:,} coins.", ephemeral=True)
                return

            new_balance = player['balance'] - item['price']
            await self.bot.db.update_user_data(interaction.user.id, interaction.guild.id, {"balance": new_balance})
            
            dm_embed = discord.Embed(title="✅ Purchase Successful!", description=f"DEI! Tambi! thank you for purchasing **{item['item_name']}**.", color=discord.Color.brand_green())
            dm_embed.add_field(name="Download", value=f"[Click Here]({item['product_link']})")
            await interaction.user.send(embed=dm_embed)
            
            # Send a confirmation message via followup
            await interaction.followup.send(content=f"Purchase complete! I've sent the link for **{item['item_name']}** to your DMs.", ephemeral=True)
            
            # --- ADDING LOGS ---
            try:
                # Send Fun PUBLIC Purchase Log
                public_log_channel = self.bot.get_channel(config.PURCHASE_LOG_CHANNEL_ID)
                if public_log_channel:
                    log_embed = discord.Embed(
                        title="New Purchase!",
                        description=f"**{interaction.user.mention}** just bought **{item['item_name']}**!\n\nThanks for buying the product ❤️",
                        color=discord.Color.from_str("#5865F2")
                    )
                    # Use the item's main screenshot for the public log
                    if item.get('screenshot_link'):
                        log_embed.set_image(url=item['screenshot_link'])
                    await public_log_channel.send(embed=log_embed)

                # Send Detailed PRIVATE Admin Log
                admin_log_channel = self.bot.get_channel(config.ADMIN_LOG_CHANNEL_ID)
                if admin_log_channel:
                    creator_name = f"Unknown Creator (`{item['creator_id']}`)"
                    try:
                        creator = await self.bot.fetch_user(item['creator_id'])
                        creator_name = f"{creator.name} (`{creator.id}`)"
                    except discord.NotFound:
                        print(f"Could not find creator with ID {item['creator_id']} for admin log.")
                    
                    admin_embed = discord.Embed(title="Admin Purchase Log", color=discord.Color.dark_red())
                    admin_embed.add_field(name="Buyer", value=f"{interaction.user.name} (`{interaction.user.id}`)", inline=False)
                    admin_embed.add_field(name="Item Purchased", value=f"{item['item_name']} (`{item['item_id']}`)", inline=False)
                    admin_embed.add_field(name="Creator", value=creator_name, inline=False)
                    admin_embed.add_field(name="Price", value=f"{item['price']:,} coins", inline=True)
                    admin_embed.add_field(name="Balance Before", value=f"{player['balance']:,} coins", inline=True)
                    admin_embed.add_field(name="Balance After", value=f"{new_balance:,} coins", inline=True)
                    
                    # Add all available screenshot links to the admin log
                    screenshot_links = []
                    if item.get('screenshot_link'):
                        screenshot_links.append(f"[Main]({item['screenshot_link']})")
                    if item.get('screenshot_link_2'):
                        screenshot_links.append(f"[Extra 1]({item['screenshot_link_2']})")
                    if item.get('screenshot_link_3'):
                        screenshot_links.append(f"[Extra 2]({item['screenshot_link_3']})")
                    
                    if screenshot_links:
                        admin_embed.add_field(name="Screenshots", value=" | ".join(screenshot_links), inline=False)

                    admin_embed.timestamp = discord.utils.utcnow()
                    await admin_log_channel.send(embed=admin_embed)
            except Exception as e:
                print(f"Error in post-purchase logging: {e}")

            # Edit the original message to remove buttons
            await interaction.edit_original_response(content="Purchase complete!", view=None, embed=None)

        except discord.Forbidden:
            player = await self.bot.db.get_user_data(interaction.user.id, interaction.guild.id)
            item = await self.bot.db.get_item_details(self.item_id)
            if item:
                 await self.bot.db.update_user_data(interaction.user.id, interaction.guild.id, {"balance": player['balance'] + item['price']})
            await interaction.followup.send(content="I couldn't DM you. Please enable DMs. Your purchase was refunded.", ephemeral=True)
        except Exception as e:
            print(f"Error in purchase view: {e}")
            await interaction.followup.send(content="An error occurred during purchase.", ephemeral=True)

# View 3: Shows a dropdown of items within a selected category.
class ItemSelectView(ui.View):
    def __init__(self, bot: commands.Bot, application: str, category: str):
        super().__init__(timeout=30)
        self.bot = bot
        self.application = application
        self.category = category
        self.add_item(self.ItemSelect(bot, application, category))

    class ItemSelect(ui.Select):
        def __init__(self, bot: commands.Bot, application: str, category: str):
            self.bot = bot
            self.application = application
            self.category = category
            super().__init__(placeholder="Select an item to purchase...")

        async def populate_options(self, guild_id: int):
            items = await self.bot.db.get_items_in_category(guild_id, self.application, self.category)
            self.options = [discord.SelectOption(label=f"{item['item_name']} ({item['price']:,} coins)", value=str(item['item_id'])) for item in items] or [discord.SelectOption(label="No items found", value="disabled")]

        async def callback(self, interaction: discord.Interaction):
            if self.values[0] == "disabled":
                # Acknowledge the interaction by editing the message
                await interaction.response.edit_message(content="There are no items to select in this category.")
                return

            item_id = int(self.values[0])
            item = await self.bot.db.get_item_details(item_id)
            if not item:
                await interaction.response.edit_message(content="This item could not be found.", view=None)
                return

            embed = discord.Embed(title=f"Confirm Purchase: {item['item_name']}", description=f"Are you sure you want to buy this for **{item['price']:,}** coins?", color=discord.Color.orange())
            embed.add_field(name="Application", value=item['application']).add_field(name="Category", value=item['category'])
            
            # Add the main screenshot
            if item.get('screenshot_link'):
                embed.set_image(url=item['screenshot_link'])
            
            # Add links to the other screenshots if they exist
            extra_images_text = []
            if item.get('screenshot_link_2'):
                extra_images_text.append(f"[Preview 2]({item['screenshot_link_2']})")
            if item.get('screenshot_link_3'):
                extra_images_text.append(f"[Preview 3]({item['screenshot_link_3']})")
            
            if extra_images_text:
                embed.add_field(name="More Previews", value=" | ".join(extra_images_text), inline=False)

            await interaction.response.edit_message(content=None, embed=embed, view=PurchaseView(self.bot, item_id, self.application, self.category))

# View 2: Shows a dropdown of categories within a selected application.
class CategorySelectView(ui.View):
    def __init__(self, bot: commands.Bot, application: str):
        super().__init__(timeout=30)
        self.bot = bot
        self.application = application
        self.add_item(self.CategorySelect(bot, application))

    class CategorySelect(ui.Select):
        def __init__(self, bot: commands.Bot, application: str):
            self.bot = bot
            self.application = application
            super().__init__(placeholder="Select a category...")

        async def populate_options(self, guild_id: int):
            categories = await self.bot.db.get_categories_for_app(guild_id, self.application)
            self.options = [discord.SelectOption(label=cat) for cat in categories] or [discord.SelectOption(label="No categories found", value="disabled")]
        
        async def callback(self, interaction: discord.Interaction):
            category = self.values[0]
            if category == "disabled":
                await interaction.response.edit_message(content="There are no categories to select.")
                return

            item_view = ItemSelectView(self.bot, self.application, category)
            await item_view.children[0].populate_options(interaction.guild.id)
            await interaction.response.edit_message(content=f"Showing items for **{category}**. Please select an item:", view=item_view)

# View 1: The initial view with application buttons.
class ApplicationSelectView(ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=30)
        self.bot = bot

    @ui.button(label="After Effects", style=discord.ButtonStyle.primary, row=0)
    async def ae_button(self, interaction: discord.Interaction, button: ui.Button):
        category_view = CategorySelectView(self.bot, "After Effects")
        await category_view.children[0].populate_options(interaction.guild.id)
        await interaction.response.edit_message(content="Please select a category for **After Effects**.", view=category_view)

    @ui.button(label="Alight Motion", style=discord.ButtonStyle.primary, row=0)
    async def am_button(self, interaction: discord.Interaction, button: ui.Button):
        category_view = CategorySelectView(self.bot, "Alight Motion")
        await category_view.children[0].populate_options(interaction.guild.id)
        await interaction.response.edit_message(content="Please select a category for **Alight Motion**.", view=category_view)

    @ui.button(label="Node", style=discord.ButtonStyle.primary, row=1)
    async def node_button(self, interaction: discord.Interaction, button: ui.Button):
        category_view = CategorySelectView(self.bot, "Node")
        await category_view.children[0].populate_options(interaction.guild.id)
        await interaction.response.edit_message(content="Please select a category for **Node**.", view=category_view)

    @ui.button(label="Capcut", style=discord.ButtonStyle.primary, row=1)
    async def capcut_button(self, interaction: discord.Interaction, button: ui.Button):
        category_view = CategorySelectView(self.bot, "Capcut")
        await category_view.children[0].populate_options(interaction.guild.id)
        await interaction.response.edit_message(content="Please select a category for **Capcut**.", view=category_view)

    @ui.button(label="Blurr", style=discord.ButtonStyle.primary, row=1)
    async def blurr_button(self, interaction: discord.Interaction, button: ui.Button):
        category_view = CategorySelectView(self.bot, "Blurr")
        await category_view.children[0].populate_options(interaction.guild.id)
        await interaction.response.edit_message(content="Please select a category for **Blurr**.", view=category_view)


# --- Shop Cog ---
class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{self.__class__.__name__} cog has been loaded.')

    @app_commands.command(name="shop", description="Browse and purchase items from the interactive shop.")
    async def shop(self, interaction: discord.Interaction):
        if config.SHOP_CHANNEL_ID != 0 and interaction.channel.id != config.SHOP_CHANNEL_ID:
            shop_channel = self.bot.get_channel(config.SHOP_CHANNEL_ID)
            await interaction.response.send_message(f"You can only use this command in the {shop_channel.mention} channel.", ephemeral=True)
            return

        await interaction.response.send_message("Welcome to the shop! Please select an application to browse:", view=ApplicationSelectView(self.bot), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
