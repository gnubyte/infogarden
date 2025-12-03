from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.models import Base
from app import db_session

class QueryProperty:
    """Query property descriptor for models"""
    def __get__(self, instance, owner):
        return db_session.query(owner)

class Document(Base):
    __tablename__ = 'documents'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    content_type = Column(String(20), default='markdown', nullable=False)  # 'markdown' or 'html'
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship('Organization', back_populates='documents')
    creator = relationship('User', foreign_keys=[created_by], back_populates='created_documents')
    updater = relationship('User', foreign_keys=[updated_by], back_populates='updated_documents')

