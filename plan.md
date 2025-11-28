# IT MSP Wiki System Implementation Plan

## Architecture Overview

- **Backend**: Flask (Python) with SQLAlchemy ORM
- **Database**: MySQL 8.0
- **Frontend**: Bootstrap 5, modern JavaScript (vanilla JS preferred over jQuery)
- **Containerization**: Docker Compose
- **Markdown Editor**: EasyMDE (supports preview, image paste)
- **PDF Export**: WeasyPrint
- **Encryption**: Fernet (cryptography library) for password storage
- **2FA QR Parsing**: pyzbar + PIL for QR code image parsing

## Project Structure

```
infogarden/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── app/
│   ├── __init__.py
│   ├── models.py          # SQLAlchemy models
│   ├── routes.py          # Main route handlers
│   ├── auth.py            # Authentication & RBAC decorators
│   ├── encryption.py      # Password encryption utilities
│   ├── activity_logger.py # Activity logging middleware
│   ├── pdf_export.py      # PDF generation utilities
│   ├── templates/
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── orgs/
│   │   ├── users/
│   │   ├── docs/
│   │   ├── contacts/
│   │   ├── passwords/
│   │   └── search/
│   ├── static/
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   └── config.py
└── init.sql               # Database initialization
```

## Database Models

### Core Models

1. **User**: id, username, email, password_hash, role, org_id (nullable), created_at, last_login
2. **Organization**: id, name, description, created_at
3. **Document**: id, org_id, title, content (markdown), created_by, updated_by, created_at, updated_at
4. **Contact**: id, org_id, name, role, email, phone, text_number, notes, emergency_contact, created_at
5. **PasswordEntry**: id, org_id, title, link, username (optional), email (optional), encrypted_password, encrypted_2fa_secret, date_added, created_by
6. **ActivityLog**: id, user_id, org_id, action_type, resource_type, resource_id, ip_address, details (JSON), timestamp
7. **Role**: id, name, permissions (JSON)

### RBAC Roles

- **global_admin**: Full system access
- **account_manager**: Org-level admin (same as IT admin)
- **it_admin**: Org-level admin (same as account manager)
- **it_basic**: Read-only + limited write within org

## Implementation Steps

### 1. Docker & Environment Setup

- Create `docker-compose.yml` with Flask app and MySQL services
- Create `Dockerfile` for Flask application
- Set up environment variables (.env) for database credentials, encryption keys
- Create `init.sql` for database schema initialization

### 2. Flask Application Foundation

- Initialize Flask app with SQLAlchemy
- Configure MySQL connection
- Set up Flask-Login for session management
- Create base template with Bootstrap 5 navigation
- Implement login/logout routes

### 3. RBAC System

- Create `auth.py` with role-based decorators:
  - `@require_global_admin`
  - `@require_org_admin` (AM + IT Admin)
  - `@require_org_access`
- Implement permission checking middleware
- Create role management UI (global admin only)

### 4. Organization Management

- CRUD operations for organizations
- Organization selection/switching
- Organization context middleware
- List/create/edit/delete orgs (global admin)

### 5. User Management

- User CRUD with role assignment
- User activity log viewer (90-day retention)
- User profile management
- Password reset functionality

### 6. Activity Logging System

- Middleware to log all page views and actions
- Log: user_id, org_id, action_type, resource_type, resource_id, IP address, timestamp
- Auto-cleanup of logs older than 90 days
- Activity viewer in user management

### 7. Documentation Module

- Markdown editor (EasyMDE) with live preview
- Image paste support (upload to static/uploads, insert markdown)
- Document CRUD within org context
- Document versioning (optional, via updated_at tracking)
- Export to PDF functionality

### 8. Contacts Module

- Contact CRUD within org
- Fields: name, role, email, phone, text_number, notes, emergency_contact checkbox
- Contact list with filtering/search
- Emergency contacts filter view

### 9. Password Manager Module

- Encrypted password storage using Fernet
- Fields: title, link, username (optional), email (optional), encrypted_password, encrypted_2fa_secret, date_added
- 2FA secret key manual entry
- QR code image upload and parsing (pyzbar)
- Password reveal (decrypt on demand with audit log)
- Password generation utility

### 10. Global Search

- Search bar integrated in navbar (always visible)
- Full-text search across documents, contacts, passwords within user's RBAC permissions
- Respects org context and role-based access (only shows results user can access)
- Search results with contextual dropdown links (typeahead/autocomplete style)
- Highlight matching text
- Search result categorization by resource type
- AJAX-powered real-time search suggestions

### 11. PDF Export

- Use WeasyPrint to convert markdown documents to PDF
- Include org branding/header
- Export button on document view/edit pages

### 12. Security Features

- Password encryption key management (environment variable)
- CSRF protection (Flask-WTF)
- SQL injection prevention (SQLAlchemy parameterized queries)
- XSS prevention (Jinja2 auto-escaping)
- Secure session management

### 13. Frontend Enhancements

- Bootstrap 5 responsive design
- Modern JavaScript (ES6+) for interactions
- AJAX for dynamic content loading
- Image upload handling for markdown editor
- QR code image parsing UI

## Key Files to Create

1. **docker-compose.yml**: Flask + MySQL services, volumes, networks
2. **app/init.py**: Flask app factory, extensions initialization
3. **app/models.py**: All SQLAlchemy models with relationships
4. **app/routes.py**: Route handlers organized by module
5. **app/auth.py**: RBAC decorators and permission checks
6. **app/encryption.py**: Fernet encryption/decryption for passwords
7. **app/activity_logger.py**: Logging middleware and utilities
8. **app/pdf_export.py**: WeasyPrint PDF generation
9. **app/templates/base.html**: Bootstrap navigation, layout
10. **app/static/js/main.js**: Modern JS for interactions, search, image handling

## Dependencies (requirements.txt)

- Flask, Flask-Login, Flask-WTF
- SQLAlchemy, PyMySQL
- cryptography (Fernet)
- WeasyPrint
- pyzbar, Pillow (QR parsing)
- python-dotenv
- markdown (for rendering)

## Security Considerations

- Encryption key stored in environment variable, never in code
- Passwords hashed with bcrypt before Fernet encryption (double protection)
- Activity logs include IP addresses for audit trail
- Role-based access enforced at route and template level
- Input validation and sanitization on all forms