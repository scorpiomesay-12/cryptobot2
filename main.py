import asyncio
import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from flask import Flask

# 1. የ Flask ሰርቨር (Render እንዳይተኛ የሚረዳ)
app = Flask(__name__)

@app.route('/')
def home():
    return "Crypto Exchange Bot with Database is alive and running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# 2. የቴሌግራም ቦት ማዋቀሪያ
TOKEN = "7870015707:AAEqqSaPXC-oxofRmMXF7TY6EMA56X61EnE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 3. የ SQLite ዳታቤዝ ማዋቀሪያ (Database Setup) ---
def init_db():
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            type TEXT,
            amount REAL,
            total_price REAL,
            payment_method TEXT,
            status TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# የምንዛሬ ዋጋዎች
BUY_RATE = 185.0   # 1 USDT የምትሸጥበት ዋጋ (በብር)
SELL_RATE = 170.0  # 1 USDT ከደንበኛ የምትገዛበት ዋጋ

# የክፍያ መረጃዎች
TELEBIRR_NUM = "0966868001"
CBE_NUM = "1000650255821"
BINANCE_UID = "893287919"
BYBIT_UID = "359670410"

# የስቴት ማስተካከያ
class OrderState(StatesGroup):
    waiting_for_buy_amount = State()
    waiting_for_buy_payment_method = State()
    waiting_for_buy_screenshot = State()
    waiting_for_sell_amount = State()
    waiting_for_sell_payment_method = State()
    waiting_for_sell_payout_details = State()

# ዋናው ሜኑ ኪቦርድ
def get_main_keyboard():
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="🟢 USDT ግዛ (Buy)"), types.KeyboardButton(text="🔴 USDT ሽጥ (Sell)")],
            [types.KeyboardButton(text="📊 የዛሬ ዋጋ (Rates)"), types.KeyboardButton(text="📜 የክፍያ ታሪክ (History)")],
            [types.KeyboardButton(text="📞 እገዛ (Support)")]
        ],
        resize_keyboard=True
    )

# /start ሲሉ የሚሰጠው ምላሽ
@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    await message.answer(
        "ሰላም! ወደ አዲሱ የ Crypto Exchange ቦት በሰላም መጡ።\nከታች ከሚገኙት አማራጮች አንዱን ይምረጡ፦",
        reply_markup=get_main_keyboard()
    )

# የዛሬውን ዋጋ ማሳየት
@dp.message(F.text == "📊 የዛሬ ዋጋ (Rates)")
async def show_rates(message: types.Message):
    text = (
        f"📊 **የዛሬው የ USDT ምንዛሬ ዋጋዎች፦**\n\n"
        f"🟢 ለመግዛት (Buy Rate): **1 USDT = {BUY_RATE} ETB**\n"
        f"🔴 ለመሸጥ (Sell Rate): **1 USDT = {SELL_RATE} ETB**\n\n"
        f"💡 **የግዢ/ሽያጭ ገደብ:** ዝቅተኛው $0.1 እስከ ከፍተኛው $10 ነው።"
    )
    await message.answer(text, parse_mode="Markdown")


# ==================== 📜 የክፍያ ታሪክ (Payment History) ====================
@dp.message(F.text == "📜 የክፍያ ታሪክ (History)")
async def show_history(message: types.Message):
    user_id = message.from_user.id
    
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT type, amount, total_price, payment_method, status FROM transactions WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        await message.answer("ትኩረት፡ እስካሁን የተመዘገበ የግብይት ታሪክ የለዎትም።")
        return
    
    history_text = "📜 **የእርስዎ የግብይት ታሪኮች፦**\n\n"
    for idx, row in enumerate(rows, 1):
        t_type, amount, total_price, pay_method, status = row
        history_text += (
            f"{idx}. **{t_type}**\n"
            f"   • መጠን: {amount} USDT ({total_price} ETB)\n"
            f"   • ክፍያ ዘዴ: {pay_method}\n"
            f"   • ሁኔታ (Status): {status}\n\n"
        )
    
    await message.answer(history_text, parse_mode="Markdown")


# ==================== 🟢 የግዢ (BUY) ሂደት ====================

