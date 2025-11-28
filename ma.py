import logging
import sqlite3
import uuid
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters, ConversationHandler
)

# ================= CONFIGURATION =================
# ⚠️ IMPORTANT: Replace these values with your own before running!
# Do NOT commit your actual bot token to version control
TOKEN = '7582434551:AAHyyRt0P24dGWa2mZ5AXdTeNBqeI-eLmCo'  # <--- REPLACE WITH YOUR BOT TOKEN
ADMIN_ID = 6518582583           # <--- REPLACE WITH YOUR TELEGRAM ID
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
# Admin States
DELIST_CODE, CANCEL_REASON, UPDATE_STATUS = range(3)
# Profile Address Update
PROFILE_ADDRESS = range(1)

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
        "🎯 Your one-stop destination for premium products and services!\n\n"
        "✨ **What we offer:**\n"
        "• 🛍️ Exclusive products at unbeatable prices\n"
        "• 💳 Multiple payment options (COD & Online)\n"
        "• 🚚 Fast & reliable delivery\n"
        "• 📊 Real-time order tracking\n"
        "• 💱 Multi-currency support (INR/USD)\n\n"
        "👇 **Navigate using the buttons below to start shopping!**"
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
    user_id = update.effective_user.id
    is_admin = (user_id == ADMIN_ID)
    
    text = (
        "🤖 **Bot Help & Commands**\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "**📱 User Commands:**\n\n"
        "• `/start` - Open the main menu and start shopping\n"
        "• `/info <product_code>` - Get detailed information about a product with image\n"
        "• `/buy <product_code>` - Start purchasing a product\n"
        "• `/help` - Show this help message\n\n"
        "**🛒 How to Shop:**\n"
        "1. Use 'Enter the Market' to browse products\n"
        "2. Copy the product code (tap on it)\n"
        "3. Use `/info <code>` for full details and images\n"
        "4. Use `/buy <code>` to place an order\n"
        "5. Track orders in 'Active Orders'\n\n"
        "**💡 Tips:**\n"
        "• Save your delivery address in Profile\n"
        "• Switch currency in Settings (INR/USD)\n"
        "• Cancel pending orders in Active Orders\n"
        "• View complete history in Order History\n\n"
        f"**💬 Support:** Contact {SUPPORT_USERNAME} for help\n"
    )
    
    if is_admin:
        text += (
            "\n━━━━━━━━━━━━━━━━━━━━\n"
            "**👑 ADMIN COMMANDS:**\n\n"
            "**Product Management:**\n"
            "• `/admin` - Open Admin Control Panel\n"
            "• `/delist <product_code>` - Remove a product from market\n\n"
            "**Order Management:**\n"
            "• `/accept <order_id>` - Accept a pending order\n"
            "• `/cancel <order_id>` - Cancel an order (requires reason)\n"
            "• `/status <order_id> <status>` - Update order status\n"
            "  Status options: Pending, Accepted, Out for Delivery, Delivered\n\n"
            "**User Management:**\n"
            "• `/users` - View all registered users\n"
            "• `/user <user_id>` - View user details and manage\n"
            "• `/ban <user_id>` - Ban a user from the bot\n"
            "• `/unban <user_id>` - Unban a user\n\n"
            "**Admin Panel Features:**\n"
            "• Add new products with images\n"
            "• View all listed items\n"
            "• Manage pending orders\n"
            "• Accept/reject orders with reasons\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

# ================= MENU CALLBACKS =================

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == 'main_menu':
        # Recreate start menu
        user = update.effective_user
        intro_text = (
            f"🌟 **Welcome to the Premium Market, {user.first_name}!** 🌟\n\n"
            "🎯 Your one-stop destination for premium products and services!\n\n"
            "✨ **What we offer:**\n"
            "• 🛍️ Exclusive products at unbeatable prices\n"
            "• 💳 Multiple payment options (COD & Online)\n"
            "• 🚚 Fast & reliable delivery\n"
            "• 📊 Real-time order tracking\n"
            "• 💱 Multi-currency support (INR/USD)\n\n"
            "👇 **Navigate using the buttons below to start shopping!**"
        )
        
        keyboard = [
            [InlineKeyboardButton("🛍️ Enter the Market", callback_data='menu_market_0')],
            [InlineKeyboardButton("👤 Profile", callback_data='menu_profile'), InlineKeyboardButton("📦 Active Orders", callback_data='menu_active')],
            [InlineKeyboardButton("📜 Order History", callback_data='menu_history')],
            [InlineKeyboardButton("⚙️ Settings", callback_data='menu_settings')]
        ]
        
        if user.id == ADMIN_ID:
            keyboard.append([InlineKeyboardButton("🔒 Admin Panel", callback_data='admin_panel')])

        await query.edit_message_text(intro_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        
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
    
    elif data == 'show_market_help':
        await show_market_help(update, context)
    
    elif data.startswith('adm_list_items_'):
        await admin_list_items(update, context)
    
    elif data.startswith('adm_pending_'):
        await admin_pending_orders(update, context)
    
    elif data.startswith('adm_all_orders_'):
        await admin_all_orders(update, context)
    
    elif data == 'adm_delist_prompt':
        await admin_delist_prompt(update, context)
    
    elif data.startswith('confirm_delist_'):
        await confirm_delist(update, context)
    
    elif data.startswith(('ban_', 'unban_')):
        await handle_ban_unban(update, context)
    
    elif data == 'finalize_product':
        await finalize_product(update, context)
    
    elif data.startswith('set_curr_'):
        await show_settings(update, context)
    
    elif data.startswith('usr_can_'):
        await user_cancel_order(update, context)
    
    elif data.startswith('adm_acc_') or data.startswith('adm_can_'):
        await admin_handle_order(update, context)
    
    elif data == 'update_address':
        # This is handled by conversation handler, so just pass
        pass

# Admin command handler
async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Access denied. Admin only.")
        return
    
    intro_text = "🔒 **Admin Control Panel**\n\nManage products, orders, and users."
    
    keyboard = [
        [InlineKeyboardButton("➕ Add New Item", callback_data='adm_add_item')],
        [InlineKeyboardButton("📋 Current Listed Items", callback_data='adm_list_items_0')],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data='adm_pending_0')],
        [InlineKeyboardButton("📦 All Placed Orders", callback_data='adm_all_orders_0')],
        [InlineKeyboardButton("🗑️ Delist Item", callback_data='adm_delist_prompt')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')]
    ]
    
    await update.message.reply_text(intro_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# ================= MARKET & PRODUCT LOGIC =================

async def show_market(update: Update, context: ContextTypes.DEFAULT_TYPE, page=0):
    ITEMS_PER_PAGE = 5
    offset = page * ITEMS_PER_PAGE
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products WHERE is_active = 1 LIMIT ? OFFSET ?", (ITEMS_PER_PAGE, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1").fetchone()[0]
    user_currency = get_user_currency(update.effective_user.id)
    conn.close()

    text = "🛒 **Available Products**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not products:
        text += "No products currently available.\nCheck back soon! 🔄"
    
    for p in products:
        price_display = format_price(p['price'], user_currency)
        orig_price_display = format_price(p['original_price'], user_currency)
        avail = "✅ Available" if p['availability'] else "❌ Out of Stock"
        text += (
            f"🔹 **{p['name']}**\n"
            f"💰 Price: {price_display}\n"
            f"🏷️ Original: {orig_price_display} (Save {p['discount']}%!)\n"
            f"📦 Status: {avail}\n"
            f"💳 Payment: {p['payment_methods']}\n"
            f"📋 Product Code: `{p['code']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )

    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'menu_market_{page-1}'))
    if (offset + ITEMS_PER_PAGE) < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f'menu_market_{page+1}'))
    if nav_row:
        buttons.append(nav_row)
    
    # Add Help button
    buttons.append([InlineKeyboardButton("❓ Help", callback_data='show_market_help')])
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')])
    
    try:
        await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    except Exception:
        await update.effective_message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def show_market_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "❓ **Shopping Help**\n\n"
        "**How to get product details:**\n"
        "Tap on a product code to copy it, then use:\n"
        "`/info <product_code>`\n\n"
        "This will show you:\n"
        "• Complete product information\n"
        "• Product image (if available)\n"
        "• Delivery locations\n"
        "• All payment options\n\n"
        "**How to buy:**\n"
        "Use `/buy <product_code>` to start ordering\n\n"
        f"**Need more help?**\nContact {SUPPORT_USERNAME}"
    )
    
    buttons = [[InlineKeyboardButton("🔙 Back to Market", callback_data='menu_market_0')]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def product_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ **Usage:** `/info <product_code>`\n\n"
            "**Example:** `/info ABC123XY`\n\n"
            "💡 Tap on a product code in the market to copy it!",
            parse_mode='Markdown'
        )
        return
    
    code = args[0]
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE code = ? AND is_active = 1", (code,)).fetchone()
    user_currency = get_user_currency(update.effective_user.id)
    conn.close()

    if not product:
        await update.message.reply_text("❌ Product not found or not available.")
        return

    details = (
        f"📦 **Complete Product Details**\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏷️ **Name:** {product['name']}\n"
        f"🆔 **Product Code:** `{product['code']}`\n\n"
        f"💰 **Pricing:**\n"
        f"• Current Price: {format_price(product['price'], user_currency)}\n"
        f"• Original Price: {format_price(product['original_price'], user_currency)}\n"
        f"• You Save: {product['discount']}% OFF\n\n"
        f"📍 **Delivery:** {product['location']}\n"
        f"💳 **Payment Methods:** {product['payment_methods']}\n"
        f"✅ **Availability:** {'In Stock ✅' if product['availability'] else 'Out of Stock ❌'}\n\n"
        f"**Ready to buy?** Use `/buy {product['code']}`"
    )

    buttons = [
        [InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_start_{product['code']}")],
        [InlineKeyboardButton("❓ Need Help?", callback_data='show_market_help')],
        [InlineKeyboardButton("🔙 Back to Market", callback_data='menu_market_0')]
    ]

    if product['image_id']:
        await update.message.reply_photo(
            product['image_id'], 
            caption=details, 
            parse_mode='Markdown', 
            reply_markup=InlineKeyboardMarkup(buttons)
        )
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
    
    total_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)).fetchone()[0]
    active_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status NOT IN ('Delivered', 'Cancelled')",
        (user_id,)
    ).fetchone()[0]
    completed_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status = 'Delivered'",
        (user_id,)
    ).fetchone()[0]
    conn.close()

    text = (
        f"👤 **My Profile**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📛 Name: {update.effective_user.full_name}\n"
        f"🆔 User ID: `{user_id}`\n"
        f"📅 Joined: {user['joined_date']}\n"
        f"💱 Currency: {user['currency']}\n\n"
        f"📊 **Order Statistics:**\n"
        f"📦 Total Orders: {total_orders}\n"
        f"⏳ Active Orders: {active_orders}\n"
        f"✅ Completed Orders: {completed_orders}\n\n"
        f"📍 **Delivery Address:**\n"
        f"{user['address'] if user['address'] else 'Not set'}"
    )
    
    buttons = [
        [InlineKeyboardButton("📍 Update Delivery Address", callback_data='update_address')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')]
    ]
    
    await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def update_address_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📝 Please enter your new delivery address:")
    return PROFILE_ADDRESS

async def update_address_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    conn.execute("UPDATE users SET address = ? WHERE user_id = ?", (address, user_id))
    conn.commit()
    conn.close()
    
    text = (
        f"✅ **Address Updated!**\n\n"
        f"Your new delivery address:\n{address}\n\n"
        f"This will be used for future orders."
    )
    
    buttons = [[InlineKeyboardButton("🔙 Back to Profile", callback_data='menu_profile')]]
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    
    return ConversationHandler.END

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
        orders = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? AND status NOT IN ('Delivered', 'Cancelled') ORDER BY timestamp DESC", 
            (user_id,)
        ).fetchall()
        title = "📦 Active Orders"
    else:
        orders = conn.execute(
            "SELECT * FROM orders WHERE user_id = ? ORDER BY timestamp DESC", 
            (user_id,)
        ).fetchall()
        title = "📜 Order History"
    
    status_emoji = {
        'Pending': '⏳',
        'Accepted': '✅',
        'Out for Delivery': '🚚',
        'Delivered': '📦',
        'Cancelled': '❌'
    }
    
    text = f"**{title}**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not orders:
        text += "No orders found.\n\n🛍️ Start shopping to see your orders here!"
    
    buttons = []
    
    for o in orders:
        product = conn.execute("SELECT name FROM products WHERE code = ?", (o['product_code'],)).fetchone()
        product_name = product['name'] if product else 'Product N/A'
        
        text += (
            f"{status_emoji.get(o['status'], '📋')} **{o['status']}**\n"
            f"🆔 Order ID: `{o['order_id']}`\n"
            f"📦 Product: {product_name}\n"
            f"💰 Price: ₹{o['price_at_time']} {o['currency']}\n"
            f"📅 Date: {o['timestamp']}\n"
        )
        
        if o['rejection_reason']:
            text += f"❌ Reason: {o['rejection_reason']}\n"
        
        # Add cancel button for pending orders in active view
        if active_only and o['status'] == 'Pending':
            buttons.append([InlineKeyboardButton(f"❌ Cancel Order {o['order_id']}", callback_data=f"usr_can_{o['order_id']}")])
        
        text += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    conn.close()
    
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')])
    
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
        [InlineKeyboardButton("📋 Current Listed Items", callback_data='adm_list_items_0')],
        [InlineKeyboardButton("⏳ Pending Orders", callback_data='adm_pending_0')],
        [InlineKeyboardButton("📦 All Placed Orders", callback_data='adm_all_orders_0')],
        [InlineKeyboardButton("🗑️ Delist Item", callback_data='adm_delist_prompt')],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data='main_menu')]
    ]
    
    text = (
        "🔒 **Admin Control Panel**\n\n"
        "Manage products, orders, and users from here.\n"
        "Select an option below:"
    )
    
    await update.callback_query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# Admin: View all listed items
