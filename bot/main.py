from bot.settings import BOT_TOKEN, OPENAI_API_KEY, ASSISTANT_ID, YOUTUBE_API_KEY
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.dispatcher.router import Router
import logging
from api_integration.openai_api import ChatGPT
from api_integration.youtube_api import Youtube
from db.facade import DB


# storage = MemoryStorage()
bot_dp = Dispatcher()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
gpt = ChatGPT(api_key=OPENAI_API_KEY, assistant_id=ASSISTANT_ID)
youtube = Youtube()
db = DB()
user_router = Router()

bot_dp.include_router(user_router)
