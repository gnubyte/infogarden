from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db_session

Base = declarative_base()

class QueryProperty:
    """Query property descriptor for models"""
    def __get__(self, instance, owner):
        return db_session.query(owner)

class User(UserMixin, Base):
    __tablename__ = 'users'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default='it_basic')
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    organization = relationship('Organization', back_populates='users')
    activity_logs = relationship('ActivityLog', back_populates='user')
    
    # Relationships to module models - using string references to avoid circular imports
    # These will be properly resolved when all models are loaded
    created_documents = relationship('Document', foreign_keys='Document.created_by', lazy='dynamic')
    updated_documents = relationship('Document', foreign_keys='Document.updated_by', lazy='dynamic')
    created_passwords = relationship('PasswordEntry', foreign_keys='PasswordEntry.created_by', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_global_admin(self):
        return self.role == 'global_admin'
    
    def is_org_admin(self):
        return self.role in ['account_manager', 'it_admin']
    
    def can_access_org(self, org_id):
        if self.is_global_admin():
            return True
        return self.org_id == org_id

class Organization(Base):
    __tablename__ = 'organizations'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default='active')  # active, inactive, archived
    logo_path = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    users = relationship('User', back_populates='organization')
    activity_logs = relationship('ActivityLog', back_populates='organization')
    
    # Relationships to module models
    documents = relationship('Document', back_populates='organization', cascade='all, delete-orphan')
    contacts = relationship('Contact', back_populates='organization', cascade='all, delete-orphan')
    passwords = relationship('PasswordEntry', back_populates='organization', cascade='all, delete-orphan')

class ActivityLog(Base):
    __tablename__ = 'activity_logs'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    org_id = Column(Integer, ForeignKey('organizations.id'), nullable=True)
    action_type = Column(String(50), nullable=False)  # view, create, update, delete
    resource_type = Column(String(50), nullable=False)  # document, contact, password, user, org
    resource_id = Column(Integer, nullable=True)
    ip_address = Column(String(45), nullable=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    user = relationship('User', back_populates='activity_logs')
    organization = relationship('Organization', back_populates='activity_logs')

class Role(Base):
    __tablename__ = 'roles'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    permissions = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)

class Setting(Base):
    __tablename__ = 'settings'
    query = QueryProperty()
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

