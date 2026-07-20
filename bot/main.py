import asyncio
import json
import logging
from datetime import datetime, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_settings
from bot.db import DB
from bot.keyboards.user import (
    kb_join_gate, kb_tos, kb_main, kb_wallet,
    kb_products_list, kb_product_view,
    kb_orders_list, kb_order_view
)
from bot.keyboards.admin import kb_admin_main

logging.basicConfig(level=logging.INFO)

settings = load_settings()
db = DB(settings.db_path)
dp = Dispatcher()

PENDING_DISPUTE_REASON: dict[int, int] = {}   # tg_id -> order_id
PENDING_ADMIN_ACTION: dict[int, str] = {}      # admin tg_id -> action key


async def is_joined(bot: Bot, user_id: int, chat_username_or_id: str) -> bool:
    if not chat_username_or_id:
        return True
    try:
        member = await bot.get_chat_member(chat_username_or_id, user_id)
        return member.status in ("creator", "administrator", "member")
    except Exception:
        return False


async def pass_gate(bot: Bot, user_tg_id: int) -> bool:
    ch_ok = await is_joined(bot, user_tg_id, settings.force_join_channel)
    gp_ok = await is_joined(bot, user_tg_id, settings.force_join_group)
    return ch_ok and gp_ok


def is_staff_role(role: str) -> bool:
    return role in ("owner", "admin", "support")


def is_admin_role(role: str) -> bool:
    return role in ("owner", "admin")


def utc_now():
    return datetime.now(timezone.utc)


def parse_db_dt(s: str | None):
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def dispute_allowed(delivered_at: str | None, window_hours: int) -> bool:
    dt = parse_db_dt(delivered_at)
    if not dt:
        return False
    diff = utc_now() - dt
    return diff.total_seconds() <= window_hours * 3600


async def send_delivery(bot: Bot, tg_user_id: int, bundle: dict, again: bool = False):
    order = bundle["order"]
    unit = bundle["unit"]
    product = bundle["product"]

    header = (
        f"✅ {'Re-delivery' if again else 'Purchase successful'}\n"
        f"Order #{order['id']} | Receipt: <code>{order['receipt_id']}</code>\n"
        f"Product: <b>{product['name']}</b>\n"
        f"Paid: ${float(order['net_usd']):.2f}\n\n"
    )

    if unit["unit_type"] == "text":
        body = unit["payload_text"] or "(empty credential)"
        sent = await bot.send_message(tg_user_id, header + f"<pre>{body}</pre>")
    else:
        file_id = unit["file_id"]
        if file_id:
            sent = await bot.send_document(
                tg_user_id,
                document=file_id,
                caption=header + "📎 Your file delivery",
            )
        else:
            sent = await bot.send_message(tg_user_id, header + "⚠️ File delivery configured but file_id missing.")

    await db.add_proof(
        order_id=order["id"],
        user_id=order["user_id"],
        proof_type="delivery",
        message_id=sent.message_id if sent else None,
        data_json=json.dumps({
            "again": again,
            "unit_type": unit["unit_type"],
            "at": utc_now().isoformat()
        }),
    )

    if product["post_delivery_enabled"] == 1:
        txt = product["post_delivery_text"] or ""
        media_type = (product["post_delivery_media_type"] or "none").lower()
        media_file_id = product["post_delivery_media_file_id"]
        media_caption = product["post_delivery_media_caption"] or ""

        if txt.strip():
            await bot.send_message(tg_user_id, txt)

        if media_type == "photo" and media_file_id:
            await bot.send_photo(tg_user_id, media_file_id, caption=media_caption or None)
        elif media_type == "video" and media_file_id:
            await bot.send_video(tg_user_id, media_file_id, caption=media_caption or None)
        elif media_type == "document" and media_file_id:
            await bot.send_document(tg_user_id, media_file_id, caption=media_caption or None)


