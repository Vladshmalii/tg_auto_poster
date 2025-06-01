from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float, Date, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, date

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(255))
    language = Column(String(10), default='ru')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subscriptions = relationship("Subscription", back_populates="user")
    autopost_settings = relationship("AutopostSettings", back_populates="user")
    test_post_limits = relationship("TestPostLimit", back_populates="user")


class Subscription(Base):
    __tablename__ = 'subscriptions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    plan_type = Column(Integer, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")


class AutopostSettings(Base):
    __tablename__ = 'autopost_settings'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    channel_id = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)
    style = Column(String(50), default='formal')
    posts_per_day = Column(Integer, default=1)
    specific_times = Column(Text)
    weekdays_only = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="autopost_settings")


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='XTR')
    payment_method = Column(String(50))
    status = Column(String(20), default='pending')
    external_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


class ActionLog(Base):
    __tablename__ = 'action_logs'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    action_type = Column(String(100), nullable=False)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class TestPostLimit(Base):
    __tablename__ = 'test_post_limits'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    test_date = Column(Date, nullable=False, default=date.today)
    channel_username = Column(String(255), nullable=False)
    category = Column(String(100))
    style = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="test_post_limits")

    __table_args__ = (
        Index('idx_test_post_limits_user_created', 'user_id', 'created_at'),
        Index('idx_test_post_limits_user_date', 'user_id', 'test_date'),
        {'extend_existing': True}
    )