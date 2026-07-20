from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def kb_join_gate(channel: str, group: str):
    rows = []
    if channel:
        rows.append([InlineKeyboardButton(text="✅ Join Channel", url=f"https://t.me/{channel.lstrip('@')}")])
    if group:
        rows.append([InlineKeyboardButton(text="✅ Join Group", url=f"https://t.me/{group.lstrip('@')}")])
    rows.append([InlineKeyboardButton(text="🔄 Recheck Join", callback_data="gate:recheck")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_tos():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ I Accept", callback_data="tos:accept")]
        ]
    )


def kb_main():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛍 Products", callback_data="menu:products")],
            [InlineKeyboardButton(text="👛 Wallet", callback_data="menu:wallet")],
            [InlineKeyboardButton(text="🎟 Coupons", callback_data="menu:coupons")],
            [InlineKeyboardButton(text="📦 My Orders", callback_data="menu:orders")],
            [InlineKeyboardButton(text="🆘 Support", callback_data="menu:support")],
            [InlineKeyboardButton(text="📜 Terms", callback_data="menu:terms")],
        ]
    )


def kb_wallet():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Balance", callback_data="wallet:balance")],
            [InlineKeyboardButton(text="➕ Deposit", callback_data="wallet:deposit")],
            [InlineKeyboardButton(text="🧾 Transactions", callback_data="wallet:tx")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:back")],
        ]
    )
