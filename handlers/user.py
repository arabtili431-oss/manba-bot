from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db
from config import ADMIN_IDS

router = Router()

class ContactAdmin(StatesGroup):
    waiting_for_message = State()

@router.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    await db.add_user(user.id, user.full_name)
    
    if await db.is_user_banned(user.id):
        await message.answer("Siz botdan bloklangansiz. ❌")
        return

    builder = InlineKeyboardBuilder()
    categories = await db.get_categories()
    for cat_id, name in categories:
        builder.button(text=name, callback_data=f"cat:{cat_id}")
    
    builder.button(text="📞 Adminga murojaat", callback_data="user_contact")
    builder.adjust(1)

    await message.answer(
        "Assalomu alaykum! Kerakli bo'limni tanlang yoki adminga murojaat yuboring:",
        reply_markup=builder.as_markup()
    )

# --- MUROJAAT QILISH (CONTACT) ---

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
            print(f"Adminga yuborishda xatolik {admin_id}: {e}")
            
    await message.answer("✅ Murojaatingiz adminga yuborildi! Tez orada javob qaytaramiz.")