async def admin_list_items(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split('_')[-1])
    
    ITEMS_PER_PAGE = 5
    offset = page * ITEMS_PER_PAGE
    
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM products WHERE is_active = 1 LIMIT ? OFFSET ?", (ITEMS_PER_PAGE, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM products WHERE is_active = 1").fetchone()[0]
    conn.close()
    
    text = "📋 **Listed Products**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not products:
        text += "No active products."
    
    for p in products:
        text += (
            f"**{p['name']}**\n"
            f"Code: `{p['code']}`\n"
            f"Price: ₹{p['price']} (Original: ₹{p['original_price']})\n"
            f"Discount: {p['discount']}%\n"
            f"Status: {'✅ Available' if p['availability'] else '❌ Unavailable'}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    
    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'adm_list_items_{page-1}'))
    if (offset + ITEMS_PER_PAGE) < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f'adm_list_items_{page+1}'))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# Admin: View pending orders
async def admin_pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split('_')[-1])
    
    ITEMS_PER_PAGE = 5
    offset = page * ITEMS_PER_PAGE
    
    conn = get_db_connection()
    orders = conn.execute(
        "SELECT * FROM orders WHERE status = 'Pending' ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (ITEMS_PER_PAGE, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM orders WHERE status = 'Pending'").fetchone()[0]
    conn.close()
    
    text = "⏳ **Pending Orders**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not orders:
        text += "No pending orders."
    
    for o in orders:
        conn = get_db_connection()
        user = conn.execute("SELECT username FROM users WHERE user_id = ?", (o['user_id'],)).fetchone()
        product = conn.execute("SELECT name FROM products WHERE code = ?", (o['product_code'],)).fetchone()
        conn.close()
        
        text += (
            f"🆔 Order: `{o['order_id']}`\n"
            f"👤 User: @{user['username'] or 'N/A'} ({o['user_id']})\n"
            f"📦 Product: {product['name'] if product else 'N/A'} (`{o['product_code']}`)\n"
            f"💰 Price: ₹{o['price_at_time']}\n"
            f"📍 Address: {o['delivery_address'][:30]}...\n"
            f"📅 Date: {o['timestamp']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    
    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'adm_pending_{page-1}'))
    if (offset + ITEMS_PER_PAGE) < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f'adm_pending_{page+1}'))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# Admin: View all orders
