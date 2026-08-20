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
                FOREIGN KEY (category_id) REFERENCES categories (id)
            )
        """)
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
            "SELECT id, title, file_id FROM books WHERE category_id = ? ORDER BY title",
            (category_id,),
        )
        return await cursor.fetchall()


async def get_book(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, title, file_id FROM books WHERE id = ?", (book_id,)
        )
        return await cursor.fetchone()


async def delete_book(book_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
        await db.commit()
