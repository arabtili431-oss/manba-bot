import aiosqlite
from config import DB_PATH


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                download_count INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                joined_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await db.commit()

    # Eski bazalarda "books" jadvalida download_count ustuni bo'lmasligi mumkin
    # va "users" jadvalida joined_at ustuni bo'lmasligi mumkin - shularni moslashtirish
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(books)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "download_count" not in columns:
            await db.execute(
                "ALTER TABLE books ADD COLUMN download_count INTEGER NOT NULL DEFAULT 0"
            )
            await db.commit()

        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "joined_at" not in columns:
            await db.execute(
                "ALTER TABLE users ADD COLUMN joined_at TEXT DEFAULT CURRENT_TIMESTAMP"
            )
            await db.commit()


# ---------- CATEGORIES ----------

async def add_category(name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        await db.commit()


async def get_categories():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT id, name FROM categories ORDER BY name")
        return await cursor.fetchall()


async def get_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, name FROM categories WHERE id = ?", (category_id,)
        )
        return await cursor.fetchone()


async def update_category_name(category_id: int, name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE categories SET name = ? WHERE id = ?", (name, category_id)
        )
        await db.commit()


async def delete_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM books WHERE category_id = ?", (category_id,))
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()


# ---------- BOOKS ----------

async def add_book(category_id: int, title: str, file_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO books (category_id, title, file_id) VALUES (?, ?, ?)",
            (category_id, title, file_id),
        )
        await db.commit()


async def get_books_by_category(category_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, file_id, download_count FROM books "
            "WHERE category_id = ? ORDER BY title",
            (category_id,),
        )
        return await cursor.fetchall()


async def get_book(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, file_id, download_count FROM books WHERE id = ?",
            (book_id,),
        )
        return await cursor.fetchone()


async def update_book_title(book_id: int, title: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE books SET title = ? WHERE id = ?", (title, book_id)
        )
        await db.commit()


async def delete_book(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        await db.commit()


async def increment_download_count(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE books SET download_count = download_count + 1 WHERE id = ?",
            (book_id,),
        )
        await db.commit()


async def search_books(query: str, limit: int = 30):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, file_id, download_count FROM books "
            "WHERE title LIKE ? ORDER BY title LIMIT ?",
            (f"%{query}%", limit),
        )
        return await cursor.fetchall()


async def get_top_books(limit: int = 10):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT title, download_count FROM books "
            "WHERE download_count > 0 ORDER BY download_count DESC LIMIT ?",
            (limit,),
        )
        return await cursor.fetchall()


async def get_book_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM books")
        row = await cursor.fetchone()
        return row[0]


async def get_total_downloads():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COALESCE(SUM(download_count), 0) FROM books")
        row = await cursor.fetchone()
        return row[0]


# ---------- USERS ----------

async def add_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        await db.commit()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT user_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]


async def get_user_count():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        row = await cursor.fetchone()
        return row[0]


async def get_new_users_today():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM users WHERE date(joined_at) = date('now')"
        )
        row = await cursor.fetchone()
        return row[0]


# ---------- SETTINGS (force-subscribe kanal va boshqalar uchun) ----------

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await db.commit()


async def get_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else None


async def delete_setting(key: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM settings WHERE key = ?", (key,))
        await db.commit()
