import os
import aiosqlite
from typing import Optional, Any

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


class DB:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON;")
        return self

    async def init_schema(self):
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            sql = f.read()
        await self.conn.executescript(sql)
        await self.conn.commit()

    async def close(self):
        await self.conn.close()

    async def fetchone(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        async with self.conn.execute(query, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, query: str, params: tuple = ()) -> list[aiosqlite.Row]:
        async with self.conn.execute(query, params) as cur:
            return await cur.fetchall()

    async def execute(self, query: str, params: tuple = ()) -> Any:
        cur = await self.conn.execute(query, params)
        await self.conn.commit()
        return cur

    async def get_or_create_user(self, tg_id: int, username: str, full_name: str):
        row = await self.fetchone("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        if row:
            return row

        await self.execute(
            "INSERT INTO users(tg_id, username, full_name) VALUES(?,?,?)",
            (tg_id, username, full_name),
        )
        row = await self.fetchone("SELECT * FROM users WHERE tg_id = ?", (tg_id,))
        await self.execute("INSERT OR IGNORE INTO wallets(user_id,balance_usd) VALUES(?,0)", (row["id"],))
        return row

    async def user_by_tg(self, tg_id: int):
        return await self.fetchone("SELECT * FROM users WHERE tg_id=?", (tg_id,))

    async def accept_tos(self, tg_id: int, version: int):
        await self.execute("UPDATE users SET tos_version_accepted=? WHERE tg_id=?", (version, tg_id))

    async def list_products(self):
        return await self.fetchall(
            "SELECT * FROM products WHERE is_active=1 ORDER BY id DESC"
        )

    async def ensure_owner(self, owner_tg_id: int):
        row = await self.user_by_tg(owner_tg_id)
        if row:
            await self.execute("UPDATE users SET role='owner' WHERE tg_id=?", (owner_tg_id,))
