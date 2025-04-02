from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    waiting_for_workout = State()

class UserRegistrationState(StatesGroup):
    language_choice = State()
    # fitness_level_choice = State()
    # workout_level = State()
    # gender_choice = State()
    # warm_up_cool_down_choice = State()
    # confirm_health_state = State()

class UserWorkoutState(StatesGroup):
    workout_duration = State()
    workout_goal = State()
    workout_focus = State()
    workout_equipment = State()
    choose_focus = State()
    choose_equipment = State()

class UserUpdateState(StatesGroup):
    choosing_update = State()
    handling_update = State()