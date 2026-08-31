import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

import database as db

router = Router()

PAGE_SIZE = 10


class Search(StatesGroup):
    waiting_for_query = State()


# ---------- FORCE-SUBSCRIBE ----------

async def check_subscription(bot: Bot, user_id: int) -> bool:
    channel = await db.get_setting("force_sub_channel")
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel, user_id=user_id)
        return member.status not in ("left", "kicked")
    except (TelegramBadRequest, TelegramForbiddenError) as e:
        logging.error(f"Majburiy obuna tekshirishda xatolik (Kanal: {channel}): {e}")
        # TelegramBadRequest bo'lganda True emas, False qaytariladi
        return False
    except Exception as e:
        logging.error(f"Kutilmagan xatolik yuz berdi: {e}")
        return False


async def send_subscribe_prompt(message: Message):
    channel = await db.get_setting("force_sub_channel")
    builder = InlineKeyboardBuilder()
    
    # Kanal havolasini to'g'ri shakllantirish
    if not channel:
        url = "https://t.me"
    elif channel.startswith("http://") or channel.startswith("https://"):
        url = channel
    elif channel.startswith("@"):
        url = f"https://t.me/{channel.lstrip('@')}"
    else:
        url = f"https://t.me/{channel}"

    builder.button(text="📢 Kanalga o'tish", url=url)
    builder.button(text="✅ Tekshirish", callback_data="check_sub")
    builder.adjust(1)
    
    await message.answer(
        "Botdan foydalanish uchun avval kanalimizga a'zo bo'ling, "
        "so'ng \"Tekshirish\" tugmasini bosing:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data == "check_sub")
async def check_sub_callback(callback: CallbackQuery):
    if await check_subscription(callback.bot, callback.from_user.id):
        await callback.message.delete()
        await show_categories(callback.message, edit=False)
    else:
        await callback.answer("Hali kanalga a'zo bo'lmadingiz yoki bot kanalda admin emas.", show_alert=True)


# ---------- MAIN MENU / CATEGORIES ----------

def categories_keyboard(categories, page: int):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = categories[start:end]

    builder = InlineKeyboardBuilder()
    for cat_id, name in page_items:
        builder.button(text=name, callback_data=f"cat:{cat_id}:{page}")
    builder.adjust(1)

    nav_row = []
    if page > 0:
        nav_row.append(("⬅️", f"catpage:{page - 1}"))
    if end < len(categories):
        nav_row.append(("➡️", f"catpage:{page + 1}"))
    if nav_row:
        nav_builder = InlineKeyboardBuilder()
        for text, cb in nav_row:
            nav_builder.button(text=text, callback_data=cb)
        nav_builder.adjust(2)
        builder.attach(nav_builder)

    search_builder = InlineKeyboardBuilder()
    search_builder.button(text="🔍 Qidirish", callback_data="start_search")
    search_builder.adjust(1)
    builder.attach(search_builder)

    return builder.as_markup()


async def show_categories(message: Message, page: int = 0, edit: bool = True):
    categories = await db.get_categories()

    if not categories:
        text = "Assalomu alaykum! 📚\n\nHozircha bo'limlar qo'shilmagan. Tez orada qo'llanmalar paydo bo'ladi."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    text = "Assalomu alaykum! 📚\n\nQuyidagi bo'limlardan birini tanlang:"
    markup = categories_keyboard(categories, page)

    if edit:
        try:
            await message.edit_text(text, reply_markup=markup)
        except TelegramBadRequest:
            await message.answer(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


@router.message(CommandStart())
async def start_handler(message: Message):
    await db.add_user(message.from_user.id)

    if not await check_subscription(message.bot, message.from_user.id):
        await send_subscribe_prompt(message)
        return

    await show_categories(message, edit=False)


@router.callback_query(F.data.startswith("catpage:"))
async def category_page_handler(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_categories(callback.message, page=page, edit=True)
    await callback.answer()


# ---------- BOOKS IN CATEGORY ----------

def books_keyboard(books, category_id: int, page: int):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_items = books[start:end]

    builder = InlineKeyboardBuilder()
    for book_id, title, _, _ in page_items:
        builder.button(text=title, callback_data=f"book:{book_id}")
    builder.adjust(1)

    nav_row = []
    if page > 0:
        nav_row.append(("⬅️", f"cat:{category_id}:{page - 1}"))
    if end < len(books):
        nav_row.append(("➡️", f"cat:{category_id}:{page + 1}"))
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


@router.callback_query(F.data.startswith("book:"))
async def book_handler(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    book = await db.get_book(book_id)

    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return

    _, title, file_id, _ = book
    await callback.message.answer_document(file_id, caption=f"📄 {title}")
    await db.increment_download_count(book_id)
    await callback.answer()


# ---------- SEARCH ----------

@router.callback_query(F.data == "start_search")
async def start_search_handler(callback: CallbackQuery, state: FSMContext):
    await state.set_state(Search.waiting_for_query)
    await callback.message.answer(
        "Qidirmoqchi bo'lgan kitob nomini yozing (bekor qilish uchun /cancel):"
    )
    await callback.answer()


@router.message(Command("cancel"), Search.waiting_for_query)
async def cancel_search(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(Search.waiting_for_query)
async def do_search(message: Message, state: FSMContext):
    await state.clear()
    query = message.text.strip()
    results = await db.search_books(query)

    if not results:
        await message.answer(f"\"{query}\" bo'yicha hech narsa topilmadi.")
        return

    builder = InlineKeyboardBuilder()
    for book_id, title, _, _ in results:
        builder.button(text=title, callback_data=f"book:{book_id}")
    builder.adjust(1)

    await message.answer(
        f"\"{query}\" bo'yicha {len(results)} ta natija topildi:",
        reply_markup=builder.as_markup(),
    )
