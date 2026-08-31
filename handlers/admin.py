import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramNotFound

import database as db
from config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AddCategory(StatesGroup):
    waiting_for_name = State()


class AddBook(StatesGroup):
    waiting_for_pdf = State()
    waiting_for_photo = State()
    waiting_for_desc = State()
    waiting_for_title = State()
    waiting_for_category = State()


class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()


class BanUser(StatesGroup):
    waiting_for_id = State()


class UnbanUser(StatesGroup):
    waiting_for_id = State()


class SetChannel(StatesGroup):
    waiting_for_channel = State()


@router.message(Command("admin"))
async def admin_menu(message: Message):
    if not is_admin(message.from_user.id):
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Bo'lim qo'shish", callback_data="admin_add_category")
    builder.button(text="➕ Kitob qo'shish", callback_data="admin_add_book")
    builder.button(text="🗑 Kitob o'chirish", callback_data="admin_del_book")
    builder.button(text="🗑 Bo'lim o'chirish", callback_data="admin_del_category")
    builder.button(text="📢 Majburiy kanal qo'shish", callback_data="admin_add_channel")
    builder.button(text="🚫 User Ban qilish", callback_data="admin_ban_user")
    builder.button(text="✅ User Unban qilish", callback_data="admin_unban_user")
    builder.button(text="📊 Statistika", callback_data="admin_stats_btn")
    builder.adjust(1)

    await message.answer("🛠 Admin panel", reply_markup=builder.as_markup())


# ---------- BO'LIM QO'SHISH ----------

