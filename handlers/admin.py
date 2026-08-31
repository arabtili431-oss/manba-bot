import asyncio
import json

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import (
    TelegramForbiddenError,
    TelegramRetryAfter,
    TelegramNotFound,
)

import database as db
from config import ADMIN_IDS

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


class AddCategory(StatesGroup):
    waiting_for_name = State()


class AddBook(StatesGroup):
    waiting_for_pdf = State()
    waiting_for_title = State()
    waiting_for_category = State()


class Broadcast(StatesGroup):
    waiting_for_message = State()
    waiting_for_confirm = State()


class EditBook(StatesGroup):
    waiting_for_new_title = State()


class EditCategory(StatesGroup):
    waiting_for_new_name = State()


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
    builder.button(text="✏️ Kitob nomini o'zgartirish", callback_data="admin_edit_book")
    builder.button(text="✏️ Bo'lim nomini o'zgartirish", callback_data="admin_edit_category")
    builder.button(text="🗑 Kitob o'chirish", callback_data="admin_del_book")
    builder.button(text="🗑 Bo'lim o'chirish", callback_data="admin_del_category")
    builder.button(text="📢 Majburiy kanal qo'shish", callback_data="admin_add_channel")
    builder.button(text="📋 Kanallarni boshqarish", callback_data="admin_manage_channels")
    builder.button(text="📊 Statistika", callback_data="admin_stats_btn")
    builder.adjust(1)

    await message.answer("🛠 Admin panel", reply_markup=builder.as_markup())


# ---------- ADD CATEGORY ----------

@router.callback_query(F.data == "admin_add_category")
async def add_category_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AddCategory.waiting_for_name)
    await callback.message.answer("Yangi bo'lim nomini yuboring (masalan: Imtihon qo'llanmalari):")
    await callback.answer()


@router.message(AddCategory.waiting_for_name)
async def add_category_finish(message: Message, state: FSMContext):
    await db.add_category(message.text.strip())
    await state.clear()
    await message.answer(f"✅ Bo'lim qo'shildi: {message.text.strip()}")


# ---------- ADD BOOK ----------

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
    await state.set_state(AddBook.waiting_for_title)
    await message.answer("Kitob nomini yuboring:")


@router.message(AddBook.waiting_for_pdf)
async def add_book_wrong_type(message: Message):
    await message.answer("Iltimos, PDF faylni hujjat (document) sifatida yuboring.")


@router.message(AddBook.waiting_for_title)
async def add_book_got_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text.strip())

    categories = await db.get_categories()
    if not categories:
        await message.answer("Avval bo'lim qo'shing (/admin -> Bo'lim qo'shish).")
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

    await db.add_book(category_id, data["title"], data["file_id"])
    await state.clear()

    await callback.message.answer(f"✅ Kitob qo'shildi: {data['title']}")
    await callback.answer()


# ---------- EDIT BOOK TITLE ----------

