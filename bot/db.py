import os
import uuid
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

    async def user_by_id(self, user_id: int):
        return await self.fetchone("SELECT * FROM users WHERE id=?", (user_id,))

    async def accept_tos(self, tg_id: int, version: int):
        await self.execute("UPDATE users SET tos_version_accepted=? WHERE tg_id=?", (version, tg_id))

    async def list_products(self):
        return await self.fetchall(
            "SELECT * FROM products WHERE is_active=1 ORDER BY id DESC"
        )

    async def product_by_id(self, product_id: int):
        return await self.fetchone("SELECT * FROM products WHERE id=?", (product_id,))

    async def ensure_owner(self, owner_tg_id: int):
        row = await self.user_by_tg(owner_tg_id)
        if row:
            await self.execute("UPDATE users SET role='owner' WHERE tg_id=?", (owner_tg_id,))

    async def wallet_balance(self, user_id: int) -> float:
        row = await self.fetchone("SELECT balance_usd FROM wallets WHERE user_id=?", (user_id,))
        return float(row["balance_usd"]) if row else 0.0

    async def wallet_add_tx(
        self,
        user_id: int,
        tx_type: str,
        direction: str,
        amount_usd: float,
        method: str | None = None,
        ref_id: str | None = None,
        note: str | None = None,
        created_by: int | None = None,
    ):
        await self.execute(
            """
            INSERT INTO wallet_tx(user_id,tx_type,direction,amount_usd,method,ref_id,note,created_by)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (user_id, tx_type, direction, amount_usd, method, ref_id, note, created_by),
        )

    async def wallet_credit(self, user_id: int, amount_usd: float, note: str = "manual"):
        await self.execute(
            "UPDATE wallets SET balance_usd=balance_usd+?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (amount_usd, user_id),
        )
        await self.wallet_add_tx(user_id, "manual_add", "credit", amount_usd, note=note)

    async def wallet_debit(self, user_id: int, amount_usd: float, note: str = "purchase"):
        await self.execute(
            "UPDATE wallets SET balance_usd=balance_usd-?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (amount_usd, user_id),
        )
        await self.wallet_add_tx(user_id, "purchase", "debit", amount_usd, note=note)

    async def create_order_with_unit(self, user_id: int, product_id: int):
        async with self.conn.execute("BEGIN IMMEDIATE"):
            user = await self.user_by_id(user_id)
            product = await self.product_by_id(product_id)
            if not user or not product:
                await self.conn.rollback()
                return None, "User or product not found."

            if product["is_active"] != 1:
                await self.conn.rollback()
                return None, "Product inactive."

            unit = await self.fetchone(
                """
                SELECT * FROM product_units
                WHERE product_id=? AND is_sold=0
                ORDER BY id ASC LIMIT 1
                """,
                (product_id,),
            )
            if not unit:
                await self.conn.rollback()
                return None, "Out of stock."

            pricing_tier = "reseller" if user["is_reseller"] == 1 else "retail"
            gross = float(product["price_usd"])
            if pricing_tier == "reseller":
                if product["reseller_price_usd"] is not None:
                    net = float(product["reseller_price_usd"])
                else:
                    disc_pct = float(user["reseller_discount_percent"] or 0)
                    net = max(0.0, gross - (gross * disc_pct / 100.0))
            else:
                net = gross

            discount = max(0.0, gross - net)

            bal = await self.wallet_balance(user_id)
            if bal < net:
                await self.conn.rollback()
                return None, f"Insufficient wallet balance. Need ${net:.2f}, have ${bal:.2f}"

            receipt_id = f"RCPT-{uuid.uuid4().hex[:10].upper()}"

            cur = await self.conn.execute(
                """
                INSERT INTO orders(user_id,product_id,pricing_tier,gross_usd,discount_usd,net_usd,status,receipt_id)
                VALUES(?,?,?,?,?,?, 'created', ?)
                """,
                (user_id, product_id, pricing_tier, gross, discount, net, receipt_id),
            )
            order_id = cur.lastrowid

            await self.conn.execute(
                """
                UPDATE product_units
                SET is_sold=1, sold_to_user_id=?, sold_order_id=?, sold_at=CURRENT_TIMESTAMP
                WHERE id=?
                """,
                (user_id, order_id, unit["id"]),
            )

            await self.conn.execute(
                "UPDATE wallets SET balance_usd=balance_usd-?, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                (net, user_id),
            )
            await self.conn.execute(
                """
                INSERT INTO wallet_tx(user_id,tx_type,direction,amount_usd,method,ref_id,note)
                VALUES(?,?,?,?,?,?,?)
                """,
                (user_id, "purchase", "debit", net, "wallet", str(order_id), "Product purchase"),
            )

            await self.conn.execute(
                "UPDATE products SET stock_count = stock_count - 1 WHERE id=? AND stock_count>0",
                (product_id,),
            )

            await self.conn.execute(
                "UPDATE orders SET status='delivered', delivered_at=CURRENT_TIMESTAMP WHERE id=?",
                (order_id,),
            )

            await self.conn.execute(
                """
                INSERT INTO deliveries(order_id,step,attempt_no,status,processed_at)
                VALUES(?, 'credential', 1, 'ok', CURRENT_TIMESTAMP)
                """,
                (order_id,),
            )

            await self.conn.commit()

            order = await self.fetchone("SELECT * FROM orders WHERE id=?", (order_id,))
            unit2 = await self.fetchone("SELECT * FROM product_units WHERE id=?", (unit["id"],))
            return {"order": order, "unit": unit2, "product": product}, None

    async def my_orders(self, user_id: int, limit: int = 10):
        return await self.fetchall(
            """
            SELECT o.*, p.name AS product_name
            FROM orders o
            JOIN products p ON p.id=o.product_id
            WHERE o.user_id=?
            ORDER BY o.id DESC
            LIMIT ?
            """,
            (user_id, limit),
        )

    async def order_for_user(self, order_id: int, user_id: int):
        return await self.fetchone(
            """
            SELECT o.*, p.name AS product_name
            FROM orders o
            JOIN products p ON p.id=o.product_id
            WHERE o.id=? AND o.user_id=?
            """,
            (order_id, user_id),
        )

    async def delivered_unit_for_order(self, order_id: int):
        return await self.fetchone(
            "SELECT * FROM product_units WHERE sold_order_id=? LIMIT 1",
            (order_id,),
        )

    async def create_dispute(self, order_id: int, user_id: int, reason: str):
        await self.execute(
            """
            INSERT INTO disputes(order_id,user_id,reason,status)
            VALUES(?,?,?,'open')
            """,
            (order_id, user_id, reason),
        )

    async def add_proof(self, order_id: int, user_id: int, proof_type: str, message_id: int | None, data_json: str):
        await self.execute(
            """
            INSERT INTO proofs(order_id,user_id,proof_type,message_id,data_json)
            VALUES(?,?,?,?,?)
            """,
            (order_id, user_id, proof_type, message_id, data_json),
      )
