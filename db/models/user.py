from sqlalchemy import (
    Column, Integer, String, select, ForeignKey, Boolean, DateTime, func
)
from db.crud import AsyncCRUD
from db.engine import Base
from datetime import datetime, timezone, date

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, index=True, primary_key=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=True)
    chosen_language = Column(String, nullable=False)

    def to_dict(self):
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}


class UserRequest(Base):
    __tablename__ = "user_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class UserCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(User)

    async def get_admin(self):
        async with self._get_session() as session:
            admin = await session.execute(select(self.model).where(self.model.role_id.is_(1)))
            if admin:
                return admin.scalars().first()

    async def set_status(self, user_id, status_type, value):
        async with self._get_session() as session:
            user = await session.execute(select(self.model).where(self.model.id.is_(user_id)))
            user = user.scalars().first()
            if user:
                if status_type == 'approved':
                    user.approved = value
                elif status_type == 'is_on_work_shift':
                    user.is_on_work_shift = value
                await session.commit()
                await session.refresh(user)
                return user
            return

    async def get_by_number(self, phone):
        async with self._get_session() as session:
            user = await session.execute(select(self.model).where(self.model.phone.is_(phone)))
            return user.scalars().first()


class UserRequestCRUD(AsyncCRUD):
    def __init__(self):
        super().__init__(UserRequest)

    async def save_request(self, user_id: int):
        async with self._get_session() as session:
            request = UserRequest(user_id=user_id)
            session.add(request)
            await session.commit()
            await session.refresh(request)
            return request
    
    async def get_requests_count(self, user_id: int) -> int:
        async with self._get_session() as session:
            today = date.today()
            start_of_day = datetime(today.year, today.month, today.day)
            
            query = select(func.count()).where(
                UserRequest.user_id == user_id,
                UserRequest.timestamp >= start_of_day
            )
            result = await session.execute(query)
            return result.scalar()
    
    async def get_daily_requests_summary(self) -> dict:
        async with self._get_session() as session:
            today = date.today()
            start_of_day = datetime(today.year, today.month, today.day)
            
            query = select(UserRequest.user_id, func.count()).where(
                UserRequest.timestamp >= start_of_day
            ).group_by(UserRequest.user_id)
            
            result = await session.execute(query)
            return {row[0]: row[1] for row in result.fetchall()}