@router.callback_query(F.data == "admin_add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddCategory.waiting_for_name)
    await callback.message.answer("Yangi bo'lim nomini yuboring (masalan: Dasturlash kitoblari):")
    await callback.answer()


@router.message(AddCategory.waiting_for_name)
async def add_category_finish(message: Message, state: FSMContext):
    await db.add_category(message.text.strip())
    await state.clear()
    await message.answer(f"✅ Bo'lim qo'shildi: {message.text.strip()}")


# ---------- MAJBURIY KANAL QO'SHISH ----------

@router.callback_query(F.data == "admin_add_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(SetChannel.waiting_for_channel)
    await callback.message.answer("Majburiy obuna kanali username yoki ID sini yuboring (masalan: @kanal_username):")
    await callback.answer()


@router.message(SetChannel.waiting_for_channel)
async def add_channel_finish(message: Message, state: FSMContext):
    await db.set_setting("force_sub_channel", message.text.strip())
    await state.clear()
    await message.answer(f"✅ Majburiy obuna kanali saqlandi: {message.text.strip()}")


# ---------- BO'LIM O'CHIRISH ----------

@router.callback_query(F.data == "admin_del_category")
async def del_category_pick(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = await db.get_categories()
    if not categories:
        await callback.answer("Bo'limlar mavjud emas.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=f"🗑 {name}", callback_data=f"confirm_del_cat:{cat_id}")
    builder.adjust(1)
    await callback.message.answer("Qaysi bo'limni o'chiramiz?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_cat:"))
async def del_category_confirm(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    await db.delete_category(category_id)
    await callback.message.answer("✅ Bo'lim va undagi barcha kitoblar o'chirildi.")
    await callback.answer()


# ---------- KITOB O'CHIRISH ----------

@router.callback_query(F.data == "admin_del_book")
async def del_book_pick_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = await db.get_categories()
    if not categories:
        await callback.answer("Bo'limlar mavjud emas.", show_alert=True)
        return
    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=name, callback_data=f"delcat_books:{cat_id}")
    builder.adjust(1)
    await callback.message.answer("Qaysi bo'limdan kitob o'chiramiz?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("delcat_books:"))
async def del_book_pick_book(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    books = await db.get_books_by_category(category_id)

    if not books:
        await callback.answer("Bu bo'limda kitob yo'q.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for book in books:
        builder.button(text=f"🗑 {book['title']}", callback_data=f"confirm_del_book:{book['id']}")
    builder.adjust(1)

    await callback.message.answer("O'chirmoqchi bo'lgan kitobni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_book:"))
async def del_book_confirm(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    await db.delete_book(book_id)
    await callback.message.answer("✅ Kitob o'chirildi.")
    await callback.answer()


# ---------- STATISTIKA ----------

@router.callback_query(F.data == "admin_stats_btn")
async def stats_btn_handler(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    user_count = await db.get_user_count()
    new_today = await db.get_new_users_today()
    book_count = await db.get_book_count()
    downloads = await db.get_total_downloads()

    text = (
        f"📊 **Bot Statistikasi:**\n\n"
        f"👥 Jami foydalanuvchilar: {user_count}\n"
        f"➕ Bugun qo'shilganlar: {new_today}\n"
        f"📚 Jami kitoblar: {book_count}\n"
        f"📥 Jami yuklab olishlar: {downloads}"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()


# ---------- BAN / UNBAN ----------

@router.callback_query(F.data == "admin_ban_user")
async def ban_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BanUser.waiting_for_id)
    await callback.message.answer("Ban qilinadigan foydalanuvchi Telegram ID sini yuboring:")
    await callback.answer()


@router.message(BanUser.waiting_for_id)
async def ban_user_finish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await db.set_user_ban(user_id, True)
        await message.answer(f"🚫 {user_id} idli foydalanuvchi bloklandi.")
    except ValueError:
        await message.answer("Xato ID kiritildi.")
    await state.clear()


@router.callback_query(F.data == "admin_unban_user")
async def unban_user_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UnbanUser.waiting_for_id)
    await callback.message.answer("Bani olib tashlanadigan foydalanuvchi Telegram ID sini yuboring:")
    await callback.answer()


@router.message(UnbanUser.waiting_for_id)
async def unban_user_finish(message: Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        await db.set_user_ban(user_id, False)
        await message.answer(f"✅ {user_id} idli foydalanuvchi blokdan chiqarildi.")
    except ValueError:
        await message.answer("Xato ID kiritildi.")
    await state.clear()


# ---------- KITOB QO'SHISH ----------

@router.callback_query(F.data == "admin_add_book")
async def add_book_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddBook.waiting_for_pdf)
    await callback.message.answer("PDF faylni yuboring:")
    await callback.answer()


@router.message(AddBook.waiting_for_pdf, F.document)
async def add_book_got_pdf(message: Message, state: FSMContext):
    await state.update_data(file_id=message.document.file_id)
    await state.set_state(AddBook.waiting_for_photo)
    await message.answer("Kitob muqovasi (rasm) yuboring yoki o'tkazib yuborish uchun /skip bosing:")


@router.message(Command("skip"), AddBook.waiting_for_photo)
async def skip_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=None)
    await state.set_state(AddBook.waiting_for_desc)
    await message.answer("Kitob tavsifini yozing yoki /skip bosing:")


@router.message(AddBook.waiting_for_photo, F.photo)
async def add_book_got_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(AddBook.waiting_for_desc)
    await message.answer("Kitob tavsifini yozing yoki /skip bosing:")


@router.message(Command("skip"), AddBook.waiting_for_desc)
async def skip_desc(message: Message, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(AddBook.waiting_for_title)
    await message.answer("Kitob nomini yuboring:")


@router.message(AddBook.waiting_for_desc)
async def add_book_got_desc(message: Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddBook.waiting_for_title)
    await message.answer("Kitob nomini yuboring:")


@router.message(AddBook.waiting_for_title)
async def add_book_got_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    categories = await db.get_categories()
    if not categories:
        await message.answer("Avval bo'lim qo'shing.")
        await state.clear()
        return

    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=name, callback_data=f"pick_cat:{cat_id}")
    builder.adjust(1)
    await state.set_state(AddBook.waiting_for_category)
    await message.answer("Qaysi bo'limga qo'shamiz?", reply_markup=builder.as_markup())


@router.callback_query(AddBook.waiting_for_category, F.data.startswith("pick_cat:"))
async def add_book_finish(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    await db.add_book(category_id, data["title"], data["file_id"], data.get("photo_id"), data.get("description"))
    await state.clear()
    await callback.message.answer(f"✅ Kitob qo'shildi: {data['title']}")
    await callback.answer()