async def admin_all_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split('_')[-1])
    
    ITEMS_PER_PAGE = 5
    offset = page * ITEMS_PER_PAGE
    
    conn = get_db_connection()
    orders = conn.execute(
        "SELECT * FROM orders ORDER BY timestamp DESC LIMIT ? OFFSET ?",
        (ITEMS_PER_PAGE, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
    conn.close()
    
    text = "📦 **All Orders**\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not orders:
        text += "No orders yet."
    
    for o in orders:
        conn = get_db_connection()
        user = conn.execute("SELECT username FROM users WHERE user_id = ?", (o['user_id'],)).fetchone()
        conn.close()
        
        status_emoji = {
            'Pending': '⏳',
            'Accepted': '✅',
            'Out for Delivery': '🚚',
            'Delivered': '📦',
            'Cancelled': '❌'
        }
        
        text += (
            f"🆔 `{o['order_id']}`\n"
            f"👤 @{user['username'] or 'N/A'}\n"
            f"📊 Status: {status_emoji.get(o['status'], '📋')} {o['status']}\n"
            f"💰 ₹{o['price_at_time']}\n"
            f"📅 {o['timestamp']}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n\n"
        )
    
    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Previous", callback_data=f'adm_all_orders_{page-1}'))
    if (offset + ITEMS_PER_PAGE) < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f'adm_all_orders_{page+1}'))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')])
    
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# Admin: Delist item prompt
async def admin_delist_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    text = (
        "🗑️ **Delist a Product**\n\n"
        "To remove a product from the market, use:\n"
        "`/delist <product_code>`\n\n"
        "Example: `/delist ABC123XY`"
    )
    
    buttons = [[InlineKeyboardButton("🔙 Back to Admin Panel", callback_data='admin_panel')]]
    await query.edit_message_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

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
    
    # Show summary before finalizing
    summary = (
        f"📋 **Product Summary**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Name:** {item['name']}\n"
        f"**Original Price:** ₹{item['orig_price']}\n"
        f"**Your Price:** ₹{item['price']}\n"
        f"**Discount:** {item['discount']}%\n"
        f"**Payment Methods:** {item['methods']}\n"
        f"**Delivery Location:** {item['loc']}\n"
        f"**Image:** {'✅ Uploaded' if img_id else '❌ No image'}\n\n"
        f"Please confirm to add this product."
    )
    
    context.user_data['new_item']['image_id'] = img_id
    
    buttons = [
        [InlineKeyboardButton("✅ Finalize Adding", callback_data='finalize_product')],
        [InlineKeyboardButton("❌ Cancel", callback_data='admin_panel')]
    ]
    
    await update.message.reply_text(summary, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    return ConversationHandler.END

async def add_skip_img(update: Update, context: ContextTypes.DEFAULT_TYPE):
    item = context.user_data['new_item']
    
    # Show summary before finalizing
    summary = (
        f"📋 **Product Summary**\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Name:** {item['name']}\n"
        f"**Original Price:** ₹{item['orig_price']}\n"
        f"**Your Price:** ₹{item['price']}\n"
        f"**Discount:** {item['discount']}%\n"
        f"**Payment Methods:** {item['methods']}\n"
        f"**Delivery Location:** {item['loc']}\n"
        f"**Image:** ❌ No image\n\n"
        f"Please confirm to add this product."
    )
    
    context.user_data['new_item']['image_id'] = None
    
    buttons = [
        [InlineKeyboardButton("✅ Finalize Adding", callback_data='finalize_product')],
        [InlineKeyboardButton("❌ Cancel", callback_data='admin_panel')]
    ]
    
    await update.message.reply_text(summary, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))
    return ConversationHandler.END

