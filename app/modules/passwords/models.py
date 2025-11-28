from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.models import Base
from app import db_session

class QueryProperty:
    """Query property descriptor for models"""
    def __get__(self, instance, owner):
        return db_session.query(owner)

class PasswordEntry(Base):
    __tablename__ = 'password_entries'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    title = Column(String(200), nullable=False)
    link = Column(String(500), nullable=True)
    username = Column(String(200), nullable=True)
    email = Column(String(200), nullable=True)
    encrypted_password = Column(Text, nullable=True)
    encrypted_2fa_secret = Column(Text, nullable=True)
    date_added = Column(DateTime, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    
    organization = relationship('Organization', back_populates='passwords')
    creator = relationship('User', back_populates='created_passwords')

