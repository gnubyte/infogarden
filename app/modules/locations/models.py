from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.models import Base
from app import db_session

class QueryProperty:
    """Query property descriptor for models"""
    def __get__(self, instance, owner):
        return db_session.query(owner)

class Location(Base):
    __tablename__ = 'locations'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    name = Column(String(200), nullable=False)
    address = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    zip_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    organization = relationship('Organization', back_populates='locations')


