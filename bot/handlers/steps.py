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


async def count_tokens(text: str) -> int:
    """Count tokens in text"""
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    return len(tokens)


async def process_voice_message(message: Message) -> str:
    voice_file = await message.bot.get_file(message.voice.file_id)
    voice_path = f"voice_messages/{message.voice.file_id}.ogg"
    # os.makedirs("voice_messages", exist_ok=True)
    # await message.bot.download_file(voice_file.file_path, voice_path)
    # print(f"Voice message saved: {voice_path}")

    # recognized_text = await recognize_speech(voice_path)
    # return recognized_text

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
        language_code = user_info.get("chosen_language", "en")

        if message.voice:
            await process_voice_message(message)
            error_text = "At this moment voice messages are not supported!"
            await message.answer(error_text)
            await state.clear()
            return False
    
        text = message.text.strip()
        token_count = await count_tokens(text)
        print(f"Token count: {token_count}, for text: {text}")
        if token_count > 200:
            error_text = texts.too_long_request.get(language_code)
            await message.answer(error_text)
            return False

        return True

    @staticmethod
    async def generate_workout(message: Message, state: FSMContext):
        user_id = message.from_user.id
        data = await state.get_data()
        user_info = data.get(f"user_{user_id}")
        language_code = user_info.get("chosen_language", "en")
        print(f"User message: {message.text}")

        # Check requests
        requests_count = await db.user_request_crud.get_requests_count(user_id=user_id)
        print(f"Requests count: {requests_count}")
        if requests_count >= 10:
            message_text = texts.too_many_requests_message.get(language_code)
            await message.answer(text=message_text)
            await state.clear()
            return

        # Save request
        await db.user_request_crud.save_request(user_id=user_id)

        message_text = texts.generating_workout_text.get(language_code)
        await message.answer(text=message_text)

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
            {message.text}
            """

        generated_workout = await gpt.generate_workout(prompt=prompt)
        exercise_number = 1
        for exercise in generated_workout:
            exersice_keys = list(exercise.keys())
            exercise_title = exercise.get(exersice_keys[0])
            exercise_description = exercise.get(exersice_keys[1])
            exercise_reps = exercise.get(exersice_keys[2])
            youtube_query = exercise.get(exersice_keys[3])
            youtube_url = await youtube.get_url(query=youtube_query)
            exercise_message_text = texts.exercise_text.get(language_code).format(
                exercise_number, exercise_title, exercise_description, exercise_reps, youtube_url)
            await message.answer(text=exercise_message_text)
            exercise_number += 1

        last_message = texts.finish_message.get(language_code)
        await message.answer(text=last_message)
        await state.clear()

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
