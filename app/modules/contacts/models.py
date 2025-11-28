from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.models import Base
from app import db_session

class QueryProperty:
    """Query property descriptor for models"""
    def __get__(self, instance, owner):
        return db_session.query(owner)

class Contact(Base):
    __tablename__ = 'contacts'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    name = Column(String(200), nullable=False)
    role = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(50), nullable=True)
    text_number = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    emergency_contact = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship('Organization', back_populates='contacts')

