import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
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
    waiting_for_buttons = State()
    waiting_for_confirm = State()


class BanUser(StatesGroup):
    waiting_for_id = State()


class UnbanUser(StatesGroup):
    waiting_for_id = State()


class SetChannel(StatesGroup):
    waiting_for_channel = State()


# ---------- ADMIN MENU ----------

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
        await callback.answer("Bo'limlar mavjud emas.", show_alert=True
