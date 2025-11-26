import logging
import sqlite3
import uuid
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)

# ================= CONFIGURATION =================
TOKEN = '8200854859:AAGqwyeAXRzTmwervJuFN6GVJK_wuRwj5rg'  # <--- REPLACE THIS
ADMIN_ID = 6083286836           # <--- REPLACE THIS (Your numeric Telegram ID)
SUPPORT_USERNAME = "@jashanxjagy"
DB_FILE = "ecommerce_bot.db"
EXCHANGE_RATE = 87  # 1 USD = 87 INR

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATABASE MANAGEMENT =================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (user_id INTEGER PRIMARY KEY, username TEXT, address TEXT, currency TEXT DEFAULT 'INR', is_banned INTEGER DEFAULT 0, joined_date TEXT)''')
    # Products Table
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (code TEXT PRIMARY KEY, name TEXT, original_price REAL, price REAL, discount REAL, 
                  payment_methods TEXT, location TEXT, availability INTEGER, image_id TEXT, is_active INTEGER DEFAULT 1)''')
    # Orders Table
    c.execute('''CREATE TABLE IF NOT EXISTS orders
                 (order_id TEXT PRIMARY KEY, user_id INTEGER, product_code TEXT, status TEXT, 
                  payment_method TEXT, delivery_address TEXT, price_at_time REAL, currency TEXT, 
                  timestamp TEXT, rejection_reason TEXT)''')
    conn.commit()
    conn.close()

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

# ================= STATES FOR CONVERSATIONS =================
# Adding Item States
ADD_NAME, ADD_ORIG_PRICE, ADD_PRICE, ADD_PAYMENT, ADD_LOC, ADD_IMG = range(6)
# Buying States
BUY_CONFIRM, BUY_ADDRESS_CHOICE, BUY_ADDRESS_INPUT, BUY_PAYMENT = range(4)
# Admin User Management
BAN_REASON = range(1)
# Admin Reject Reason
REJECT_REASON = range(1)

# ================= HELPER FUNCTIONS =================
def format_price(price, currency):
    if currency == 'USD':
        converted = round(price / EXCHANGE_RATE, 2)
        return f"${converted} USD"
    return f"₹{price} INR"

def generate_unique_code():
    return str(uuid.uuid4())[:8].upper()

def get_user_currency(user_id):
    conn = get_db_connection()
    user = conn.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    return user['currency'] if user else 'INR'

# ================= COMMAND HANDLERS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn = get_db_connection()
    
    # Check ban status
    db_user = conn.execute("SELECT is_banned FROM users WHERE user_id = ?", (user.id,)).fetchone()
    if db_user and db_user['is_banned']:
        await update.message.reply_text("🚫 You are banned from using this bot.")
        conn.close()
        return

    # Register user if new
    if not db_user:
        conn.execute("INSERT INTO users (user_id, username, joined_date) VALUES (?, ?, ?)",
                     (user.id, user.username, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    conn.close()

    intro_text = (
        f"🌟 **Welcome to the Premium Market, {user.first_name}!** 🌟\n\n"
        "Discover exclusive services and products tailored just for you. "
        "Experience the next level of e-commerce automation.\n\n"
        "👇 **Navigate using the buttons below:**"
    )
    
    keyboard = [
        [InlineKeyboardButton("🛍️ Enter the Market", callback_data='menu_market_0')],
        [InlineKeyboardButton("👤 Profile", callback_data='menu_profile'), InlineKeyboardButton("📦 Active Orders", callback_data='menu_active')],
        [InlineKeyboardButton("📜 Order History", callback_data='menu_history')],
        [InlineKeyboardButton("⚙️ Settings", callback_data='menu_settings')]
    ]
    
    if user.id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("🔒 Admin Panel", callback_data='admin_panel')])

    await update.message.reply_text(intro_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🤖 **Bot Help & Instructions**\n\n"
        "**For Users:**\n"
        "• `/start` - Open the main menu\n"
        "• `/info <code` - Get detailed info about a product\n"
        "• `/buy <code>` - Start purchasing a product\n"
        "• Support: Contact " + SUPPORT_USERNAME + "\n\n"
    )
    if update.effective_user.id == ADMIN_ID:
        text += (
            "**👑 Admin Commands:**\n"
            "• `/admin` - Open Admin Dashboard\n"
            "• `/users` - List all users\n"
            "• `/user <id>` - Manage a specific user\n"
            "• `/accept <order_id>` - Quick accept\n"
            "• `/cancel <order_id>` - Quick cancel\n"
            "• `/delist <code>` - Quick delist item"
        )
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= MENU CALLBACKS =================

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'main_menu':
        await start(update, context)
        
    elif data.startswith('menu_market_'):
        page = int(data.split('_')[-1])
        await show_market(update, context, page)
        
    elif data == 'menu_profile':
        await show_profile(update, context)
        
    elif data == 'menu_settings':
        await show_settings(update, context)
        
    elif data == 'menu_active':
        await show_orders(update, context, active_only=True)
        
    elif data == 'menu_history':
        await show_orders(update, context, active_only=False)

    elif data == 'admin_panel':
        if update.effective_user.id == ADMIN_ID:
            await show_admin_panel(update, context)