async def finalize_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    item = context.user_data.get('new_item')
    if not item:
        await query.edit_message_text("❌ Error: Product data not found.")
        return
    
    code = generate_unique_code()
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO products (code, name, original_price, price, discount, payment_methods, location, availability, image_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (code, item['name'], item['orig_price'], item['price'], item['discount'], item['methods'], item['loc'], 1, item.get('image_id'))
    )
    conn.commit()
    conn.close()
    
    await query.edit_message_text(
        f"✅ **Product Added Successfully!**\n\n"
        f"📋 Product Code: `{code}`\n"
        f"🏷️ Name: {item['name']}\n"
        f"💰 Price: ₹{item['price']}\n\n"
        f"The product is now live in the market!",
        parse_mode='Markdown'
    )
    
    # Clear the user data
    context.user_data.pop('new_item', None)

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
    if update.effective_user.id != ADMIN_ID: 
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/delist <product_code>`", parse_mode='Markdown')
        return
    
    code = context.args[0]
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM products WHERE code = ?", (code,)).fetchone()
    
    if not product:
        await update.message.reply_text("❌ Product not found.", parse_mode='Markdown')
        conn.close()
        return
    
    # Show product details and ask for confirmation
    text = (
        f"🗑️ **Confirm Delisting**\n\n"
        f"Product: {product['name']}\n"
        f"Code: `{product['code']}`\n"
        f"Price: ₹{product['price']}\n\n"
        f"Are you sure you want to remove this item?"
    )
    
    buttons = [
        [InlineKeyboardButton("✅ Confirm Delist", callback_data=f'confirm_delist_{code}')],
        [InlineKeyboardButton("❌ Cancel", callback_data='admin_panel')]
    ]
    
    conn.close()
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

async def confirm_delist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    code = query.data.split('_')[-1]
    
    conn = get_db_connection()
    conn.execute("UPDATE products SET is_active = 0 WHERE code = ?", (code,))
    conn.commit()
    conn.close()
    
    await query.answer("Product delisted!")
    await query.edit_message_text(f"✅ Product `{code}` has been removed from the market.", parse_mode='Markdown')

# Admin: Quick Accept Order
async def admin_accept_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/accept <order_id>`", parse_mode='Markdown')
        return
    
    order_id = context.args[0]
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    
    if not order:
        await update.message.reply_text("❌ Order not found.")
        conn.close()
        return
    
    if order['status'] != 'Pending':
        await update.message.reply_text(f"⚠️ Order is already {order['status']}.")
        conn.close()
        return
    
    conn.execute("UPDATE orders SET status = 'Accepted' WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()
    
    # Notify user
    await context.bot.send_message(
        chat_id=order['user_id'],
        text=f"✅ **Order Accepted!**\n\nYour order `{order_id}` has been accepted by the market!\nYou can track it in Active Orders.",
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(f"✅ Order `{order_id}` accepted!", parse_mode='Markdown')

# Admin: Quick Cancel Order
async def admin_cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/cancel <order_id>`", parse_mode='Markdown')
        return
    
    order_id = context.args[0]
    context.user_data['cancel_order_id'] = order_id
    
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    conn.close()
    
    if not order:
        await update.message.reply_text("❌ Order not found.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        f"📝 Please provide a reason for cancelling order `{order_id}`:",
        parse_mode='Markdown'
    )
    return CANCEL_REASON

async def cancel_reason_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text
    order_id = context.user_data.get('cancel_order_id')
    
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    
    if order:
        conn.execute(
            "UPDATE orders SET status = 'Cancelled', rejection_reason = ? WHERE order_id = ?",
            (reason, order_id)
        )
        conn.commit()
        
        # Notify user
        await context.bot.send_message(
            chat_id=order['user_id'],
            text=(
                f"❌ **Order Cancelled**\n\n"
                f"Order ID: `{order_id}`\n"
                f"Reason: {reason}"
            ),
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(f"✅ Order `{order_id}` cancelled.", parse_mode='Markdown')
    
    conn.close()
    return ConversationHandler.END

# Admin: Update Order Status
async def admin_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Usage: `/status <order_id> <status>`\n\n"
            "Valid statuses:\n• Pending\n• Accepted\n• Out for Delivery\n• Delivered",
            parse_mode='Markdown'
        )
        return
    
    order_id = context.args[0]
    new_status = ' '.join(context.args[1:])
    
    valid_statuses = ['Pending', 'Accepted', 'Out for Delivery', 'Delivered', 'Cancelled']
    if new_status not in valid_statuses:
        await update.message.reply_text(f"❌ Invalid status. Choose from: {', '.join(valid_statuses)}")
        return
    
    conn = get_db_connection()
    order = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    
    if not order:
        await update.message.reply_text("❌ Order not found.")
        conn.close()
        return
    
    conn.execute("UPDATE orders SET status = ? WHERE order_id = ?", (new_status, order_id))
    conn.commit()
    conn.close()
    
    # Notify user
    status_emoji = {
        'Pending': '⏳',
        'Accepted': '✅',
        'Out for Delivery': '🚚',
        'Delivered': '📦',
        'Cancelled': '❌'
    }
    
    await context.bot.send_message(
        chat_id=order['user_id'],
        text=(
            f"{status_emoji.get(new_status, '📋')} **Order Status Updated**\n\n"
            f"Order ID: `{order_id}`\n"
            f"New Status: **{new_status}**"
        ),
        parse_mode='Markdown'
    )
    
    await update.message.reply_text(f"✅ Order `{order_id}` status updated to **{new_status}**", parse_mode='Markdown')

# Admin: List All Users
async def admin_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users ORDER BY joined_date DESC").fetchall()
    conn.close()
    
    if not users:
        await update.message.reply_text("📋 No users registered yet.")
        return
    
    text = "👥 **Registered Users**\n\n"
    for user in users:
        ban_status = "🚫 Banned" if user['is_banned'] else "✅ Active"
        text += (
            f"ID: `{user['user_id']}`\n"
            f"Username: @{user['username'] or 'N/A'}\n"
            f"Status: {ban_status}\n"
            f"Joined: {user['joined_date']}\n"
            f"━━━━━━━━━━━━━━\n"
        )
    
    await update.message.reply_text(text, parse_mode='Markdown')

# Admin: User Details and Management
async def admin_user_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/user <user_id>`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID. Must be a number.")
        return
    
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    
    if not user:
        await update.message.reply_text("❌ User not found.")
        conn.close()
        return
    
    # Get user statistics
    total_orders = conn.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,)).fetchone()[0]
    pending_orders = conn.execute(
        "SELECT COUNT(*) FROM orders WHERE user_id = ? AND status NOT IN ('Delivered', 'Cancelled')",
        (user_id,)
    ).fetchone()[0]
    conn.close()
    
    text = (
        f"👤 **User Details**\n\n"
        f"ID: `{user['user_id']}`\n"
        f"Username: @{user['username'] or 'N/A'}\n"
        f"Currency: {user['currency']}\n"
        f"Address: {user['address'] or 'Not set'}\n"
        f"Status: {'🚫 Banned' if user['is_banned'] else '✅ Active'}\n"
        f"Joined: {user['joined_date']}\n\n"
        f"📊 **Statistics:**\n"
        f"Total Orders: {total_orders}\n"
        f"Active Orders: {pending_orders}"
    )
    
    buttons = []
    if user['is_banned']:
        buttons.append([InlineKeyboardButton("✅ Unban User", callback_data=f'unban_{user_id}')])
    else:
        buttons.append([InlineKeyboardButton("🚫 Ban User", callback_data=f'ban_{user_id}')])
    
    buttons.append([InlineKeyboardButton("📜 View Order History", callback_data=f'admin_user_orders_{user_id}')])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data='admin_panel')])
    
    await update.message.reply_text(text, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(buttons))