@dp.message(F.text == "🟢 USDT ግዛ (Buy)")
async def buy_usdt(message: types.Message, state: FSMContext):
    await message.answer(
        "🟢 **USDT ለመግዛት፦**\n\n"
        "እባክዎ መግዛት የሚፈልጉትን የ **USDT መጠን** ያስገቡ (ለምሳሌ፦ `1`, `5`, ወይም `0.5`)\n"
        "⚠️ *ገደብ: ከ $0.1 እስከ $10*"
    )
    await state.set_state(OrderState.waiting_for_buy_amount)

@dp.message(OrderState.waiting_for_buy_amount, F.text)
async def process_buy_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < 0.1 or amount > 10.0:
            await message.answer("⚠️ ይቅርታ! ዝቅተኛው የግዢ መጠን $0.1 ሲሆን፣ ከፍተኛው ደግሞ $10 ነው። እባክዎ ትክክለኛ መጠን ያስገቡ።")
            return
        
        total_price = amount * BUY_RATE
        await state.update_data(buy_amount=amount, total_price=total_price)
        
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="📱 Telebirr"), types.KeyboardButton(text="🏦 CBE (የንግድ ባንክ)")],
                [types.KeyboardButton(text="🟡 Binance UID"), types.KeyboardButton(text="🟣 Bybit UID")]
            ],
            resize_keyboard=True
        )
        
        text = (
            f"🛒 **የግዢ ማጠቃለያ፦**\n"
            f"• የሚገዙት: **{amount} USDT**\n"
            f"• የሚከፍሉት: **{total_price} ETB**\n\n"
            f"💳 እባክዎ ለመክፈል የሚፈልጉትን **የክፍያ አማራጭ** ከታች ካሉት ይምረጡ፦"
        )
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(OrderState.waiting_for_buy_payment_method)
        
    except ValueError:
        await message.answer("⚠️ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ (ለምሳሌ፦ 2 ወይም 3.5)")

@dp.message(OrderState.waiting_for_buy_payment_method, F.text.in_(["📱 Telebirr", "🏦 CBE (የንግድ ባንክ)", "🟡 Binance UID", "🟣 Bybit UID"]))
async def process_buy_payment_choice(message: types.Message, state: FSMContext):
    choice = message.text
    await state.update_data(payment_method=choice)
    data = await state.get_data()
    total_price = data.get("total_price")
    
    if "Telebirr" in choice:
        payment_info = f"📱 **Telebirr ቁጥር:** `{TELEBIRR_NUM}`\n💰 የሚከፍሉት መጠን: **{total_price} ETB**"
    elif "CBE" in choice:
        payment_info = f"🏦 **CBE አውንት:** `{CBE_NUM}`\n💰 የሚከፍሉት መጠን: **{total_price} ETB**"
    elif "Binance" in choice:
        payment_info = f"🟡 **Binance UID:** `{BINANCE_UID}`"
    elif "Bybit" in choice:
        payment_info = f"🟣 **Bybit UID:** `{BYBIT_UID}`"
        
    text = (
        f"{payment_info}\n\n"
        f"📸 እባክዎ ገንዘቡን ከላኩ በኋላ የክፍያ ማረጋገጫ **ስክሪንሾት (Screenshot)** ፎቶ በዚህ ቦት ላይ ይላኩ።"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=get_main_keyboard())
    await state.set_state(OrderState.waiting_for_buy_screenshot)

@dp.message(OrderState.waiting_for_buy_screenshot, F.photo)
async def handle_buy_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    amount = data.get("buy_amount")
    total_price = data.get("total_price")
    payment_method = data.get("payment_method")
    
    # ዳታቤዝ ውስጥ ትዕዛዙን እንመዝገባለን (Pending status)
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, username, type, amount, total_price, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, "ግዢ (Buy)", amount, total_price, payment_method, "በሂደት ላይ (Pending)"))
    conn.commit()
    conn.close()
    
    await message.answer("✅ ስክሪንሾትዎ ደርሷል! ትዕዛዝዎ ተመዝግቧል። 'የክፍያ ታሪክ' በመጫን ማየት ይችላሉ።")
    await state.clear()

