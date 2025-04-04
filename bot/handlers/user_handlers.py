import asyncio
import re
import bot.texts as texts
import bot.keyboards as keyboards
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import bot.states as states
from bot.texts import workout_creation
from db.facade import DB
import bot.filters as filters
from aiogram.dispatcher.router import Router
from utils.functions import get_user_language, update_chosen_focuses
from aiogram.filters.command import Command
from bot.handlers.steps import UserRegistrationSteps, UserWorkoutCreationSteps

user_registration_steps = UserRegistrationSteps()
workout_creation_steps = UserWorkoutCreationSteps()

async def user_registration(router: Router):
    @router.message(filters.NotRegisteredUser())
    async def greeting_handler(message: Message, state: FSMContext):
        await user_registration_steps.final_registration_step(message=message, state=state)

async def user_workout_flow(router: Router):
    @router.message(filters.RegisteredUser())
    async def process_workout_request(message: Message, state: FSMContext):
        current_state = await state.get_state()

        if not current_state or current_state != states.UserWorkoutState.workout_duration:
            await state.set_state(states.UserWorkoutState.workout_duration)

        instruction = await workout_creation_steps.validate_message_content(message, state)
        if not instruction:
            await workout_creation_steps.get_workout_info_step(message=message, state=state)
        else:
            await workout_creation_steps.generate_workout(message=message, state=state, instruction=instruction)
    
    @router.message(states.UserWorkoutState.generating)
    async def ignore_messages_during_generation(message: Message):
        return

async def register_user_handlers(router: Router):   
    await user_registration(router=router)
    await user_workout_flow(router=router)