# Admin: Ban User
async def admin_ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/ban <user_id>`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    conn = get_db_connection()
    conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"🚫 User `{user_id}` has been banned.", parse_mode='Markdown')

# Admin: Unban User
async def admin_unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("⚠️ Usage: `/unban <user_id>`", parse_mode='Markdown')
        return
    
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")
        return
    
    conn = get_db_connection()
    conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ User `{user_id}` has been unbanned.", parse_mode='Markdown')

# Callback handlers for ban/unban
async def handle_ban_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    
    conn = get_db_connection()
    if action == 'ban':
        conn.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        message = f"🚫 User `{user_id}` has been banned."
    else:  # unban
        conn.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        message = f"✅ User `{user_id}` has been unbanned."
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text(message, parse_mode='Markdown')

# ================= MAIN APP SETUP =================

def main():
    init_db()
    application = Application.builder().token(TOKEN).build()

    # Conversation Handlers
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

    conv_cancel_order = ConversationHandler(
        entry_points=[CommandHandler('cancel', admin_cancel_command)],
        states={
            CANCEL_REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, cancel_reason_handler)],
        },
        fallbacks=[CommandHandler('start', start)]
    )

    conv_update_address = ConversationHandler(
        entry_points=[CallbackQueryHandler(update_address_start, pattern='update_address')],
        states={
            PROFILE_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_address_save)],
        },
        fallbacks=[CommandHandler('start', start)]
    )

    # User Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", product_info_command))
    
    # Admin Command Handlers
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("delist", admin_delist_command))
    application.add_handler(CommandHandler("accept", admin_accept_command))
    application.add_handler(CommandHandler("status", admin_status_command))
    application.add_handler(CommandHandler("users", admin_users_command))
    application.add_handler(CommandHandler("user", admin_user_command))
    application.add_handler(CommandHandler("ban", admin_ban_command))
    application.add_handler(CommandHandler("unban", admin_unban_command))

    # Conversation Handlers
    application.add_handler(conv_add_item)
    application.add_handler(conv_buy)
    application.add_handler(conv_cancel_order)
    application.add_handler(conv_update_address)

    # Main Callback Handler (handles all callback queries with routing logic)
    application.add_handler(CallbackQueryHandler(main_menu_callback))

    print("🤖 Bot is running...")
    print(f"📊 Admin ID: {ADMIN_ID}")
    print(f"💬 Support: {SUPPORT_USERNAME}")
    application.run_polling()

if __name__ == '__main__':
    main()