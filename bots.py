"""
Python Kod Ishlatuvchi Telegram Bot
Faqat owner uchun — xavfsiz rejim

O'rnatish:
pip install aiogram python-dotenv

.env fayl:
BOT_TOKEN=your_token
OWNER_ID=your_telegram_id  # @userinfobot dan oling
"""

import asyncio
import io
import os
import sys
import traceback
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8664018305:AAEHkWBdMtY6Yt9braqezYfX06wrWk_9sow)
OWNER_ID = int(os.getenv("OWNER_ID", "6805613901"))  # Faqat shu odam ishlatishi mumkin

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()

# Har bir sессiya uchun global o'zgaruvchilar saqlanadi
user_globals = {}


def get_globals(user_id: int) -> dict:
    if user_id not in user_globals:
        user_globals[user_id] = {"__builtins__": __builtins__}
    return user_globals[user_id]


async def run_code(code: str, user_id: int) -> str:
    """Kodni xavfsiz ishga tushirish"""
    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    
    globs = get_globals(user_id)
    result_value = None
    error = None

    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            # Oxirgi ifodani eval qilishga urinish (natijani ko'rsatish uchun)
            try:
                import ast
                tree = ast.parse(code, mode='exec')
                
                # Oxirgi satr expression bo'lsa, uni eval qilamiz
                if tree.body and isinstance(tree.body[-1], ast.Expr):
                    last_expr = tree.body.pop()
                    exec(compile(tree, '<string>', 'exec'), globs)
                    result_value = eval(
                        compile(ast.Expression(last_expr.value), '<string>', 'eval'),
                        globs
                    )
                else:
                    exec(compile(tree, '<string>', 'exec'), globs)
            except Exception as e:
                error = traceback.format_exc()
    except Exception as e:
        error = traceback.format_exc()

    output = stdout_capture.getvalue()
    stderr_output = stderr_capture.getvalue()

    # Natijani formatlash
    parts = []

    if output:
        parts.append(f"📤 Output:\n{output.rstrip()}")

    if result_value is not None:
        parts.append(f"✅ Natija: {repr(result_value)}")

    if stderr_output:
        parts.append(f"⚠️ Stderr:\n{stderr_output.rstrip()}")

    if error:
        # Xato xabarini qisqartirish
        short_error = "\n".join(error.strip().split("\n")[-3:])
        parts.append(f"❌ Xato:\n{short_error}")

    if not parts:
        parts.append("✅ Kod muvaffaqiyatli bajarildi (output yo'q)")

    return "\n\n".join(parts)


# ===================== HANDLERLAR =====================

@router.message(CommandStart())
async def start_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        await message.answer("⛔ Bu bot faqat egasi uchun.")
        return

    await message.answer(
        "👨‍💻 <b>Python Executor Bot</b>\n\n"
        "Ishlatiш usullari:\n\n"
        "1️⃣ Kod yuboring — to'g'ridan-to'g'ri:\n"
        "<code>print('Salom dunyo!')</code>\n\n"
        "2️⃣ /run buyrug'i bilan:\n"
        "<code>/run 2 + 2</code>\n\n"
        "3️⃣ Ko'p qatorli kod:\n"
        "Kod blokini yuboring\n\n"
        "📌 Komandalar:\n"
        "/start — boshlash\n"
        "/clear — o'zgaruvchilarni tozalash\n"
        "/vars — joriy o'zgaruvchilarni ko'rish\n",
        parse_mode="HTML"
    )


@router.message(Command("clear"))
async def clear_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    user_globals.pop(message.from_user.id, None)
    await message.answer("🧹 O'zgaruvchilar tozalandi!")


@router.message(Command("vars"))
async def vars_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    
    globs = get_globals(message.from_user.id)
    user_vars = {
        k: repr(v) for k, v in globs.items()
        if not k.startswith("_") and k != "__builtins__"
    }
    
    if not user_vars:
        await message.answer("📭 Hozircha o'zgaruvchilar yo'q.")
        return
    
    text = "📦 <b>Joriy o'zgaruvchilar:</b>\n\n"
    for k, v in user_vars.items():
        val_short = v[:50] + "..." if len(v) > 50 else v
        text += f"<code>{k}</code> = {val_short}\n"
    
    await message.answer(text, parse_mode="HTML")


@router.message(Command("run"))
async def run_command_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    
    code = message.text.replace("/run", "", 1).strip()
    if not code:
        await message.answer("❗ Kod kiriting: /run print('salom')")
        return
    
    await execute_and_reply(message, code)


@router.message(F.text & ~F.text.startswith("/"))
async def code_handler(message: Message):
    if message.from_user.id != OWNER_ID:
        return
    
    code = message.text.strip()
    
    # Kod bloki formati: ```python ... ```
    if code.startswith("```") and code.endswith("```"):
        code = code.strip("`")
        if code.startswith("python"):
            code = code[6:].strip()
    
    await execute_and_reply(message, code)


async def execute_and_reply(message: Message, code: str):
    """Kodni ishga tushirib natijasini yuborish"""
    thinking_msg = await message.answer("⚙️ Ishga tushirilmoqda...")
    
    try:
        # Timeout bilan ishga tushirish (30 sekund)
        result = await asyncio.wait_for(
            run_code(code, message.from_user.id),
            timeout=30.0
        )
    except asyncio.TimeoutError:
        result = "⏱ Timeout! Kod 30 sekunddan ko'p vaqt oldi."
    except Exception as e:
        result = f"❌ Kutilmagan xato: {e}"
    
    # Natija juda uzun bo'lsa, fayl sifatida yuborish
    if len(result) > 4000:
        result_file = io.BytesIO(result.encode())
        result_file.name = f"output_{datetime.now().strftime('%H%M%S')}.txt"
        await thinking_msg.delete()
        await message.answer_document(
            result_file,
            caption="📄 Natija juda uzun, fayl sifatida yuborildi."
        )
    else:
        await thinking_msg.edit_text(
            f"<pre>{result}</pre>",
            parse_mode="HTML"
        )


# ===================== MAIN =====================

async def main():
    dp.include_router(router)
    print(f"🤖 Bot ishga tushdi! Owner ID: {OWNER_ID}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
                  
