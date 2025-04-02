import asyncio
from db.models.user import UserCRUD, UserRequestCRUD

class DB:
    user_crud = UserCRUD()
    user_request_crud = UserRequestCRUD()
