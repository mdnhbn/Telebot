# main.py

import sqlite3
import logging
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from functools import wraps

# --- কনফিগারেশন (এই অংশগুলো আপনার তথ্য দিয়ে পূরণ করুন) ---
TELEGRAM_BOT_TOKEN = "YOUR_HTTP_API_TOKEN_HERE"  # এখানে আপনার বট টোকেন দিন
ADMIN_ID = 123456789  # এখানে আপনার নিজের টেলিগ্রাম ইউজার আইডি দিন

# --- Conversation Handler States ---
(ASK_WALLET_SETUP, ASK_BROADCAST_MSG, ASK_USER_ID_MANAGE, ASK_POINTS_ADD,
 ASK_POINTS_SUB, ASK_MIN_WITHDRAW, ASK_MAX_WITHDRAW, ASK_REFER_BONUS,
 ASK_DAILY_BONUS, ASK_JOIN_CHANNEL, ASK_XROCKET_API, ASK_BAN_USER, ASK_UNBAN_USER) = range(13)

# --- Logging Setup ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Database Functions ---
def db_connect():
    return sqlite3.connect("super_bot.db", check_same_thread=False)

def setup_database():
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, first_name TEXT, username TEXT, points INTEGER DEFAULT 0,
        wallet_address TEXT, is_verified BOOLEAN DEFAULT FALSE, is_banned BOOLEAN DEFAULT FALSE,
        referred_by INTEGER, last_bonus_claim DATE
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)
    """)
    # Default settings matching the video's panel
    default_settings = {
        'maintenance_mode': 'off', 'bot_status': 'on', 'withdraw_status': 'on',
        'withdraw_conformation': 'on', 'captcha_verification': 'on',
        'min_withdraw': '1000', 'max_withdraw': '10000', 'withdraw_tax': '5',
        'bot_currency': 'POINTS', 'payout_currency': 'XROCK', 'refer_bonus': '50',
        'daily_bonus': '10', 'joining_channels': '', 'xrocket_api_key': 'Not Set',
        'home_text': 'Welcome to our amazing bot!', 'new_user_notification': 'on'
    }
    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def set_setting(key, value):
    conn = db_connect()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

# --- Decorators for security and control ---
def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("⛔️ You are not authorized for this command.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def maintenance_check(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if get_setting('maintenance_mode') == 'on' and update.effective_user.id != ADMIN_ID:
            await update.message.reply_text("🛠️ The bot is currently under maintenance. Please try again later.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- Admin Panel UI Function (replicates the video) ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Fetch all settings to display current status
    settings = {row[0]: row[1] for row in db_connect().cursor().execute("SELECT key, value FROM settings").fetchall()}

    def get_status_icon(key, on_val='on', off_val='off'):
        return "✅" if settings.get(key) == on_val else "❌"

    text = (
        f"👑 *Welcome To Admin Panel*\n\n"
        f"📋 *Review Bot Details*:\n"
        f"  Main Owner ~ `{ADMIN_ID}`\n"
        f"  Bot ON/OFF ~ {get_status_icon('bot_status', 'on', 'off')} {'Active' if settings.get('bot_status') == 'on' else 'Disabled'}\n"
        f"  Maintenance ON/OFF ~ {get_status_icon('maintenance_mode', 'on', 'off')} {'Active' if settings.get('maintenance_mode') == 'on' else 'Inactive'}\n\n"
        f"⚙️ *General Settings*:\n"
        f"  Withdraw Mode ~ {get_status_icon('withdraw_status')} {'Active' if settings.get('withdraw_status') == 'on' else 'Disabled'}\n"
        f"  Withdraw Conformation ~ {get_status_icon('withdraw_conformation')} {'Active' if settings.get('withdraw_conformation') == 'on' else 'Disabled'}\n"
        f"  Captcha Verification ~ {get_status_icon('captcha_verification')} {'Active' if settings.get('captcha_verification') == 'on' else 'Disabled'}\n\n"
        f"💰 *Financial Settings*:\n"
        f"  Minimum Withdraw ~ *{settings.get('min_withdraw')}*\n"
        f"  Maximum Withdraw ~ *{settings.get('max_withdraw')}*\n"
        f"  Withdraw Tax Amount ~ *{settings.get('withdraw_tax')}%*\n"
        f"  Bot Currency ~ *{settings.get('bot_currency')}*\n"
        f"  Payout Currency ~ *{settings.get('payout_currency')}*\n\n"
        f"🎁 *Bonus & Referral*:\n"
        f"  Per Refer Amount ~ *{settings.get('refer_bonus')}*\n"
        f"  Daily Bonus Amount ~ *{settings.get('daily_bonus')}*\n\n"
        f"🔑 *API & Integration*:\n"
        f"  Home Text ~ {'Set' if settings.get('home_text') else 'Not Set'}\n"
        f"  xRocket API Key Is ~ {'✅ Set' if settings.get('xrocket_api_key') != 'Not Set' else '❌ Not Set'}"
    )

    # Replicating the button layout from the video
    keyboard = [
        # First Row Group
        [InlineKeyboardButton("🔄 Transfer Ownership", callback_data='admin_transfer_owner'), InlineKeyboardButton("💸 Set Withdraw Tax", callback_data='admin_set_tax')],
        [InlineKeyboardButton(f"{get_status_icon('captcha_verification')} Captcha Verification", callback_data='admin_toggle_captcha')],
        # Second Row Group
        [InlineKeyboardButton("➕ Add Admin", callback_data='admin_add_admin'), InlineKeyboardButton("➖ Remove Admin", callback_data='admin_remove_admin')],
        [InlineKeyboardButton(f"{get_status_icon('bot_status')} Bot Status", callback_data='admin_toggle_bot_status')],
        # Third Row Group
        [InlineKeyboardButton("🚫 Ban User", callback_data='admin_ban_user'), InlineKeyboardButton("✅ Unban User", callback_data='admin_unban_user')],
        [InlineKeyboardButton(f"{get_status_icon('maintenance_mode')} Maintenance Mode", callback_data='admin_toggle_maintenance')],
        # Fourth Row Group
        [InlineKeyboardButton("🔗 Set Joining Channel", callback_data='admin_set_join_channel'), InlineKeyboardButton("🔍 Set Check Channel", callback_data='admin_set_check_channel')],
        [InlineKeyboardButton(f"{get_status_icon('withdraw_status')} Withdraw Status", callback_data='admin_toggle_withdraw_status')],
        [InlineKeyboardButton("🗑️ Remove Joining Channel", callback_data='admin_remove_join_channel'), InlineKeyboardButton("🗑️ Remove Check Channel", callback_data='admin_remove_check_channel')],
        # Fifth Row Group
        [InlineKeyboardButton("👥 Set Per Referer", callback_data='admin_set_refer_bonus'), InlineKeyboardButton("➕ Add Balance", callback_data='admin_add_balance')],
        [InlineKeyboardButton("➖ Remove Balance", callback_data='admin_remove_balance'), InlineKeyboardButton("💰 Set Minimum Withdraw", callback_data='admin_set_min_withdraw')],
        [InlineKeyboardButton("📢 Broadcast", callback_data='admin_broadcast'), InlineKeyboardButton("💬 Talk With User", callback_data='admin_talk_user')],
        [InlineKeyboardButton("💰 Set Maximum Withdraw", callback_data='admin_set_max_withdraw')],
        # Sixth Row Group
        [InlineKeyboardButton("💵 Set Payout Currency", callback_data='admin_set_payout_currency'), InlineKeyboardButton("🪙 Set Bot Currency", callback_data='admin_set_bot_currency')],
        [InlineKeyboardButton(f"{get_status_icon('withdraw_conformation')} Withdraw Conformation", callback_data='admin_toggle_withdraw_conformation')],
        # Seventh Row Group
        [InlineKeyboardButton("🔎 Find User Details", callback_data='admin_find_user'), InlineKeyboardButton("📋 Withdraw Chat Id", callback_data='admin_withdraw_chat_id')],
        [InlineKeyboardButton("🛡️ Add/Remove Admins Permission", callback_data='admin_manage_permissions')],
        # Eighth Row Group
        [InlineKeyboardButton("🔑 Set Api Key", callback_data='admin_set_api_key'), InlineKeyboardButton("📝 Set Home Text", callback_data='admin_set_home_text')],
        [InlineKeyboardButton("🎁 Set Daily Bonus", callback_data='admin_set_daily_bonus')],
        # Ninth Row Group
        [InlineKeyboardButton("📋 Get Admin List", callback_data='admin_get_admin_list'), InlineKeyboardButton("📜 Check Ban List", callback_data='admin_check_ban_list')],
        [InlineKeyboardButton(f"{get_status_icon('new_user_notification')} New User Notification", callback_data='admin_toggle_new_user_notification')],
    ]

    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')

# This handler will manage all admin button clicks
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data.split('_', 1)[1]
    
    # Toggle functions
    toggle_map = {
        'toggle_maintenance': 'maintenance_mode', 'toggle_bot_status': 'bot_status',
        'toggle_withdraw_status': 'withdraw_status', 'toggle_withdraw_conformation': 'withdraw_conformation',
        'toggle_captcha': 'captcha_verification', 'toggle_new_user_notification': 'new_user_notification'
    }
    
    if action in toggle_map:
        key = toggle_map[action]
        current_val = get_setting(key)
        new_val = 'off' if current_val == 'on' else 'on'
        set_setting(key, new_val)
        await query.message.reply_text(f"✅ *{key.replace('_', ' ').title()}* has been set to *{new_val.upper()}*.", parse_mode='Markdown')
        # Refresh the admin panel to show the change
        # A bit of a workaround to call an async function from a regular one
        await admin_panel(query.message, context)
        return

    # Set value functions (will trigger ConversationHandler)
    # This is a simplified example for one function, others will follow this pattern
    if action == "set_min_withdraw":
        await query.message.reply_text("Please enter the new minimum withdrawal amount:")
        return ASK_MIN_WITHDRAW
    
    elif action == "set_api_key":
        await query.message.reply_text("Please provide your xRocket API Key:")
        return ASK_XROCKET_API

# Conversation handler for setting minimum withdraw
async def handle_set_min_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        set_setting('min_withdraw', amount)
        await update.message.reply_text(f"✅ Minimum withdrawal amount has been set to *{amount}*.", parse_mode='Markdown')
        await admin_panel(update.message, context) # Show updated panel
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ Invalid amount. Please enter a number.")
        return ASK_MIN_WITHDRAW

async def handle_set_xrocket_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_key = update.message.text
    set_setting('xrocket_api_key', api_key)
    await update.message.reply_text(f"✅ xRocket API Key has been set.", parse_mode='Markdown')
    await admin_panel(update.message, context)
    return ConversationHandler.END

# Fallback/Cancel function
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# --- Main Bot Logic (Simplified User Flow) ---
@maintenance_check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Simplified start message for this example
    await update.message.reply_text(f"Welcome, {user.first_name}! This is the user side of the bot.")

# Main function to run the bot
def main() -> None:
    setup_database()
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Conversation handler for admin settings
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_callback_handler)],
        states={
            ASK_MIN_WITHDRAW: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_min_withdraw)],
            ASK_XROCKET_API: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_set_xrocket_api)],
            # ... add other states for all other setting functions
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False,
    )

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('adminpanel', admin_panel)) # Match the video's command
    application.add_handler(conv_handler)
    
    # Run the bot
    application.run_polling()

if __name__ == "__main__":
    main()