@router.callback_query(F.data == "admin_edit_book")
async def edit_book_pick_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = await db.get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=name, callback_data=f"editcat_books:{cat_id}")
    builder.adjust(1)
    await callback.message.answer("Qaysi bo'limdan kitob nomini o'zgartiramiz?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("editcat_books:"))
async def edit_book_pick_book(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    books = await db.get_books_by_category(category_id)

    if not books:
        await callback.answer("Bu bo'limda kitob yo'q.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for book_id, title, _, _ in books:
        builder.button(text=f"✏️ {title}", callback_data=f"editbook_pick:{book_id}")
    builder.adjust(1)

    await callback.message.answer("Qaysi kitob nomini o'zgartiramiz?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("editbook_pick:"))
async def edit_book_ask_new_title(callback: CallbackQuery, state: FSMContext):
    book_id = int(callback.data.split(":")[1])
    await state.update_data(book_id=book_id)
    await state.set_state(EditBook.waiting_for_new_title)
    await callback.message.answer("Yangi nomni yuboring:")
    await callback.answer()


@router.message(EditBook.waiting_for_new_title)
async def edit_book_save(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_book_title(data["book_id"], message.text.strip())
    await state.clear()
    await message.answer(f"✅ Kitob nomi yangilandi: {message.text.strip()}")


# ---------- EDIT CATEGORY NAME ----------

@router.callback_query(F.data == "admin_edit_category")
async def edit_category_pick(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = await db.get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=f"✏️ {name}", callback_data=f"editcat_pick:{cat_id}")
    builder.adjust(1)
    await callback.message.answer("Qaysi bo'lim nomini o'zgartiramiz?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("editcat_pick:"))
async def edit_category_ask_new_name(callback: CallbackQuery, state: FSMContext):
    category_id = int(callback.data.split(":")[1])
    await state.update_data(category_id=category_id)
    await state.set_state(EditCategory.waiting_for_new_name)
    await callback.message.answer("Yangi nomni yuboring:")
    await callback.answer()


@router.message(EditCategory.waiting_for_new_name)
async def edit_category_save(message: Message, state: FSMContext):
    data = await state.get_data()
    await db.update_category_name(data["category_id"], message.text.strip())
    await state.clear()
    await message.answer(f"✅ Bo'lim nomi yangilandi: {message.text.strip()}")


# ---------- DELETE BOOK ----------

@router.callback_query(F.data == "admin_del_book")
async def del_book_pick_category(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = await db.get_categories()
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
    for book_id, title, _, _ in books:
        builder.button(text=f"🗑 {title}", callback_data=f"confirm_del_book:{book_id}")
    builder.adjust(1)

    await callback.message.answer("O'chirmoqchi bo'lgan kitobni tanlang:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_book:"))
async def del_book_confirm(callback: CallbackQuery):
    book_id = int(callback.data.split(":")[1])
    await db.delete_book(book_id)
    await callback.message.answer("✅ Kitob o'chirildi.")
    await callback.answer()


# ---------- DELETE CATEGORY ----------

@router.callback_query(F.data == "admin_del_category")
async def del_category_pick(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    categories = await db.get_categories()
    builder = InlineKeyboardBuilder()
    for cat_id, name in categories:
        builder.button(text=f"🗑 {name}", callback_data=f"confirm_del_cat:{cat_id}")
    builder.adjust(1)
    await callback.message.answer(
        "Diqqat: bo'lim o'chirilsa, undagi barcha kitoblar ham o'chadi.\nQaysi bo'limni o'chiramiz?",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_cat:"))
async def del_category_confirm(callback: CallbackQuery):
    category_id = int(callback.data.split(":")[1])
    await db.delete_category(category_id)
    await callback.message.answer("✅ Bo'lim va undagi barcha kitoblar o'chirildi.")
    await callback.answer()


# ---------- BROADCAST (/send) ----------

@router.message(Command("send"))
async def send_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(Broadcast.waiting_for_message)
    await message.answer(
        "Yubormoqchi bo'lgan xabarni menga yuboring "
        "(matn, rasm, video yoki fayl bo'lishi mumkin).\n\n"
        "Bekor qilish uchun /cancel yuboring."
    )


@router.message(Command("cancel"), Broadcast.waiting_for_message)
async def send_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Bekor qilindi.")


@router.message(Broadcast.waiting_for_message)
async def send_got_message(message: Message, state: FSMContext):
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id)

    user_count = await db.get_user_count()

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yuborish", callback_data="broadcast_confirm")
    builder.button(text="❌ Bekor qilish", callback_data="broadcast_cancel")
    builder.adjust(2)

    await state.set_state(Broadcast.waiting_for_confirm)
    await message.answer(
        f"Yuqoridagi xabar {user_count} ta foydalanuvchiga yuboriladi. Tasdiqlaysizmi?",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(Broadcast.waiting_for_confirm, F.data == "broadcast_cancel")
async def send_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


@router.callback_query(Broadcast.waiting_for_confirm, F.data == "broadcast_confirm")
async def send_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    users = await db.get_all_users()
    await callback.message.edit_text(f"⏳ Yuborilmoqda... (0/{len(users)})")

    sent = 0
    failed = 0
    blocked_count = 0
    not_found_count = 0
    other_count = 0

    for user_id in users:
        try:
            await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=data["chat_id"],
                message_id=data["message_id"],
            )
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await callback.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=data["chat_id"],
                    message_id=data["message_id"],
                )
                sent += 1
            except Exception:
                failed += 1
                other_count += 1
        except TelegramForbiddenError:
            failed += 1
            blocked_count += 1
        except TelegramNotFound:
            failed += 1
            not_found_count += 1
        except Exception:
            failed += 1
            other_count += 1

        await asyncio.sleep(0.05)

    report_text = (
        f"✅ Yuborish yakunlandi.\n\n"
        f"📤 Yuborildi: {sent}\n"
        f"❌ Yuborilmadi: {failed}\n\n"
        f"📌 **Xatoliklar sababi:**\n"
        f"🚫 Botni bloklagan / O'chirilgan akkauntlar: {blocked_count}\n"
        f"🔍 Chat topilmadi: {not_found_count}\n"
        f"⚠️ Boshqa xatoliklar: {other_count}"
    )

    await callback.message.answer(report_text)
    await callback.answer()


# ---------- STATS (/stats) ----------

async def send_stats(message: Message):
    user_count = await db.get_user_count()
    new_today = await db.get_new_users_today()
    book_count = await db.get_book_count()
    total_downloads = await db.get_total_downloads()
    top_books = await db.get_top_books(5)

    text = (
        "📊 Statistika\n\n"
        f"👥 Jami foydalanuvchilar: {user_count}\n"
        f"🆕 Bugun qo'shilganlar: {new_today}\n"
        f"📚 Jami kitoblar: {book_count}\n"
        f"⬇️ Jami yuklab olishlar: {total_downloads}\n"
    )

    if top_books:
        text += "\n🔥 Eng ko'p yuklangan kitoblar:\n"
        for i, (title, count) in enumerate(top_books, start=1):
            text += f"{i}. {title} — {count} marta\n"

    await message.answer(text)


@router.message(Command("stats"))
async def stats_handler(message: Message):
    if not is_admin(message.from_user.id):
        return
    await send_stats(message)


@router.callback_query(F.data == "admin_stats_btn")
async def stats_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await send_stats(callback.message)
    await callback.answer()


# ---------- FORCE-SUBSCRIBE SETTINGS ----------

@router.message(Command("setchannel"))
@router.callback_query(F.data == "admin_add_channel")
async def set_channel_start(event: Message | CallbackQuery, state: FSMContext):
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    await state.set_state(SetChannel.waiting_for_channel)
    msg_text = (
        "Majburiy obuna kanali username'ini yuboring (masalan: @mening_kanalim).\n\n"
        "Bir nechta kanal qo'shishingiz mumkin, ular ketma-ket saqlab boriladi.\n\n"
        "Diqqat: bot shu kanallarda admin bo'lishi shart!\n\n"
        "Mavjud kanallarni ko'rish yoki o'chirish uchun /removechannel buyrug'idan foydalaning."
    )
    if isinstance(event, CallbackQuery):
        await event.message.answer(msg_text)
        await event.answer()
    else:
        await event.answer(msg_text)


@router.message(SetChannel.waiting_for_channel)
async def set_channel_save(message: Message, state: FSMContext):
    channel = message.text.strip()
    if not channel.startswith("@") and not channel.startswith("-100") and not channel.startswith("http://") and not channel.startswith("https://"):
        channel = "@" + channel

    existing = await db.get_setting("force_sub_channel")
    channels = [c.strip() for c in existing.split(",") if c.strip()] if existing else []

    if channel in channels:
        await message.answer(f"⚠️ Bu kanal ({channel}) allaqachon majburiy obuna ro'yxatida bor.")
        await state.clear()
        return

    channels.append(channel)
    new_setting = ",".join(channels)
    await db.set_setting("force_sub_channel", new_setting)
    await state.clear()

    text = "✅ Yangi majburiy obuna kanali qo'shildi!\n\n📋 **Hozirgi kanallar ro'yxati:**\n"
    for idx, ch in enumerate(channels, 1):
        text += f"{idx}. {ch}\n"
    text += "\nBotni ushbu kanallarda admin qilishni unutmang."

    await message.answer(text)


@router.message(Command("removechannel"))
@router.callback_query(F.data == "admin_manage_channels")
async def remove_channel_menu(event: Message | CallbackQuery):
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    existing = await db.get_setting("force_sub_channel")
    channels = [c.strip() for c in existing.split(",") if c.strip()] if existing else []

    if not channels:
        msg = "Hozircha hech qanday majburiy obuna kanallari o'rnatilmagan."
        if isinstance(event, CallbackQuery):
            await event.message.answer(msg)
            await event.answer()
        else:
            await event.answer(msg)
        return

    builder = InlineKeyboardBuilder()
    for idx, ch in enumerate(channels):
        builder.button(text=f"🗑 {ch}", callback_data=f"delchan:{idx}")
    builder.button(text="🔥 Barchasini o'chirish", callback_data="delchan_all")
    builder.adjust(1)

    msg = "📋 **Majburiy obuna kanallari:**\nO'chirmoqchi bo'lgan kanalingizni bosing:"
    if isinstance(event, CallbackQuery):
        await event.message.answer(msg, reply_markup=builder.as_markup())
        await event.answer()
    else:
        await event.answer(msg, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("delchan:"))
async def del_single_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    idx = int(callback.data.split(":")[1])
    existing = await db.get_setting("force_sub_channel")
    channels = [c.strip() for c in existing.split(",") if c.strip()] if existing else []

    if 0 <= idx < len(channels):
        removed = channels.pop(idx)
        if channels:
            await db.set_setting("force_sub_channel", ",".join(channels))
        else:
            await db.delete_setting("force_sub_channel")
        await callback.message.answer(f"✅ Kanal o'chirildi: {removed}")
    else:
        await callback.answer("Kanal topilmadi.", show_alert=True)
    await callback.answer()


@router.callback_query(F.data == "delchan_all")
async def del_all_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await db.delete_setting("force_sub_channel")
    await callback.message.answer("✅ Barcha majburiy obuna kanallari o'chirildi.")
    await callback.answer()


# ---------- BACKUP (/backup) ----------

@router.message(Command("backup"))
async def backup_handler(message: Message):
    if not is_admin(message.from_user.id):
        return

    data = await db.export_all_data()
    backup_path = "/tmp/backup.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    await message.answer_document(
        FSInputFile(backup_path, filename="backup.json"),
        caption="📦 Ma'lumotlar zaxira nusxasi (JSON)",
    )