@dp.message(F.text == "/start")
async def start_handler(m: Message, bot: Bot):
    full_name = (m.from_user.full_name or "").strip()
    username = m.from_user.username or ""
    user = await db.get_or_create_user(m.from_user.id, username, full_name)

    if m.from_user.id == settings.owner_telegram_id and user["role"] != "owner":
        await db.execute("UPDATE users SET role='owner' WHERE tg_id=?", (m.from_user.id,))
        user = await db.user_by_tg(m.from_user.id)

    if user["is_banned"] == 1:
        await m.answer("⛔ You are banned.")
        return

    if not await pass_gate(bot, m.from_user.id):
        await m.answer(
            "🔒 Please join required channel/group first.",
            reply_markup=kb_join_gate(settings.force_join_channel, settings.force_join_group),
        )
        return

    if (user["tos_version_accepted"] or 0) < settings.tos_version:
        await m.answer(
            f"📜 Please accept Terms (v{settings.tos_version}) to continue.",
            reply_markup=kb_tos(),
        )
        return

    await m.answer("🏠 Welcome! Choose an option:", reply_markup=kb_main())


@dp.callback_query(F.data == "gate:recheck")
async def gate_recheck(c: CallbackQuery, bot: Bot):
    if await pass_gate(bot, c.from_user.id):
        user = await db.user_by_tg(c.from_user.id)
        if (user["tos_version_accepted"] or 0) < settings.tos_version:
            await c.message.answer(
                f"📜 Please accept Terms (v{settings.tos_version}) to continue.",
                reply_markup=kb_tos(),
            )
        else:
            await c.message.answer("✅ Access granted.", reply_markup=kb_main())
    else:
        await c.answer("Still not joined both.", show_alert=True)


@dp.callback_query(F.data == "tos:accept")
async def tos_accept(c: CallbackQuery):
    await db.accept_tos(c.from_user.id, settings.tos_version)
    await c.message.answer("✅ Terms accepted.", reply_markup=kb_main())
    await c.answer()


@dp.callback_query(F.data == "menu:back")
async def menu_back(c: CallbackQuery):
    await c.message.answer("🏠 Main menu:", reply_markup=kb_main())
    await c.answer()


@dp.callback_query(F.data == "menu:wallet")
async def menu_wallet(c: CallbackQuery):
    await c.message.answer("👛 Wallet menu:", reply_markup=kb_wallet())
    await c.answer()


@dp.callback_query(F.data == "wallet:balance")
async def wallet_balance(c: CallbackQuery):
    user = await db.user_by_tg(c.from_user.id)
    bal = await db.wallet_balance(user["id"])
    await c.message.answer(f"💰 Wallet balance: ${bal:.2f}")
    await c.answer()


@dp.callback_query(F.data == "wallet:deposit")
async def wallet_deposit(c: CallbackQuery):
    await c.message.answer(
        "➕ Deposit request:\n"
        "Manual methods currently enabled: UPI / Binance ID.\n"
        "Send amount + proof to admin/support."
    )
    await c.answer()


@dp.callback_query(F.data == "wallet:tx")
async def wallet_tx(c: CallbackQuery):
    user = await db.user_by_tg(c.from_user.id)
    rows = await db.fetchall(
        "SELECT * FROM wallet_tx WHERE user_id=? ORDER BY id DESC LIMIT 10",
        (user["id"],),
    )
    if not rows:
        await c.message.answer("No wallet transactions yet.")
    else:
        lines = ["🧾 Last 10 transactions:"]
        for r in rows:
            sign = "+" if r["direction"] == "credit" else "-"
            lines.append(f"{r['id']}. {r['tx_type']} {sign}${float(r['amount_usd']):.2f}")
        await c.message.answer("\n".join(lines))
    await c.answer()


@dp.callback_query(F.data == "menu:products")
async def menu_products(c: CallbackQuery):
    products = await db.list_products()
    if not products:
        await c.message.answer("No products yet.")
    else:
        await c.message.answer("🛍 Select a product:", reply_markup=kb_products_list(products))
    await c.answer()


