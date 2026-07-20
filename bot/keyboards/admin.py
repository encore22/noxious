from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def kb_admin_main():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📦 Products", callback_data="admin:products")],
            [InlineKeyboardButton(text="💳 Payments", callback_data="admin:payments")],
            [InlineKeyboardButton(text="👥 Users", callback_data="admin:users")],
            [InlineKeyboardButton(text="💸 Wallet Ops", callback_data="admin:walletops")],
            [InlineKeyboardButton(text="🧾 Orders", callback_data="admin:orders")],
            [InlineKeyboardButton(text="🎟 Coupons", callback_data="admin:coupons")],
            [InlineKeyboardButton(text="📢 Broadcast", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="📊 Analytics", callback_data="admin:analytics")],
            [InlineKeyboardButton(text="⚙️ Settings", callback_data="admin:settings")],
            [InlineKeyboardButton(text="🧑‍💼 Roles", callback_data="admin:roles")],
        ]
    )
