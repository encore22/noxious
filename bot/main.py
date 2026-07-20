import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_settings
from bot.db import DB
from bot.keyboards.user import kb_join_gate, kb_tos, kb_main, kb_wallet
from bot.keyboards.admin import kb_admin_main

logging.basicConfig(level=logging.INFO)


settings = load_settings()
db = DB(settings.db_path)
dp = Dispatcher()


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


@dp.message(F.text == "/start")
async def start_handler(m: Message, bot: Bot):
    full_name = (m.from_user.full_name or "").strip()
    username = m.from_user.username or ""
    user = await db.get_or_create_user(m.from_user.id, username, full_name)

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


@dp.callback_query(F.data == "menu:wallet")
async def menu_wallet(c: CallbackQuery):
    await c.message.answer("👛 Wallet menu:", reply_markup=kb_wallet())
    await c.answer()


@dp.callback_query(F.data == "menu:products")
async def menu_products(c: CallbackQuery):
    products = await db.list_products()
    if not products:
        await c.message.answer("No products yet.")
    else:
        lines = ["🛍 Products:"]
        for p in products:
            price = p["price_usd"]
            stock = p["stock_count"]
            lines.append(f"- {p['name']} | ${price:.2f} | Stock: {stock}")
        await c.message.answer("\n".join(lines))
    await c.answer()


@dp.callback_query(F.data == "menu:terms")
async def menu_terms(c: CallbackQuery):
    await c.message.answer(f"📜 Terms version: {settings.tos_version}")
    await c.answer()


@dp.callback_query(F.data == "menu:support")
async def menu_support(c: CallbackQuery):
    await c.message.answer("🆘 Support will be connected.")
    await c.answer()


@dp.message(F.text == "/admin")
async def admin_panel(m: Message):
    user = await db.user_by_tg(m.from_user.id)
    if not user or not is_staff_role(user["role"]):
        await m.answer("⛔ Admin only.")
        return
    await m.answer("🛠 Admin Panel", reply_markup=kb_admin_main())


async def main():
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN missing in .env")

    await db.connect()
    await db.init_schema()

    # Ensure owner user role if they started before
    await db.ensure_owner(settings.owner_telegram_id)

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