@dp.callback_query(F.data.startswith("prod:view:"))
async def product_view(c: CallbackQuery):
    product_id = int(c.data.split(":")[2])
    p = await db.product_by_id(product_id)
    if not p or p["is_active"] != 1:
        await c.answer("Product unavailable.", show_alert=True)
        return

    user = await db.user_by_tg(c.from_user.id)
    price = float(p["price_usd"])
    if user["is_reseller"] == 1:
        if p["reseller_price_usd"] is not None:
            price = float(p["reseller_price_usd"])
        else:
            disc = float(user["reseller_discount_percent"] or 0)
            price = max(0.0, price - (price * disc / 100.0))

    stock_txt = f"{p['stock_count']}" if p["show_stock"] == 1 else "Hidden"
    msg = (
        f"🧾 <b>{p['name']}</b>\n"
        f"Your Price: ${price:.2f}\n"
        f"Stock: {stock_txt}\n\n"
        f"{p['description'] or ''}"
    )
    await c.message.answer(msg, reply_markup=kb_product_view(product_id))
    await c.answer()


@dp.callback_query(F.data.startswith("prod:buy:"))
async def product_buy(c: CallbackQuery, bot: Bot):
    product_id = int(c.data.split(":")[2])
    user = await db.user_by_tg(c.from_user.id)
    if not user:
        await c.answer("User not found.", show_alert=True)
        return

    bundle, err = await db.create_order_with_unit(user["id"], product_id)
    if err:
        await c.answer(err, show_alert=True)
        return

    await send_delivery(bot, c.from_user.id, bundle, again=False)
    await c.message.answer("📦 Delivered. You can view from My Orders too.")
    await c.answer("Purchase complete ✅", show_alert=True)


@dp.callback_query(F.data == "menu:orders")
async def menu_orders(c: CallbackQuery):
    user = await db.user_by_tg(c.from_user.id)
    orders = await db.my_orders(user["id"], limit=20)
    if not orders:
        await c.message.answer("You have no orders yet.")
    else:
        await c.message.answer("📦 Your orders:", reply_markup=kb_orders_list(orders))
    await c.answer()


@dp.callback_query(F.data.startswith("order:view:"))
async def order_view(c: CallbackQuery):
    order_id = int(c.data.split(":")[2])
    user = await db.user_by_tg(c.from_user.id)
    o = await db.order_for_user(order_id, user["id"])
    if not o:
        await c.answer("Order not found.", show_alert=True)
        return

    allow = dispute_allowed(o["delivered_at"], settings.dispute_window_hours)
    msg = (
        f"🧾 Order #{o['id']}\n"
        f"Receipt: <code>{o['receipt_id']}</code>\n"
        f"Product: {o['product_name']}\n"
        f"Paid: ${float(o['net_usd']):.2f}\n"
        f"Status: {o['status']}\n"
        f"Dispute window: {'Open' if allow else 'Closed'}"
    )
    await c.message.answer(msg, reply_markup=kb_order_view(order_id))
    await c.answer()


@dp.callback_query(F.data.startswith("order:show:"))
async def order_show_again(c: CallbackQuery, bot: Bot):
    order_id = int(c.data.split(":")[2])
    user = await db.user_by_tg(c.from_user.id)
    o = await db.order_for_user(order_id, user["id"])
    if not o:
        await c.answer("Order not found.", show_alert=True)
        return
    unit = await db.delivered_unit_for_order(order_id)
    if not unit:
        await c.answer("No delivery unit found.", show_alert=True)
        return
    product = await db.product_by_id(o["product_id"])
    await send_delivery(bot, c.from_user.id, {"order": o, "unit": unit, "product": product}, again=True)
    await c.answer("Re-delivered ✅", show_alert=True)


