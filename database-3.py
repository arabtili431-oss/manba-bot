import asyncpg
from config import DATABASE_URL

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    return _pool


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id SERIAL PRIMARY KEY,
                category_id INTEGER NOT NULL REFERENCES categories(id),
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                download_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                joined_at TIMESTAMP NOT NULL DEFAULT now()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)


# ---------- CATEGORIES ----------

async def add_category(name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO categories (name) VALUES ($1)", name)


async def get_categories():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name FROM categories ORDER BY name")
        return [(row["id"], row["name"]) for row in rows]


async def get_category(category_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, name FROM categories WHERE id = $1", category_id
        )
        return (row["id"], row["name"]) if row else None


async def update_category_name(category_id: int, name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE categories SET name = $1 WHERE id = $2", name, category_id
        )


async def delete_category(category_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM books WHERE category_id = $1", category_id)
        await conn.execute("DELETE FROM categories WHERE id = $1", category_id)


# ---------- BOOKS ----------

async def add_book(category_id: int, title: str, file_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO books (category_id, title, file_id) VALUES ($1, $2, $3)",
            category_id, title, file_id,
        )


async def get_books_by_category(category_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, file_id, download_count FROM books "
            "WHERE category_id = $1 ORDER BY title",
            category_id,
        )
        return [(r["id"], r["title"], r["file_id"], r["download_count"]) for r in rows]


async def get_book(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, title, file_id, download_count FROM books WHERE id = $1",
            book_id,
        )
        if not row:
            return None
        return (row["id"], row["title"], row["file_id"], row["download_count"])


async def update_book_title(book_id: int, title: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE books SET title = $1 WHERE id = $2", title, book_id)


async def delete_book(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM books WHERE id = $1", book_id)


async def increment_download_count(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE books SET download_count = download_count + 1 WHERE id = $1",
            book_id,
        )


async def search_books(query: str, limit: int = 30):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, file_id, download_count FROM books "
            "WHERE title ILIKE $1 ORDER BY title LIMIT $2",
            f"%{query}%", limit,
        )
        return [(r["id"], r["title"], r["file_id"], r["download_count"]) for r in rows]


async def get_top_books(limit: int = 10):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT title, download_count FROM books "
            "WHERE download_count > 0 ORDER BY download_count DESC LIMIT $1",
            limit,
        )
        return [(r["title"], r["download_count"]) for r in rows]


async def get_book_count():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM books")


async def get_total_downloads():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COALESCE(SUM(download_count), 0) FROM books")
        return result


# ---------- USERS ----------

async def add_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
            user_id,
        )


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users")
        return [row["user_id"] for row in rows]


async def get_user_count():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def get_new_users_today():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE joined_at::date = CURRENT_DATE"
        )


# ---------- SETTINGS (force-subscribe kanal va boshqalar uchun) ----------

async def set_setting(key: str, value: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            key, value,
        )


async def get_setting(key: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)


async def delete_setting(key: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM settings WHERE key = $1", key)


# ---------- BACKUP / EXPORT ----------

async def export_all_data():
    pool = await get_pool()
    async with pool.acquire() as conn:
        categories = await conn.fetch("SELECT id, name FROM categories ORDER BY id")
        books = await conn.fetch(
            "SELECT id, category_id, title, file_id, download_count FROM books ORDER BY id"
        )
        users = await conn.fetch("SELECT user_id FROM users")
        settings = await conn.fetch("SELECT key, value FROM settings")

    return {
        "categories": [dict(r) for r in categories],
        "books": [dict(r) for r in books],
        "users": [r["user_id"] for r in users],
        "settings": {r["key"]: r["value"] for r in settings},
    }
