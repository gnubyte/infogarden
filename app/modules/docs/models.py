from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.models import Base
from app import db_session

class QueryProperty:
    """Query property descriptor for models"""
    def __get__(self, instance, owner):
        return db_session.query(owner)

class DocumentFolder(Base):
    __tablename__ = 'document_folders'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    name = Column(String(200), nullable=False)
    parent_id = Column(Integer, ForeignKey('document_folders.id'), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship('Organization', back_populates='document_folders')
    parent = relationship('DocumentFolder', remote_side=[id], backref='children')
    creator = relationship('User', foreign_keys=[created_by])
    
    def get_path(self):
        """Get the full path of the folder"""
        path = [self.name]
        current = self.parent
        while current:
            path.insert(0, current.name)
            current = current.parent
        return '/'.join(path)

class Document(Base):
    __tablename__ = 'documents'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    folder_id = Column(Integer, ForeignKey('document_folders.id'), nullable=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=True)
    content_type = Column(String(20), default='markdown', nullable=False)  # 'markdown' or 'html'
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship('Organization', back_populates='documents')
    folder = relationship('DocumentFolder', backref='documents')
    creator = relationship('User', foreign_keys=[created_by], back_populates='created_documents')
    updater = relationship('User', foreign_keys=[updated_by], back_populates='updated_documents')

class Software(Base):
    __tablename__ = 'software'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    title = Column(String(200), nullable=False)
    note = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)  # Size in bytes
    link = Column(String(500), nullable=True)  # Optional link to documentation
    uploaded_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    last_uploaded = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    download_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    organization = relationship('Organization', back_populates='software')
    uploader = relationship('User', foreign_keys=[uploaded_by])