@dp.callback_query(F.data.startswith("order:dispute:"))
async def order_dispute(c: CallbackQuery):
    order_id = int(c.data.split(":")[2])
    user = await db.user_by_tg(c.from_user.id)
    o = await db.order_for_user(order_id, user["id"])
    if not o:
        await c.answer("Order not found.", show_alert=True)
        return

    if not dispute_allowed(o["delivered_at"], settings.dispute_window_hours):
        await c.answer("Dispute window expired.", show_alert=True)
        return

    PENDING_DISPUTE_REASON[c.from_user.id] = order_id
    await c.message.answer(
        f"⚠️ Send dispute reason text for Order #{order_id}.\n"
        f"Window: {settings.dispute_window_hours}h from delivery."
    )
    await c.answer()


@dp.callback_query(F.data == "menu:terms")
async def menu_terms(c: CallbackQuery):
    await c.message.answer(f"📜 Terms version: {settings.tos_version}")
    await c.answer()


@dp.callback_query(F.data == "menu:support")
async def menu_support(c: CallbackQuery):
    await c.message.answer("🆘 Send your issue. Support will respond.")
    await c.answer()


@dp.callback_query(F.data == "menu:coupons")
async def menu_coupons(c: CallbackQuery):
    await c.message.answer("🎟 Send coupon code as plain text (example: WELCOME10).")
    await c.answer()


