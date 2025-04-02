from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    waiting_for_workout = State()

class UserRegistrationState(StatesGroup):
    language_choice = State()

class UserWorkoutState(StatesGroup):
    workout_duration = State()
    generating = State()

class UserUpdateState(StatesGroup):
    choosing_update = State()
    handling_update = State()