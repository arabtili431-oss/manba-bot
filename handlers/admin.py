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


# ---------- FOYDALANUVCHILAR MUROJAATIGA JAVOB BERISH (REPLY) ----------

@router.message(F.reply_to_message)
async def admin_reply_to_user(message: Message):
    if not is_admin(message.from_user.id):
        return
        
    reply_msg = message.reply_to_message
    
    if reply_msg.text and "🆔 ID:" in reply_msg.text:
        try:
            for line in reply_msg.text.split("\n"):
                if "🆔 ID:" in line:
                    user_id = int(line.split("`")[1])
                    
                    await message.bot.send_message(
                        chat_id=user_id,
                        text=f"👨‍💻 **Adindan javob:**\n\n{message.text}"
                    )
                    await message.reply("✅ Javob foydalanuvchiga yuborildi!")
                    return
        except Exception as e:
            await message.reply(f"❌ Xatolik yuz berdi: {e}")


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
    if not is_admin(message.from_user.id):
        return
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
    if not is_admin(message.from_user.id):
        return
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
    if not is_admin(callback.from_user.id):
        return
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
    if not is_admin(callback.from_user.id):
        return
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
    if not is_admin(callback.from_user.id):
        return
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
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(BanUser.waiting_for_id)
    await callback.message.answer("Ban qilinadigan foydalanuvchi Telegram ID sini yuboring:")
    await callback.answer()


@router.message(BanUser.waiting_for_id)
async def ban_user_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        user_id = int(message.text.strip())
        await db.set_user_ban(user_id, True)
        await message.answer(f"🚫 {user_id} idli foydalanuvchi bloklandi.")
    except ValueError:
        await message.answer("Xato ID kiritildi.")
    await state.clear()


@router.callback_query(F.data == "admin_unban_user")
async def unban_user_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(UnbanUser.waiting_for_id)
    await callback.message.answer("Bani olib tashlanadigan foydalanuvchi Telegram ID sini yuboring:")
    await callback.answer()


@router.message(UnbanUser.waiting_for_id)
async def unban_user_finish(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
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
    if not is_admin(message.from_user.id):
        return
    await state.update_data(file_id=message.document.file_id)
    await state.set_state(AddBook.waiting_for_photo)
    await message.answer("Kitob muqovasi (rasm) yuboring yoki o'tkazib yuborish uchun /skip bosing:")


@router.message(Command("skip"), AddBook.waiting_for_photo)
async def skip_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(photo_id=None)
    await state.set_state(AddBook.waiting_for_desc)
    await message.answer("Kitob tavsifini yozing yoki /skip bosing:")


@router.message(AddBook.waiting_for_photo, F.photo)
async def add_book_got_photo(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(photo_id=message.photo[-1].file_id)
    await state.set_state(AddBook.waiting_for_desc)
    await message.answer("Kitob tavsifini yozing yoki /skip bosing:")


@router.message(Command("skip"), AddBook.waiting_for_desc)
async def skip_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(description=None)
    await state.set_state(AddBook.waiting_for_title)
    await message.answer("Kitob nomini yuboring:")


@router.message(AddBook.waiting_for_desc)
async def add_book_got_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(description=message.text.strip())
    await state.set_state(AddBook.waiting_for_title)
    await message.answer("Kitob nomini yuboring:")


@router.message(AddBook.waiting_for_title)
async def add_book_got_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
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
    if not is_admin(callback.from_user.id):
        return
    category_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    await db.add_book(category_id, data["title"], data["file_id"], data.get("photo_id"), data.get("description"))
    await state.clear()
    await callback.message.answer(f"✅ Kitob qo'shildi: {data['title']}")
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
@router.message(Command("cancel"), Broadcast.waiting_for_buttons)
async def send_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("Xabar yuborish bekor qilindi.")


@router.message(Broadcast.waiting_for_message)
async def send_got_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(chat_id=message.chat.id, message_id=message.message_id)
    
    await state.set_state(Broadcast.waiting_for_buttons)
    await message.answer(
        "Endi xabar ostiga qo'shiladigan tugmalarni yuboring.\n\n"
        "📝 **Format:**\n"
        "`Tugma nomi - https://havola.com`\n\n"
        "Yoki yonma-yon qo'shish uchun `|` bilan ajrating:\n"
        "`1-tugma - https://link1.com | 2-tugma - https://link2.com`\n\n"
        "Agar tugma kerak bo'lmasa, shunchaki **/skip** buyrug'ini yuboring.",
        parse_mode="Markdown"
    )


def create_inline_keyboard_from_text(text: str):
    if not text or text.strip() == "/skip":
        return None
        
    builder = InlineKeyboardBuilder()
    lines = text.strip().split("\n")
    
    for line in lines:
        buttons = line.split("|")
        row = []
        for btn in buttons:
            if "-" in btn:
                btn_text, btn_url = btn.split("-", 1)
                row.append(InlineKeyboardButton(text=btn_text.strip(), url=btn_url.strip()))
        if row:
            builder.row(*row)
            
    return builder.as_markup()


@router.message(Broadcast.waiting_for_buttons)
async def send_got_buttons(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(buttons_text=message.text.strip())
    data = await state.get_data()
    
    markup = create_inline_keyboard_from_text(data.get("buttons_text"))
    
    await message.answer("👀 Xabar foydalanuvchilarga mana shunday ko'rinishda yuboriladi:")
    try:
        await message.bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=data["chat_id"],
            message_id=data["message_id"],
            reply_markup=markup
        )
    except Exception as e:
        await message.answer("⚠️ Xabarni namoyish qilishda xatolik. URL havolalar xato bo'lishi mumkin. Qaytadan tekshiring.")
        return

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
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text("Bekor qilindi.")
    await callback.answer()


@router.callback_query(Broadcast.waiting_for_confirm, F.data == "broadcast_confirm")
async def send_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    await state.clear()

    markup = create_inline_keyboard_from_text(data.get("buttons_text"))
    users = await db.get_all_users()
    await callback.message.edit_text(f"⏳ Yuborilmoqda... (0/{len(users)})")

    sent = 0
    failed = 0
    blocked_count = 0

    for user_id in users:
        try:
            await callback.bot.copy_message(
                chat_id=user_id,
                from_chat_id=data["chat_id"],
                message_id=data["message_id"],
                reply_markup=markup
            )
            sent += 1
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            try:
                await callback.bot.copy_message(
                    chat_id=user_id,
                    from_chat_id=data["chat_id"],
                    message_id=data["message_id"],
                    reply_markup=markup
                )
                sent += 1
            except Exception:
                failed += 1
        except (TelegramForbiddenError, TelegramNotFound):
            failed += 1
            blocked_count += 1
            await db.delete_user(user_id)
        except Exception as e:
            logging.error(f"Xabar yuborishda xatolik: {e}")
            failed += 1

        await asyncio.sleep(0.05)

    report_text = (
        f"✅ Yuborish yakunlandi.\n\n"
        f"📤 Yuborildi: {sent}\n"
        f"❌ Yuborilmadi: {failed}\n"
        f"🗑 Bazadan o'chirilgan faol bo'lmaganlar: {blocked_count}"
    )
    await callback.message.answer(report_text)
    await callback.answer()
