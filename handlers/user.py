import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db
from config import ADMIN_IDS  # Adminlarga xabar yuborish uchun ID lar import qilinadi

router = Router()
PAGE_SIZE = 5

class Search(StatesGroup):
    waiting_for_query = State()

class ContactAdmin(StatesGroup):
    waiting_for_message = State()


# ---------- MIDDLEWARE (BAN VA MAJBURIY OBUNANI TEKSHIRISH) ----------

@router.message.outer_middleware()
@router.callback_query.outer_middleware()
async def check_ban_and_sub_middleware(handler, event, data):
    user_id = event.from_user.id
    bot: Bot = data.get("bot")

    # 1. Ban qilinganligini tekshirish
    try:
        if await db.is_banned(user_id):
            if isinstance(event, Message):
                await event.answer("🚫 Siz botdan foydalanishdan mahrum qilingansiz.")
            elif isinstance(event, CallbackQuery):
                await event.answer("🚫 Siz bloklangansiz.", show_alert=True)
            return
    except Exception as e:
        logging.error(f"Ban tekshirishda xatolik: {e}")

    # "check_sub" tugmasi bosilsa, pastki tekshiruvga tushmasligi kerak
    if isinstance(event, CallbackQuery) and event.data == "check_sub":
        return await handler(event, data)

    # 2. Majburiy obunani tekshirish
    try:
        channel = await db.get_setting("force_sub_channel")
        if channel:
            member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'creator', 'administrator', 'restricted']:
                
                builder = InlineKeyboardBuilder()
                # URL shaklini to'g'rilash (masalan, @kanal_username -> t.me/kanal_username)
                url = f"https://t.me/{channel.replace('@', '')}" if "@" in channel else channel
                
                builder.button(text="📢 Kanalga obuna bo'lish", url=url)
                builder.button(text="✅ Tasdiqlash", callback_data="check_sub")
                builder.adjust(1)
                
                msg_text = "❌ Botdan foydalanish uchun avval quyidagi kanalga obuna bo'lishingiz kerak:"
                
                if isinstance(event, Message):
                    await event.answer(msg_text, reply_markup=builder.as_markup())
                elif isinstance(event, CallbackQuery):
                    await event.message.answer(msg_text, reply_markup=builder.as_markup())
                    await event.answer()
                return
    except Exception as e:
        logging.error(f"Majburiy obunani tekshirishda xatolik (Bot admin bo'lmasligi mumkin): {e}")

    return await handler(event, data)


# ---------- OBUNANI TASDIQLASH TUGMASI ----------