# ================= MARKET & PRODUCT LOGIC =================

async def show_market(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    ITEMS_PER_PAGE = 5
    offset = page * ITEMS_PER_PAGE
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products WHERE is_active = 1 LIMIT ? OFFSET ?", (ITEMS_PER_PAGE, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1").fetchone()[0]
    user_currency = get_user_currency(update.effective_user.id)
    conn.close()

    text = "🛒 **Available Products**\n\n"
    if not products:
        text += "No products currently available."
    
    for p in products:
        price_display = format_price(p['price'], user_currency)
        avail = "✅ Available" if p['availability'] else "❌ Out of Stock"
        text += (
            f"🔹 *{p['name']}*\n"
            f"💰 Price: {price_display} (Save {p['discount']}!)\n"
            f"📦 {avail}\n"
            f"💳 Methods: {p['payment_methods']}\n"
            f"📋 Code: `{p['code']}`\n\n"
        )

    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'menu_market_{page-1}'))
    if (offset + ITEMS_PER_PAGE) < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f'menu_market_{page+1}'))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')])
    
    try:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await update.effective_message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def product_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /info <product_code>")
        return
    
    code = args[0]
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE code = ?", (code,)).fetchone()
    user_currency = get_user_currency(update.effective_user.id)
    conn.close()

    if not product:
        await update.message.reply_text("❌ Product not found.")
        return

    details = (
        f"📦 **Product Details**\n\n"
        f"🏷️ **Name:** {product['name']}\n"
        f"🆔 **Code:** `{product['code']}`\n"
        f"💵 **Price:** {format_price(product['price'], user_currency)}\n"
        f"📉 **Discount:** {product['discount']}%\n"
        f"📍 **Location:** {product['location']}\n"
        f"💳 **Payment:** {product['payment_methods']}\n"
        f"✅ **Status:** {'Available' if product['availability'] else 'Unavailable'}"
    )

    buttons = [
        [InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_start_{product['code']}")],
        [InlineKeyboardButton("❓ Help", url=f"https://t.me/{SUPPORT_USERNAME.replace('@', '')}")]
    ]

    if product['image_id']:
        await update.message.reply_photo(product['image_id'], caption=details, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(details, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# ================= BUYING FLOW (CONVERSATION) =================

async def buy_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        code = query.data.split('_')[-1]
        await query.answer()
    else:
        # Triggered via /buy command
        if not context.args:
            await update.message.reply_text("Usage: /buy <product_code>")
            return ConversationHandler.END
        code = context.args[0]

    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE code = ? AND is_active = 1", (code,)).fetchone()
    user_currency = get_user_currency(update.effective_user.id)
    
    if not product:
        msg = "❌ Product not found or inactive."
        if query: await query.edit_message_text(msg)
        else: await update.message.reply_text(msg)
        conn.close()
        return ConversationHandler.END

    if not product['availability']:
        msg = "❌ This product is currently out of stock."
        if query: await query.edit_message_text(msg)
        else: await update.message.reply_text(msg)
        conn.close()
        return ConversationHandler.END

    context.user_data['buy_product'] = dict(product)
    conn.close()

    text = (
        f"🛍️ **Order Summary**\n"
        f"Product: {product['name']}\n"
        f"Price: {format_price(product['price'], user_currency)}\n"
        f"Refund Policy: 7 Days (if applicable)\n\n"
        "Do you want to proceed?"
    )
    buttons = [[InlineKeyboardButton("✅ Place Order", callback_data='buy_confirm')],
               [InlineKeyboardButton("❌ Cancel", callback_data='buy_cancel')]]
    
    if query:
        await query.edit_message_caption(caption=text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons)) if query.message.caption else await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    
    return BUY_CONFIRM

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'buy_cancel':
        await query.edit_message_text("❌ Order cancelled.")
        return ConversationHandler.END

    # Ask for address
    conn = get_db_connection()
    user = conn.execute("SELECT address FROM users WHERE user_id = ?", (update.effective_user.id,)).fetchone()
    conn.close()

    buttons = []
    if user and user['address']:
        context.user_data['saved_address'] = user['address']
        buttons.append([InlineKeyboardButton(f"Use Saved: {user['address'][:20]}...", callback_data='addr_saved')])
    
    buttons.append([InlineKeyboardButton("✍️ Enter New Address", callback_data='addr_new')])
    
    await query.edit_message_text("📍 **Delivery Address**\nSelect an option:", 
                                  parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_ADDRESS_CHOICE

async def buy_address_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == 'addr_saved':
        context.user_data['final_address'] = context.user_data['saved_address']
        return await ask_payment_method(update, context)
    
    elif query.data == 'addr_new':
        await query.edit_message_text("📝 Please type your full delivery address now:")
        return BUY_ADDRESS_INPUT

async def buy_address_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text
    context.user_data['final_address'] = address
    
    # Save to profile?
    conn = get_db_connection()
    conn.execute("UPDATE users SET address = ? WHERE user_id = ?", (address, update.effective_user.id))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Address saved.")
    # Move to payment method via a dummy message or re-render
    return await ask_payment_method(update, context, is_msg=True)

async def ask_payment_method(update: Update, context: ContextTypes.DEFAULT_TYPE, is_msg=False):
    buttons = [
        [InlineKeyboardButton("💵 Cash on Delivery (COD)", callback_data='pay_cod')],
        [InlineKeyboardButton("💳 Online Payment", callback_data='pay_online')]
    ]
    text = "💳 **Select Payment Method**"
    
    if is_msg:
        await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    else:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    return BUY_PAYMENT

async def buy_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    product = context.user_data['buy_product']
    
    if data == 'pay_online':
        await query.edit_message_text(
            f"💻 **Online Payment**\n\nPlease contact support to complete payment.\n"
            f"Send code `{product['code']}` to {SUPPORT_USERNAME}",
            parse_mode='Markdown'
        )
        return ConversationHandler.END
    
    elif data == 'pay_cod':
        # Finalize Order
        order_id = "ORD-" + str(uuid.uuid4())[:6].upper()
        user = query.from_user
        address = context.user_data['final_address']
        conn = get_db_connection()
        user_currency = get_user_currency(user.id)
        
        conn.execute(
            "INSERT INTO orders (order_id, user_id, product_code, status, payment_method, delivery_address, price_at_time, currency, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (order_id, user.id, product['code'], 'Pending', 'COD', address, product['price'], user_currency, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        conn.close()
        
        # Notify Admin
        admin_text = (
            f"🔔 **New Order Received!**\n\n"
            f"🆔 Order ID: `{order_id}`\n"
            f"👤 User: {user.full_name} (@{user.username})\n"
            f"📦 Product: {product['name']} (`{product['code']}`)\n"
            f"💰 Price: {product['price']}\n"
            f"📍 Address: {address}\n"
            f"💳 Method: COD"
        )
        admin_btns = [
            [InlineKeyboardButton("✅ Accept", callback_data=f'adm_acc_{order_id}'),
             InlineKeyboardButton("❌ Cancel", callback_data=f'adm_can_{order_id}')]
        ]
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(admin_btns))
        
        await query.edit_message_text(
            f"🎉 **Order Placed Successfully!**\n\n"
            f"🆔 Order ID: `{order_id}`\n"
            f"Check 'Active Orders' for status updates.",
            parse_mode='Markdown'
        )
        return ConversationHandler.END

# ================= USER PROFILE & SETTINGS =================

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    orders = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)).fetchone()[0]
    conn.close()

    text = (
        f"👤 **My Profile**\n\n"
        f"📛 Name: {update.effective_user.full_name}\n"
        f"📅 Joined: {user['joined_date']}\n"
        f"📦 Total Orders: {orders}\n"
        f"📍 Saved Address: {user['address'] if user['address'] else 'Not set'}"
    )
    # Simplified: Address update happens during buy or can be a separate conversation
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]
    await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = get_db_connection()
    user = conn.execute("SELECT currency FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    current_curr = user['currency'] if user else 'INR'
    new_curr = 'USD' if current_curr == 'INR' else 'INR'
    
    # If triggered by button toggle
    query = update.callback_query
    if query.data.startswith('set_curr_'):
        new_val = query.data.split('_')[-1]
        conn.execute("UPDATE users SET currency = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        current_curr = new_val
        new_curr = 'USD' if current_curr == 'INR' else 'INR'
        await query.answer("Currency updated!")

    conn.close()
    
    text = f"⚙️ **Settings**\n\nCurrent Currency: **{current_curr}**"
    buttons = [
        [InlineKeyboardButton(f"Switch to {new_curr}", callback_data=f'set_curr_{new_curr}')],
        [InlineKeyboardButton("🔙 Back", callback_data='main_menu')]
    ]
    
    if query.data == 'menu_settings':
         await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    else:
         await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def show_orders(update: Update, context: ContextTypes.DEFAULT_TYPE, active_only=True):
    user_id = update.effective_user.id
    conn = get_db_connection()
    if active_only:
        orders = conn.execute("SELECT * FROM orders WHERE user_id = ? AND status NOT IN ('Delivered', 'Cancelled') ORDER BY timestamp DESC", (user_id,)).fetchall()
        title = "📦 Active Orders"
    else:
        orders = conn.execute("SELECT * FROM orders WHERE user_id = ? ORDER BY timestamp DESC", (user_id,)).fetchall()
        title = "📜 Order History"
    
    text = f"**{title}**\n\n"
    if not orders:
        text += "No orders found."
    
    buttons = [[InlineKeyboardButton("🔙 Back", callback_data='main_menu')]]
    
    for o in orders:
        text += (
            f"🆔 `{o['order_id']}`\n"
            f"📦 Item Code: `{o['product_code']}`\n"
            f"📊 Status: **{o['status']}**\n"
            f"📅 Date: {o['timestamp']}\n"
        )
        if active_only and o['status'] == 'Pending':
             buttons.insert(0, [InlineKeyboardButton(f"❌ Cancel {o['order_id']}", callback_data=f"usr_can_{o['order_id']}")])
        text += "-------------------\n"
    
    conn.close()
    await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def user_cancel_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    order_id = query.data.split('_')[-1]
    conn = get_db_connection()
    order = conn.execute("SELECT status FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    
    if order and order['status'] == 'Pending':
        conn.execute("UPDATE orders SET status = 'Cancelled' WHERE order_id = ?", (order_id,))
        conn.commit()
        await query.answer("Order Cancelled")
        await show_orders(update, context, active_only=True)
        # Notify Admin
        await context.bot.send_message(chat_id=ADMIN_ID, text=f"⚠️ User cancelled order `{order_id}`", parse_mode='Markdown')
    else:
        await query.answer("Cannot cancel this order anymore.", show_alert=True)
    conn.close()

# ================= ADMIN PANEL & LOGIC =================

async def show_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [
        [InlineKeyboardButton("➕ Add New Item", callback_data='adm_add_item')],
        [InlineKeyboardButton("📋 Listed Items", callback_data='adm_list_items_0')],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data='adm_pending')],
        [InlineKeyboardButton("🗑️ Delist Item", callback_data='adm_delist_prompt')]
    ]
    await update.callback_query.edit_message_text("🔒 **Admin Control Panel**", parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# --- Add Item Conversation ---
async def add_item_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text("📝 Enter Product Name:")
    return ADD_NAME

async def add_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_item'] = {'name': update.message.text}
    await update.message.reply_text("💰 Enter Original Price (INR):")
    return ADD_ORIG_PRICE

async def add_orig_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_item']['orig_price'] = float(update.message.text)
    await update.message.reply_text("🏷️ Enter Discounted Price (INR):")
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    price = float(update.message.text)
    orig = context.user_data['new_item']['orig_price']
    discount = round(((orig - price) / orig) * 100, 1)
    context.user_data['new_item']['price'] = price
    context.user_data['new_item']['discount'] = discount
    await update.message.reply_text("💳 Enter Payment Methods (e.g., UPI, Card, COD):")
    return ADD_PAYMENT

async def add_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_item']['methods'] = update.message.text
    await update.message.reply_text("📍 Enter Delivery Location/Availability:")
    return ADD_LOC

async def add_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['new_item']['loc'] = update.message.text
    await update.message.reply_text("🖼️ Send Product Image (or type /skip):")
    return ADD_IMG

async def add_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = context.user_data['new_item']
    img_id = None
    if update.message.photo:
        img_id = update.message.photo[-1].file_id
    
    code = generate_unique_code()
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (code, name, original_price, price, discount, payment_methods, location, availability, image_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (code, item['name'], item['orig_price'], item['price'], item['discount'], item['methods'], item['loc'], 1, img_id)
    )
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        f"✅ **Product Added!**\nCode: `{code}`\nName: {item['name']}",
        parse_mode='Markdown'
    )
    return ConversationHandler.END

async def add_skip_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Same as above but img_id is None
    item = context.user_data['new_item']
    code = generate_unique_code()
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (code, name, original_price, price, discount, payment_methods, location, availability, image_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (code, item['name'], item['orig_price'], item['price'], item['discount'], item['methods'], item['loc'], 1, None)
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ **Product Added (No Image)!**\nCode: `{code}`", parse_mode='Markdown')
    return ConversationHandler.END

# --- Admin Order Management ---
async def admin_handle_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    action, order_id = data.split('_')[1], data.split('_')[2]
    
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    
    if not order:
        await query.answer("Order not found")
        conn.close()
        return

    if action == 'acc':
        new_status = 'Accepted'
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
        conn.commit()
        await context.bot.send_message(chat_id=order['user_id'], text=f"✅ Your order `{order_id}` has been **Accepted**!", parse_mode='Markdown')
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n✅ ACCEPTED") if query.message.caption else await query.edit_message_text(f"{query.message.text}\n\n✅ ACCEPTED")
    
    elif action == 'can':
        new_status = 'Cancelled'
        conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
        conn.commit()
        await context.bot.send_message(chat_id=order['user_id'], text=f"❌ Your order `{order_id}` has been **Cancelled** by admin.", parse_mode='Markdown')
        await query.edit_message_caption(caption=f"{query.message.caption}\n\n❌ CANCELLED") if query.message.caption else await query.edit_message_text(f"{query.message.text}\n\n❌ CANCELLED")

    conn.close()
    await query.answer()

async def admin_delist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Usage: /delist <code>")
        return
    
    code = context.args[0]
    conn = get_db_connection()
    conn.execute("DELETE FROM products WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    await update.message.reply_text(f"🗑️ Product `{code}` removed.", parse_mode='Markdown')

# ================= MAIN APP SETUP =================

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    # Conversations
    conv_add_item = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_item_start, pattern='adm_add_item')],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name)],
            ADD_ORIG_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_orig_price)],
            ADD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_PAYMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_payment)],
            ADD_LOC: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_loc)],
            ADD_IMG: [MessageHandler(filters.PHOTO, add_img), CommandHandler('skip', add_skip_img)],
        },
        fallbacks=[CommandHandler('cancel', start)]
    )

    conv_buy = ConversationHandler(
        entry_points=[
            CommandHandler('buy', buy_start),
            CallbackQueryHandler(buy_start, pattern='^buy_start_')
        ],
        states={
            BUY_CONFIRM: [CallbackQueryHandler(buy_confirm, pattern='^(buy_confirm|buy_cancel)$')],
            BUY_ADDRESS_CHOICE: [CallbackQueryHandler(buy_address_choice, pattern='^addr_')],
            BUY_ADDRESS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, buy_address_input)],
            BUY_PAYMENT: [CallbackQueryHandler(buy_payment, pattern='^pay_')]
        },
        fallbacks=[CommandHandler('cancel', start)]
    )

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", product_info_command))
    
    # Admin Commands
    application.add_handler(CommandHandler("delist", admin_delist_command))

    # Conversation Handlers
    application.add_handler(conv_add_item)
    application.add_handler(conv_buy)

    # Callback Handlers
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^menu_|^admin_panel'))
    application.add_handler(CallbackQueryHandler(show_settings, pattern='^set_curr_'))
    application.add_handler(CallbackQueryHandler(user_cancel_order, pattern='^usr_can_'))
    application.add_handler(CallbackQueryHandler(admin_handle_order, pattern='^adm_(acc|can)_'))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()