@dp.message(F.text == "/admin")
async def admin_panel(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_staff_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return
    await m.answer(
        "🛠 Admin Panel\n\n"
        "Quick commands:\n"
        "/stock_add <product_id>\nThen send lines (1 line = 1 unit)\n\n"
        "/wallet_add <tg_id> <amount>\n"
        "/wallet_deduct <tg_id> <amount>\n"
        "/reseller_add <tg_id> <discount_percent>\n"
        "/reseller_remove <tg_id>\n"
        "/analytics",
        reply_markup=kb_admin_main(),
    )


@dp.message(F.text.startswith("/stock_add"))
async def admin_stock_add_start(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_admin_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return

    parts = m.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await m.answer("Usage: /stock_add <product_id>")
        return

    product_id = int(parts[1])
    p = await db.product_by_id(product_id)
    if not p:
        await m.answer("Product not found.")
        return

    PENDING_ADMIN_ACTION[m.from_user.id] = f"stock_add:{product_id}"
    await m.answer(
        f"Send stock lines for product #{product_id} ({p['name']}).\n"
        f"Each line = one credential/unit.\n"
        f"Send /cancel to abort."
    )


@dp.message(F.text == "/analytics")
async def admin_analytics(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_staff_role(user["role"]):
        await m.answer("⛔ Staff only.")
        return

    snap, low = await db.analytics_snapshot()
    lines = [
        "📊 Analytics Snapshot",
        f"Users: {snap['total_users']}",
        f"Orders: {snap['total_orders']}",
        f"Revenue: ${float(snap['gross_revenue']):.2f}",
        f"Open disputes: {snap['open_disputes']}",
        "",
        "⚠️ Low stock:",
    ]
    if not low:
        lines.append("- None")
    else:
        for p in low:
            lines.append(f"- #{p['id']} {p['name']} | stock {p['stock_count']} (thr {p['low_stock_threshold']})")
    await m.answer("\n".join(lines))


@dp.message(F.text.startswith("/wallet_add"))
async def admin_wallet_add(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_admin_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return

    parts = m.text.strip().split()
    if len(parts) != 3:
        await m.answer("Usage: /wallet_add <tg_id> <amount>")
        return
    try:
        tg_id = int(parts[1])
        amount = float(parts[2])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await m.answer("Invalid values.")
        return

    ok, msg = await db.wallet_credit_by_tg(tg_id, amount, actor_user_id=user["id"])
    await m.answer(("✅ " if ok else "❌ ") + msg)


@dp.message(F.text.startswith("/wallet_deduct"))
async def admin_wallet_deduct(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_admin_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return

    parts = m.text.strip().split()
    if len(parts) != 3:
        await m.answer("Usage: /wallet_deduct <tg_id> <amount>")
        return
    try:
        tg_id = int(parts[1])
        amount = float(parts[2])
        if amount <= 0:
            raise ValueError
    except ValueError:
        await m.answer("Invalid values.")
        return

    ok, msg = await db.wallet_debit_by_tg(tg_id, amount, actor_user_id=user["id"])
    await m.answer(("✅ " if ok else "❌ ") + msg)


@dp.message(F.text.startswith("/reseller_add"))
async def admin_reseller_add(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_admin_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return
    parts = m.text.strip().split()
    if len(parts) != 3:
        await m.answer("Usage: /reseller_add <tg_id> <discount_percent>")
        return
    try:
        tg_id = int(parts[1])
        discount = float(parts[2])
    except ValueError:
        await m.answer("Invalid values.")
        return
    ok, msg = await db.set_reseller(tg_id, True, discount)
    await m.answer(("✅ " if ok else "❌ ") + msg)


@dp.message(F.text.startswith("/reseller_remove"))
async def admin_reseller_remove(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_admin_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return
    parts = m.text.strip().split()
    if len(parts) != 2:
        await m.answer("Usage: /reseller_remove <tg_id>")
        return
    try:
        tg_id = int(parts[1])
    except ValueError:
        await m.answer("Invalid tg_id.")
        return
    ok, msg = await db.set_reseller(tg_id, False)
    await m.answer(("✅ " if ok else "❌ ") + msg)


@dp.message(F.text == "/cancel")
async def cancel_any(m: Message):
    if m.from_user.id in PENDING_ADMIN_ACTION:
        PENDING_ADMIN_ACTION.pop(m.from_user.id, None)
        await m.answer("Cancelled.")
        return
    if m.from_user.id in PENDING_DISPUTE_REASON:
        PENDING_DISPUTE_REASON.pop(m.from_user.id, None)
        await m.answer("Cancelled.")
        return
    await m.answer("Nothing pending.")


@dp.message(F.text)
async def text_router(m: Message, bot: Bot):
    txt = (m.text or "").strip()

    # dispute reason capture
    if m.from_user.id in PENDING_DISPUTE_REASON:
        order_id = PENDING_DISPUTE_REASON.pop(m.from_user.id)
        user = await db.user_by_tg(m.from_user.id)
        reason = txt
        await db.create_dispute(order_id, user["id"], reason)
        await m.answer("✅ Dispute submitted. Support will review.")

        if settings.support_chat_id:
            try:
                await bot.send_message(
                    settings.support_chat_id,
                    f"🆘 New dispute\nOrder #{order_id}\nUser: {m.from_user.id}\nReason: {reason}",
                )
            except Exception:
                pass
        return

    # admin pending actions
    if m.from_user.id in PENDING_ADMIN_ACTION:
        action = PENDING_ADMIN_ACTION[m.from_user.id]
        user = await db.user_by_tg(m.from_user.id)
        if not user or not is_admin_role(user["role"]):
            PENDING_ADMIN_ACTION.pop(m.from_user.id, None)
            await m.answer("⛔ Admin only.")
            return

        if action.startswith("stock_add:"):
            product_id = int(action.split(":")[1])
            lines = txt.splitlines()
            n = await db.add_product_units_text(product_id, lines)
            PENDING_ADMIN_ACTION.pop(m.from_user.id, None)
            await m.answer(f"✅ Added {n} units to product #{product_id}.")
            return

    # coupon apply fallback (plain text)
    user = await db.user_by_tg(m.from_user.id)
    if user and len(txt) >= 3 and " " not in txt and txt.isascii():
        ok, msg = await db.apply_coupon_for_user(user["id"], txt)
        if ok:
            await m.answer("✅ " + msg)
            return


async def main():
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN missing in .env")

    await db.connect()
    await db.init_schema()

    b