@router.callback_query(F.data == "check_sub")
async def check_sub_handler(callback: CallbackQuery, bot: Bot):
    channel = await db.get_setting("force_sub_channel")
    if not channel:
        await callback.message.delete()
        return
        
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=callback.from_user.id)
        if member.status in ['member', 'creator', 'administrator', 'restricted']:
            await callback.message.delete()
            await callback.message.answer("✅ Rahmat! Obuna tasdiqlandi.\n\nIltimos, qaytadan /start buyrug'ini yuboring.")
        else:
            await callback.answer("❌ Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)
    except Exception as e:
        await callback.answer("⚠️ Xatolik yuz berdi. Bot kanalga admin ekanligini tekshiring.", show_alert=True)


# ---------- BO'LIMLAR TUGMALARI ----------

def categories_keyboard(categories, page: int):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = categories[start:end]

    builder = InlineKeyboardBuilder()
    for cat_id, name in page_items:
        builder.button(text=name, callback_data=f"cat:{cat_id}:0")
    builder.adjust(1)

    nav_row = []
    if page > 0:
        nav_row.append(("⏮ Oldingi", f"catpage:{page - 1}"))
    if end < len(categories):
        nav_row.append(("Keyingi ⏭", f"catpage:{page + 1}"))

    if nav_row:
        nav_builder = InlineKeyboardBuilder()
        for text, cb in nav_row:
            nav_builder.button(text=text, callback_data=cb)
        nav_builder.adjust(2)
        builder.attach(nav_builder)

    action_builder = InlineKeyboardBuilder()
    action_builder.button(text="🔍 Qidirish", callback_data="start_search")
    action_builder.button(text="⭐️ Saqlanganlar", callback_data="show_favorites")
    action_builder.button(text="📞 Adminga murojaat", callback_data="user_contact")
    action_builder.adjust(2, 1) # Qidirish va Saqlanganlar yonma-yon, Murojaat pastda
    builder.attach(action_builder)

    return builder.as_markup()


# ---------- KITOBLAR TUGMALARI ----------

def books_keyboard(books, category_id: int, page: int):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = books[start:end]

    builder = InlineKeyboardBuilder()
    for book in page_items:
        builder.button(text=book["title"], callback_data=f"book:{book['id']}")
    builder.adjust(1)

    nav_row = []
    if page > 0:
        nav_row.append(("⏮ Oldingi", f"cat:{category_id}:{page - 1}"))
    if end < len(books):
        nav_row.append(("Keyingi ⏭", f"cat:{category_id}:{page + 1}"))

    if nav_row:
        nav_builder = InlineKeyboardBuilder()
        for text, cb in nav_row:
            nav_builder.button(text=text, callback_data=cb)
        nav_builder.adjust(2)
        builder.attach(nav_builder)

    back_builder = InlineKeyboardBuilder()
    back_builder.button(text="⬅️ Bo'limlarga qaytish", callback_data="catpage:0")
    back_builder.adjust(1)
    builder.attach(back_builder)

    return builder.as_markup()


@router.message(CommandStart())
async def start_handler(message: Message):
    await db.add_user(message.from_user.id)
    categories = await db.get_categories()
    await message.answer("Assalomu alaykum! 📚\nBo'limlardan birini tanlang:", reply_markup=categories_keyboard(categories, 0))


@router.callback_query(F.data.startswith("catpage:"))
async def category_page_handler(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    categories = await db.get_categories()
    await callback.message.edit_text("Bo'limlardan birini tanlang:", reply_markup=categories_keyboard(categories, page))
    await callback.answer()


@router.callback_query(F.data.startswith("cat:"))
async def category_handler(callback: CallbackQuery):
    parts = callback.data.split(":")
    category_id = int(parts[1])
    page = int(parts[2]) if len(parts) > 2 else 0

    books = await db.get_books_by_category(category_id)

    if not books:
        await callback.answer("Bu bo'limda hozircha kitob yo'q.", show_alert=True)
        return

    await callback.message.edit_text(
        "Kitoblardan birini tanlang:",
        reply_markup=books_keyboard(books, category_id, page),
    )
    await callback.answer()


# ---------- KITOB MA'LUMOTLARI VA YUKLAB OLISH ----------

@router.callback_query(F.data.startswith("book:"))
async def book_handler(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    book = await db.get_book(book_id)

    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return

    avg_rating, count = await db.get_book_rating(book_id)
    is_fav = await db.is_favorite(callback.from_user.id, book_id)
    fav_text = "❌ Saqlanganlardan o'chirish" if is_fav else "⭐️ Saqlanganlarga qo'shish"

    caption = (
        f"📖 **{book['title']}**\n\n"
        f"📝 **Tavsif:** {book['description'] or 'Mavjud emas'}\n"
        f"⭐️ **Baho:** {avg_rating}/5 ({count} ta ovoz)\n"
        f"📥 **Yuklab olishlar:** {book['download_count']}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📥 PDF yuklab olish", callback_data=f"download:{book_id}")
    builder.button(text=fav_text, callback_data=f"fav:{book_id}")

    rate_row = [InlineKeyboardBuilder().button(text=f"⭐️ {i}", callback_data=f"rate:{book_id}:{i}") for i in range(1, 6)]
    for r in rate_row:
        builder.attach(r)

    builder.adjust(1, 1, 5)

    if book["photo_id"]:
        await callback.message.answer_photo(photo=book["photo_id"], caption=caption, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await callback.message.answer(text=caption, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("download:"))
async def download_book(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    book = await db.get_book(book_id)
    await callback.message.answer_document(book["file_id"], caption=f"📄 {book['title']}")
    await db.increment_download_count(book_id)
    await callback.answer()


@router.callback_query(F.data.startswith("fav:"))
async def favorite_toggle(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    status = await db.toggle_favorite(callback.from_user.id, book_id)
    msg = "Saqlanganlarga qo'shildi!" if status else "Saqlanganlardan olib tashlandi!"
    await callback.answer(msg, show_alert=True)


@router.callback_query(F.data.startswith("rate:"))
async def rate_book(callback: CallbackQuery):
    _, book_id, rating = callback.data.split(":")
    await db.set_rating(callback.from_user.id, int(book_id), int(rating))
    await callback.answer("Bahoingiz saqlandi!", show_alert=True)


@router.callback_query(F.data == "show_favorites")
async def show_favorites(callback: CallbackQuery):
    favs = await db.get_user_favorites(callback.from_user.id)
    if not favs:
        await callback.answer("Sizda hali saqlangan kitoblar yo'q.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for b_id, title in favs:
        builder.button(text=title, callback_data=f"book:{b_id}")
    builder.adjust(1)
    await callback.message.answer("⭐️ Sizning saqlangan kitoblaringiz:", reply_markup=builder.as_markup())
    await callback.answer()


# ---------- QIDIRUV ----------

@router.callback_query(F.data == "start_search")
async def start_search_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Search.waiting_for_query)
    await callback.message.answer("Qidirmoqchi bo'lgan kitob nomini yozing:")
    await callback.answer()


@router.message(Search.waiting_for_query)
async def do_search(message: Message, state: FSMContext):
    await state.clear()
    query = message.text.strip()
    results = await db.search_books(query)

    if not results:
        await message.answer(f"\"{query}\" bo'yicha hech narsa topilmadi.")
        return

    builder = InlineKeyboardBuilder()
    for book in results:
        builder.button(text=book["title"], callback_data=f"book:{book['id']}")
    builder.adjust(1)

    await message.answer(f"\"{query}\" bo'yicha {len(results)} ta natija topildi:", reply_markup=builder.as_markup())


# ---------- ADMINGA MUROJAAT QILISH (CONTACT) ----------

@router.message(Command("contact"))
@router.callback_query(F.data == "user_contact")
async def contact_start(event: Message | CallbackQuery, state: FSMContext):
    message = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        await event.answer()
        
    await state.set_state(ContactAdmin.waiting_for_message)
    await message.answer(
        "✍️ Adminga yubormoqchi bo'lgan murojaatingiz, taklifingiz yoki savolingizni yuboring "
        "(matn, rasm yoki video ko'rinishida bo'lishi mumkin):\n\n"
        "Bekor qilish uchun /cancel yuboring."
    )

@router.message(Command("cancel"), ContactAdmin.waiting_for_message)
async def contact_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Murojaat yuborish bekor qilindi.")

@router.message(ContactAdmin.waiting_for_message)
async def contact_send_to_admin(message: Message, state: FSMContext):
    user = message.from_user
    await state.clear()
    
    info_text = (
        f"📩 **Yangi murojaat!**\n\n"
        f"👤 Foydalanuvchi: {user.full_name} (@{user.username if user.username else 'yoq'})\n"
        f"🆔 ID: `{user.id}`\n\n"
        f"Javob berish uchun ushbu xabarga **Reply (Javob berish)** qilib yozing."
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(admin_id, info_text, parse_mode="Markdown")
            await message.bot.copy_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
        except Exception as e:
            logging.error(f"Adminga yuborishda xatolik {admin_id}: {e}")
            
    await message.answer("✅ Murojaatingiz adminga yuborildi! Tez orada javob qaytaramiz.")
