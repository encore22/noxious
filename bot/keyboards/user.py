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


def kb_products_list(products):
    rows = []
    for p in products:
        rows.append(
            [InlineKeyboardButton(
                text=f"{p['name']} • ${float(p['price_usd']):.2f}",
                callback_data=f"prod:view:{p['id']}"
            )]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_product_view(product_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Buy Now", callback_data=f"prod:buy:{product_id}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:products")],
        ]
    )


def kb_orders_list(orders):
    rows = []
    for o in orders:
        rows.append(
            [InlineKeyboardButton(
                text=f"#{o['id']} • {o['product_name']} • ${float(o['net_usd']):.2f}",
                callback_data=f"order:view:{o['id']}"
            )]
        )
    rows.append([InlineKeyboardButton(text="⬅️ Back", callback_data="menu:back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_order_view(order_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔐 Show Delivery Again", callback_data=f"order:show:{order_id}")],
            [InlineKeyboardButton(text="⚠️ Open Dispute", callback_data=f"order:dispute:{order_id}")],
            [InlineKeyboardButton(text="⬅️ Back", callback_data="menu:orders")],
        ]
    )
