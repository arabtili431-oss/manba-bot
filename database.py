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
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                file_id TEXT NOT NULL,
                photo_id TEXT DEFAULT NULL,
                description TEXT DEFAULT NULL,
                download_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                joined_at TIMESTAMP NOT NULL DEFAULT now(),
                is_banned BOOLEAN DEFAULT FALSE
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id BIGINT NOT NULL,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, book_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                user_id BIGINT NOT NULL,
                book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
                PRIMARY KEY (user_id, book_id)
            )
        """)

        # MAVJUD BAZANI AVTOMATIK YANGILASH (MIGRATION)
        await conn.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_banned BOOLEAN DEFAULT FALSE")
        await conn.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS photo_id TEXT DEFAULT NULL")
        await conn.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS description TEXT DEFAULT NULL")


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


async def delete_category(category_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM categories WHERE id = $1", category_id)


# ---------- BOOKS ----------

async def add_book(category_id: int, title: str, file_id: str, photo_id: str = None, description: str = None):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO books (category_id, title, file_id, photo_id, description) VALUES ($1, $2, $3, $4, $5)",
            category_id, title, file_id, photo_id, description,
        )


async def get_books_by_category(category_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, file_id, photo_id, description, download_count FROM books "
            "WHERE category_id = $1 ORDER BY title",
            category_id,
        )
        return [dict(r) for r in rows]


async def get_book(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, title, file_id, photo_id, description, download_count FROM books WHERE id = $1",
            book_id,
        )
        return dict(row) if row else None


async def delete_book(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM books WHERE id = $1", book_id)


async def increment_download_count(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE books SET download_count = download_count + 1 WHERE id = $1", book_id)


async def search_books(query: str, limit: int = 30):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, title, file_id, photo_id, description, download_count FROM books "
            "WHERE title ILIKE $1 ORDER BY title LIMIT $2",
            f"%{query}%", limit,
        )
        return [dict(r) for r in rows]


# ---------- FAVORITES & RATINGS ----------

async def toggle_favorite(user_id: int, book_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval(
            "SELECT 1 FROM favorites WHERE user_id = $1 AND book_id = $2", user_id, book_id
        )
        if exists:
            await conn.execute("DELETE FROM favorites WHERE user_id = $1 AND book_id = $2", user_id, book_id)
            return False
        else:
            await conn.execute("INSERT INTO favorites (user_id, book_id) VALUES ($1, $2)", user_id, book_id)
            return True


async def is_favorite(user_id: int, book_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return bool(await conn.fetchval(
            "SELECT 1 FROM favorites WHERE user_id = $1 AND book_id = $2", user_id, book_id
        ))


async def get_user_favorites(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT b.id, b.title FROM favorites f JOIN books b ON f.book_id = b.id WHERE f.user_id = $1",
            user_id
        )
        return [(r["id"], r["title"]) for r in rows]


async def set_rating(user_id: int, book_id: int, rating: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO ratings (user_id, book_id, rating) VALUES ($1, $2, $3)
            ON CONFLICT (user_id, book_id) DO UPDATE SET rating = EXCLUDED.rating
        """, user_id, book_id, rating)


async def get_book_rating(book_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchrow(
            "SELECT AVG(rating)::numeric(10,1) as avg_rating, COUNT(*) as count FROM ratings WHERE book_id = $1",
            book_id
        )
        return (val["avg_rating"] or 0.0, val["count"] or 0)


# ---------- USERS & BAN SYSTEM ----------

async def add_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users (user_id) VALUES ($1) ON CONFLICT (user_id) DO NOTHING",
            user_id,
        )


async def delete_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM users WHERE user_id = $1", user_id)


async def set_user_ban(user_id: int, is_banned: bool):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_banned = $1 WHERE user_id = $2", is_banned, user_id)


async def is_banned(user_id: int) -> bool:
    pool = await get_pool()
    async with pool.acquire() as conn:
        val = await conn.fetchval("SELECT is_banned FROM users WHERE user_id = $1", user_id)
        return bool(val)


async def get_all_users():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT user_id FROM users WHERE is_banned = FALSE")
        return [row["user_id"] for row in rows]


async def get_user_count():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


async def get_new_users_today():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users WHERE joined_at::date = CURRENT_DATE")


async def get_book_count():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM books")


async def get_total_downloads():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COALESCE(SUM(download_count), 0) FROM books")


# ---------- SETTINGS ----------

async def set_setting(key: str, value: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO settings (key, value) VALUES ($1, $2) ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            key, value,
        )


async def get_setting(key: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT value FROM settings WHERE key = $1", key)
