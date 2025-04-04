import asyncio
import re
import os
from typing import Literal

import tiktoken
import bot.texts as texts
import bot.keyboards as keyboards
from aiogram.types import Message, CallbackQuery, Voice
from aiogram.fsm.context import FSMContext
import bot.states as states
from bot.main import gpt, youtube, db, bot
from bot.states import UserWorkoutState
from bot.texts import warm_up_cool_down_message, exercise_text
import bot.filters as filters
from aiogram.dispatcher.router import Router
from utils.functions import get_user_language, get_language_from_state, get_placeholders, update_user_settings
from aiogram.filters.command import Command
import re
from datetime import datetime
from bot.settings import TELEGRAM_CHANNEL_ID, BOT_TOKEN
import aiohttp


async def count_tokens(text: str) -> int:
    """Count tokens in text"""
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    return len(tokens)


async def send_telegram_message_to_channel(text: str):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHANNEL_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(url, json=payload, timeout=10)

    except Exception as e:
        print(f"Failed to send message to channel: {e}")


async def process_voice_message(message: Message) -> str:
    voice_file = await message.bot.get_file(message.voice.file_id)
    voice_path = f"voice_messages/{message.voice.file_id}.ogg"
    os.makedirs("voice_messages", exist_ok=True)
    await message.bot.download_file(voice_file.file_path, voice_path)
    print(f"Voice message saved: {voice_path}")
    text = await gpt.transcribe_audio_to_text(voice_path)
    os.remove(voice_path)
    return text

class UserRegistrationSteps:
    @staticmethod
    async def final_registration_step(message: Message, state: FSMContext):
        user_language_code = message.from_user.language_code

        user_data = {"id": message.from_user.id,
                     "username": message.from_user.username,
                     "first_name": message.from_user.first_name,
                     "last_name": message.from_user.last_name,
                     "chosen_language": user_language_code}
        # print(f"USER DATA: {user_data}")
        await db.user_crud.create(**user_data)
        await state.update_data({f"user_{message.from_user.id}": user_data})
        await state.clear()
        await UserWorkoutCreationSteps.get_workout_info_step(message, state)


class UserWorkoutCreationSteps:
    @staticmethod
    async def validate_message_content(message: Message, state: FSMContext) -> bool:
        user_id = message.from_user.id
        data = await state.get_data()
        user_info = data.get(f"user_{user_id}", {})
        if not user_info:
            # print(f"Not find user in state in 'get_workout_info_step'")
            user = await db.user_crud.read(id_=user_id)
            user_info = {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "chosen_language": user.chosen_language
            }
            await state.update_data({f"user_{user_id}": user_info})

        language_code = user_info.get("chosen_language", "en")

        # Check requests
        requests_count = await db.user_request_crud.get_requests_count(user_id=user_id)
        print(f"Requests count: {requests_count}")
        if requests_count >= 10:
            message_text = texts.too_many_requests_message.get(language_code)
            await message.answer(text=message_text)
            await state.clear()
            return False

        if message.voice:
            text = await process_voice_message(message)
        else:
            text = message.text.strip()

        token_count = await count_tokens(text)
        print(f"Token count: {token_count}, for text: {text}")
        if token_count > 200:
            error_text = texts.too_long_request.get(language_code)
            await message.answer(error_text)
            await state.clear()
            return False

        return text

    @staticmethod
    async def generate_workout(message: Message, state: FSMContext, instruction: str):
        user_id = message.from_user.id
        data = await state.get_data()
        user_info = data.get(f"user_{user_id}")
        language_code = user_info.get("chosen_language", "en")
        print(f"User message: {instruction}")
        # Save request
        await db.user_request_crud.save_request(user_id=user_id)

        message_text = texts.generating_workout_text.get(language_code)
        await message.answer(text=message_text)
        await state.set_state(UserWorkoutState.generating)

        prompt = f"""
            From the Statement, deduce these parameters:
            {{
                "workout_goal",
                "workout_equipment",
                "fitness_level",
                "duration"
            }}
            Use these to create a workout in the statement’s language. Do not include warmup or cooldown.
            Give me the answers in the language of the Statement and in this format:
            1. exercise name,
            2. exercise description,
            3. Number of reps,
            4. Get a Video demo from youtube (Provide the search query I should use to find that exercise in English and make sure it includes the exercise name in English).
            Return result as json format with fields: name, description, reps, youtube_query.
            
            Statement:
            {instruction}
            """

        generated_workout = await gpt.generate_workout(prompt=prompt)
        print(f"Generated workout count: {len(generated_workout)}")

        youtube_queries = [exercise.get("youtube_query") for exercise in generated_workout]
        youtube_urls = await asyncio.gather(*[youtube.get_url(query) for query in youtube_queries])
        print(f"Generated YouTube links: {len(youtube_urls)}")

        full_workout_text = f"<b>Prompt:</b>\n{instruction}\n\n<b>AI Answer:</b>\n"
        for exercise_number, (exercise, youtube_url) in enumerate(zip(generated_workout, youtube_urls), start=1):
            exercise_title = exercise.get("name")
            exercise_description = exercise.get("description")
            exercise_reps = exercise.get("reps")

            exercise_message_text = texts.exercise_text.get(language_code).format(
                exercise_number, exercise_title, exercise_description, exercise_reps, youtube_url)
            full_workout_text += f"{exercise_message_text}\n\n"
            await message.answer(text=exercise_message_text)

        await send_telegram_message_to_channel(full_workout_text)

        last_message = texts.finish_message.get(language_code)
        await message.answer(text=last_message)
        await state.set_state(UserWorkoutState.workout_duration)

    @staticmethod
    async def get_workout_info_step(message: Message, state: FSMContext):
        user_id = message.from_user.id
        data = await state.get_data()
        user_info = data.get(f"user_{user_id}")
        if not user_info:
            print(f"Not find user in state in 'get_workout_info_step'")
            user = await db.user_crud.read(id_=user_id)
            user_info = {
                "id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "chosen_language": user.chosen_language
            }
            await state.update_data({f"user_{user_id}": user_info})

        language_code = user_info.get("chosen_language", "en")
        message_text = texts.start_messages.get(language_code)
        await message.answer(text=message_text)
        await state.set_state(UserWorkoutState.workout_duration)