@dp.message(OrderState.waiting_for_buy_screenshot)
async def wrong_buy_screenshot(message: types.Message):
    await message.answer("⚠️ እባክዎ የባንክ ክፍያ ማረጋገጫ **ስክሪንሾት (Photo)** ፎቶ ብቻ ይላኩ።")


# ==================== 🔴 የሽያጭ (SELL) ሂደት ====================

@dp.message(F.text == "🔴 USDT ሽጥ (Sell)")
async def sell_usdt(message: types.Message, state: FSMContext):
    await message.answer(
        "🔴 **USDT ለመሸጥ፦**\n\n"
        "እባክዎ መሸጥ የሚፈልጉትን የ **USDT መጠን** ያስገቡ\n"
        "⚠️ *ገደብ: ከ $0.1 እስከ $10*"
    )
    await state.set_state(OrderState.waiting_for_sell_amount)

@dp.message(OrderState.waiting_for_sell_amount, F.text)
async def process_sell_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount < 0.1 or amount > 10.0:
            await message.answer("⚠️ ይቅርታ! ዝቅተኛው የሽያጭ መጠን $0.1 ሲሆን፣ ከፍተኛው ደግሞ $10 ነው። እባክዎ ትክክለኛ መጠን ያስገቡ።")
            return
        
        total_payout = amount * SELL_RATE
        await state.update_data(sell_amount=amount, total_payout=total_payout)
        
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="📱 Telebirr (መቀበያ)"), types.KeyboardButton(text="🏦 CBE (መቀበያ)")],
                [types.KeyboardButton(text="🟡 Binance UID (መቀበያ)"), types.KeyboardButton(text="🟣 Bybit UID (መቀበያ)")]
            ],
            resize_keyboard=True
        )
        
        text = (
            f"📤 **የሽያጭ ማጠቃለያ፦**\n"
            f"• የሚሸጡት: **{amount} USDT**\n"
            f"• የሚቀበሉት: **{total_payout} ETB**\n\n"
            f"💸 ገንዘቡን በየትኛው አካውንት መቀበል ይፈልጋሉ?"
        )
        await message.answer(text, reply_markup=keyboard)
        await state.set_state(OrderState.waiting_for_sell_payment_method)
        
    except ValueError:
        await message.answer("⚠️ እባክዎ ትክክለኛ ቁጥር ብቻ ያስገቡ።")

@dp.message(OrderState.waiting_for_sell_payment_method, F.text)
async def process_sell_payout_choice(message: types.Message, state: FSMContext):
    choice = message.text
    await state.update_data(payout_method=choice)
    
    await message.answer(
        f"✍️ እባክዎ ገንዘቡ የሚገባልዎትን **የሂሳብ ቁጥር**፣ **የባንክ ስም** እና **የባለቤቱን ስም** (ወይም የክሪፕቶ ዩአይዲዎን UID) ይጻፉልን።",
        reply_markup=get_main_keyboard()
    )
    await state.set_state(OrderState.waiting_for_sell_payout_details)

@dp.message(OrderState.waiting_for_sell_payout_details, F.text)
async def finalize_sell_order(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or "No Username"
    amount = data.get("sell_amount")
    total_payout = data.get("total_payout")
    payout_method = data.get("payout_method")
    
    # ዳታቤዝ ውስጥ የሽያጭ ትዕዛዙን እንመዝገባለን
    conn = sqlite3.connect("bot_database.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO transactions (user_id, username, type, amount, total_price, payment_method, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, "ሽያጭ (Sell)", amount, total_payout, payout_method, "በሂደት ላይ (Pending)"))
    conn.commit()
    conn.close()
    
    await message.answer(
        "✅ የሽያጭ ጥያቄዎ እና የባንክ መረጃዎ ተመዝግቧል!\n"
        "እባክዎ ትዕዛዝዎ እስኪረጋገጥ በትዕግስት ይጠብቁ። 'የክፍያ ታሪክ' በመጫን መከታተል ይችላሉ።"
    )
    await state.clear()


# ዋናው የማስኬጃ ሉፕ
async def main():
    import threading
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())