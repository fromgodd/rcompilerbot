import asyncio
import subprocess
import logging
from datetime import datetime
import os
import tempfile
import shutil

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent, ParseMode

# Configure logging with colors
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load blacklisted users from file
with open('blacklist.txt', 'r') as blacklist_file:
    BLACKLIST = {int(line.strip()) for line in blacklist_file}

# Load bot token from envd.txt
with open('envd.txt', 'r') as env_file:
    API_TOKEN = env_file.read().strip()

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

async def anti_loop_handler(message: types.Message):
    # Check if the message contains a potential infinite loop in R
    if "while(" in message.text or "for(" in message.text:
        await message.reply("Your command contains a potential infinite loop. It is not allowed.")
        log_message = f"\033[91m{datetime.now()} -  Anti-loop Protection - User ID: {message.from_user.id}, Username: {message.from_user.username}, Event: Blocked User for Infinite Loop\033[0m"
        logger.info(log_message)
        raise types.exceptions.MessageNotModified(message.message_id)

async def start_message(cx: types.CallbackQuery):
    welcome_message = (
        "Welcome to the R Playground bot!\n"
        "Send me any R code, and I'll execute it for you."
    )
    await cx.answer(welcome_message)

@dp.message_handler(commands=['start', 'help'], state="*")
async def send_welcome(message: types.Message):
    await message.reply("Welcome to the R Playground bot!\nSend me any R code, and I'll execute it for you.")
    log_message = f"\033[94m{datetime.now()} -  Start/Help Command - User ID: {message.from_user.id}, Username: {message.from_user.username}, Event: Start/Help Command\033[0m"
    logger.info(log_message)

@dp.message_handler(content_types=['text'])
async def process_r_code(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # Check if the user is blacklisted
    if user_id in BLACKLIST:
        await message.reply("You are blocked from using this service.")
        log_message = f"\033[91m{datetime.now()} -  Blacklisted User - User ID: {user_id}, Username: {username}, Event: Blocked User\033[0m"
        logger.info(log_message)
        return

    # Check for potential harmful commands in R code
    if "while(" in message.text or "for(" in message.text:
        await message.reply("Your command contains a potential infinite loop or harmful code. It is not allowed.")
        log_message = f"\033[91m{datetime.now()} -  Harmful Command Protection - User ID: {user_id}, Username: {username}, Event: Blocked User for Harmful Command\033[0m"
        logger.info(log_message)
        return

    r_code = message.text

    with tempfile.TemporaryDirectory() as temp_dir:
        r_code_file = os.path.join(temp_dir, "r_code.R")
        with open(r_code_file, "w") as f:
            f.write(r_code)

        try:
            # Execute R code within the temporary directory
            result = subprocess.check_output(["Rscript", r_code_file], cwd=temp_dir, timeout=5, stderr=subprocess.STDOUT, text=True)
            output_message = f" Output:\n`\n{result}\n`"
            log_message = f"\033[92m{datetime.now()} -  Success - User ID: {user_id}, Username: {username}, Event: Process R Code\033[0m"
            logger.info(log_message)
        except subprocess.CalledProcessError as e:
            output_message = f" Error:\n`\n{e.output}\n`"
            log_message = f"\033[91m{datetime.now()} -  Error - User ID: {user_id}, Username: {username}, Event: Process R Code, Error: {e.output}\033[0m"
            logger.error(log_message)

        await message.reply(output_message, parse_mode=ParseMode.MARKDOWN)

@dp.inline_handler(lambda query: True)
async def inline_handler(inline_query: InlineQuery):
    try:
        # Extract the R code from the inline query
        r_code = inline_query.query.strip()

        with tempfile.TemporaryDirectory() as temp_dir:
            r_code_file = os.path.join(temp_dir, "r_code.R")
            with open(r_code_file, "w") as f:
                f.write(r_code)

            # Execute R code using subprocess with a timeout of 5 seconds
            result = subprocess.check_output(["Rscript", r_code_file], cwd=temp_dir, timeout=5, stderr=subprocess.STDOUT, text=True)
            output_message = f" Output:\n`\n{result}\n`"

            # Create an inline article result with the R code and its output
            article = InlineQueryResultArticle(
                id='1',
                title='R Code Result',
                input_message_content=InputTextMessageContent(output_message, parse_mode=ParseMode.MARKDOWN),
                description='Execute R code inline',
            )

            await bot.answer_inline_query(inline_query.id, results=[article])
            log_message = f"\033[92m{datetime.now()} -  Success - User ID: {inline_query.from_user.id}, Username: {inline_query.from_user.username}, Event: Inline Query\033[0m"
            logger.info(log_message)
    except subprocess.CalledProcessError as e:
        # Handle errors
        error_message = f" Error:\n`\n{e.output}\n`"
        log_message = f"\033[91m{datetime.now()} -  Error - User ID: {inline_query.from_user.id}, Username: {inline_query.from_user.username}, Event: Inline Query, Error: {e.output}\033[0m"
        logger.error(log_message)
        await bot.answer_inline_query(inline_query.id, results=[InlineQueryResultArticle(id='1', title='Error', input_message_content=InputTextMessageContent(error_message, parse_mode=ParseMode.MARKDOWN))])

if __name__ == '__main__':
    from aiogram import executor

    loop = asyncio.get_event_loop()
    executor.start_polling(dp, loop=loop, skip_updates=True)
