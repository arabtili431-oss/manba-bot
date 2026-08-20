from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

import database as db

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):
    categories = await db.get_categories()

    if not categories:
        await message.answer(
            "Assalomu alaykum! 📚\n\nHozircha bo'limlar qo'shilmagan. Tez orada qo'llanmalar paydo bo'ladi."
        )
        return

    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=name, callback_data=f"cat:{cat_id}")
    builder.adjust(1)

    await message.answer(
        "Assalomu alaykum! 📚\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("cat:"))
async def category_handler(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    books = await db.get_books_by_category(category_id)

    if not books:
        await callback.answer("Bu bo'limda hozircha kitob yo'q.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for book_id, title, _ in books:
        builder.button(text=title, callback_data=f"book:{book_id}")
    builder.button(text="⬅️ Orqaga", callback_data="back_to_categories")
    builder.adjust(1)

    await callback.message.edit_text(
        "Kitoblardan birini tanlang:", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_categories")
async def back_handler(callback: CallbackQuery):
    categories = await db.get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=name, callback_data=f"cat:{cat_id}")
    builder.adjust(1)

    await callback.message.edit_text(
        "Quyidagi bo'limlardan birini tanlang:", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("book:"))
async def book_handler(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    book = await db.get_book(book_id)

    if not book:
        await callback.answer("Kitob topilmadi.", show_alert=True)
        return

    _, title, file_id = book
    await callback.message.answer_document(file_id, caption=f"📄 {title}")
    await callback.answer()
