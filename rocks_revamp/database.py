import sqlite3
import functools
from discord.ext import commands

# This class now manages two separate database files.
class DatabaseManager:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economy_db_path = "economy.db"
        self.shop_db_path = "shop.db"
        # Initialize both databases on startup.
        self._init_sync()

    def _run_sync(self, func, *args, **kwargs):
        """Helper to run a synchronous function in a non-blocking way."""
        partial_func = functools.partial(func, *args, **kwargs)
        return self.bot.loop.run_in_executor(None, partial_func)

    def _init_sync(self):
        """Initializes both databases."""
        # Initialize economy.db
        with sqlite3.connect(self.economy_db_path) as con:
            cur = con.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER NOT NULL, guild_id INTEGER NOT NULL,
                    balance INTEGER DEFAULT 0, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
                    last_daily TEXT, daily_streak INTEGER DEFAULT 0,
                    last_coin_claim REAL DEFAULT 0, last_xp_claim REAL DEFAULT 0,
                    daily_spam_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
        print("Economy database initialized successfully.")

        # Initialize shop.db
        with sqlite3.connect(self.shop_db_path) as con:
            cur = con.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            # Add the new screenshot_link columns
            cur.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT, creator_id INTEGER NOT NULL,
                    guild_id INTEGER NOT NULL, item_name TEXT NOT NULL, application TEXT NOT NULL,
                    category TEXT NOT NULL, price INTEGER NOT NULL, product_link TEXT NOT NULL,
                    screenshot_link TEXT,
                    screenshot_link_2 TEXT,
                    screenshot_link_3 TEXT
                )
            """)
        print("Shop database initialized successfully.")

    # --- USER ECONOMY FUNCTIONS (economy.db) ---

    def _get_user_data_sync(self, user_id: int, guild_id: int):
        with sqlite3.connect(self.economy_db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            user_data = cur.fetchone()
            if not user_data:
                cur.execute("INSERT INTO users (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id))
                con.commit()
                cur.execute("SELECT * FROM users WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
                user_data = cur.fetchone()
            return dict(user_data)

    async def get_user_data(self, user_id: int, guild_id: int):
        return await self._run_sync(self._get_user_data_sync, user_id, guild_id)

    def _update_user_data_sync(self, user_id: int, guild_id: int, data: dict):
        with sqlite3.connect(self.economy_db_path) as con:
            cur = con.cursor()
            set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
            values = list(data.values()) + [user_id, guild_id]
            query = f"UPDATE users SET {set_clause} WHERE user_id = ? AND guild_id = ?"
            cur.execute(query, tuple(values))
            con.commit()

    async def update_user_data(self, user_id: int, guild_id: int, data: dict):
        await self._run_sync(self._update_user_data_sync, user_id, guild_id, data)

    # --- SHOP ITEM FUNCTIONS (shop.db) ---

    def _add_item_to_shop_sync(self, creator_id, guild_id, item_name, application, category, price, product_link, screenshot_link, screenshot_link_2, screenshot_link_3):
        with sqlite3.connect(self.shop_db_path) as con:
            cur = con.cursor()
            cur.execute(
                "INSERT INTO items (creator_id, guild_id, item_name, application, category, price, product_link, screenshot_link, screenshot_link_2, screenshot_link_3) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (creator_id, guild_id, item_name, application, category, price, product_link, screenshot_link, screenshot_link_2, screenshot_link_3)
            )
            con.commit()

    async def add_item_to_shop(self, creator_id, guild_id, item_name, application, category, price, product_link, screenshot_link, screenshot_link_2, screenshot_link_3):
        await self._run_sync(self._add_item_to_shop_sync, creator_id, guild_id, item_name, application, category, price, product_link, screenshot_link, screenshot_link_2, screenshot_link_3)

    def _get_creator_uploads_sync(self, creator_id, guild_id):
        with sqlite3.connect(self.shop_db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM items WHERE creator_id = ? AND guild_id = ?", (creator_id, guild_id))
            return [dict(row) for row in cur.fetchall()]

    async def get_creator_uploads(self, creator_id, guild_id):
        return await self._run_sync(self._get_creator_uploads_sync, creator_id, guild_id)
    
    def _get_categories_for_app_sync(self, guild_id, application):
        with sqlite3.connect(self.shop_db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT DISTINCT category FROM items WHERE guild_id = ? AND application = ?", (guild_id, application))
            return [row['category'] for row in cur.fetchall()]

    async def get_categories_for_app(self, guild_id, application):
        return await self._run_sync(self._get_categories_for_app_sync, guild_id, application)

    def _get_items_in_category_sync(self, guild_id, application, category):
        with sqlite3.connect(self.shop_db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT item_id, item_name, price FROM items WHERE guild_id = ? AND application = ? AND category = ?", (guild_id, application, category))
            return [dict(row) for row in cur.fetchall()]

    async def get_items_in_category(self, guild_id, application, category):
        return await self._run_sync(self._get_items_in_category_sync, guild_id, application, category)

    def _get_item_details_sync(self, item_id):
        with sqlite3.connect(self.shop_db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute("SELECT * FROM items WHERE item_id = ?", (item_id,))
            item = cur.fetchone()
            return dict(item) if item else None

    async def get_item_details(self, item_id):
        return await self._run_sync(self._get_item_details_sync, item_id)

    def _update_item_details_sync(self, item_id, data):
        with sqlite3.connect(self.shop_db_path) as con:
            cur = con.cursor()
            set_clause = ", ".join([f"{key} = ?" for key in data.keys()])
            values = list(data.values()) + [item_id]
            cur.execute(f"UPDATE items SET {set_clause} WHERE item_id = ?", tuple(values))
            con.commit()

    async def update_item_details(self, item_id, data):
        await self._run_sync(self._update_item_details_sync, item_id, data)

    def _delete_item_sync(self, item_id):
        with sqlite3.connect(self.shop_db_path) as con:
            cur = con.cursor()
            cur.execute("DELETE FROM items WHERE item_id = ?", (item_id,))
            con.commit()

    async def delete_item(self, item_id):
        await self._run_sync(self._delete_item_sync, item_id)

    # --- NEW: Schema Viewer Function ---
    def _get_table_schema_sync(self, db_path, table_name):
        with sqlite3.connect(db_path) as con:
            con.row_factory = sqlite3.Row
            cur = con.cursor()
            cur.execute(f"PRAGMA table_info({table_name})")
            return [dict(row) for row in cur.fetchall()]

    async def get_shop_schema(self):
        return await self._run_sync(self._get_table_schema_sync, self.shop_db_path, "items")
