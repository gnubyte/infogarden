# InfoGarden - IT MSP Wiki System

A comprehensive wiki and knowledge management system designed for IT Managed Service Providers (MSPs) to manage multiple organizations.

## Features

- **Multi-Organization Support**: Manage multiple client organizations from a single platform
- **Role-Based Access Control (RBAC)**: 
  - Global Admin: Full system access
  - Account Manager / IT Admin: Organization-level admin access
  - IT Basic: Limited read/write access within organization
- **Documentation Module**: Markdown-based wiki with live preview, image paste support, and PDF export
- **Contacts Management**: Store and manage organization contacts with emergency contact flagging
- **Password Manager**: Encrypted password storage with 2FA secret support and QR code parsing
- **Global Search**: Real-time search across documents, contacts, and passwords with contextual results
- **Activity Logging**: 90-day audit trail with IP address tracking
- **Database Backups**: Automatic weekly backups (configurable) with manual backup/restore capabilities
- **Auto-Migrations**: Automatic schema migration on startup

## Tech Stack

- **Backend**: Flask (Python)
- **Database**: MySQL 8.0
- **Frontend**: Bootstrap 5, Modern JavaScript (ES6+)
- **Markdown Editor**: EasyMDE
- **PDF Export**: WeasyPrint
- **Encryption**: Fernet (cryptography library)
- **Containerization**: Docker Compose

## Quick Start

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd infogarden
   ```

2. **Set up environment variables**

   Create a `.env` file in the project root with the following variables:

   **Required:**
   - `SECRET_KEY`: A random secret key for Flask sessions
   - `ENCRYPTION_KEY`: A Fernet encryption key (generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)

   **Database Connection (choose one method):**
   
   **Option 1: Full connection string**
   ```bash
   DATABASE_URL=mysql+pymysql://user:password@host:port/database
   ```
   
   **Option 2: Individual components (recommended for Docker)**
   ```bash
   DB_HOST=localhost          # or 'db' when using docker-compose
   DB_PORT=3306
   DB_USER=infogarden
   DB_PASSWORD=your_password
   DB_NAME=infogarden
   ```

   **Optional:**
   - `FLASK_ENV`: Set to `production` for production deployments
   - `FLASK_PORT`: Port for the web service (default: 5000)
   - `BACKUP_ENABLED`: Enable/disable automatic backups (default: true)
   - `BACKUP_DAY`: Day of week for backups (default: sunday)
   - `BACKUP_HOUR`: Hour for backups (default: 0)
   - `BACKUP_MINUTE`: Minute for backups (default: 0)
   - `BACKUP_RETENTION_DAYS`: Days to keep backups (default: 30)

3. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Open http://localhost:5000
   - Create a global admin user via database or initial setup script

## Docker Deployment

For detailed Docker deployment instructions, including running without docker-compose, see [DOCKER.md](DOCKER.md).

## Project Structure

```
infogarden/
├── app/
│   ├── core/              # Core functionality (auth, models, encryption, etc.)
│   ├── modules/           # Feature modules (orgs, users, docs, contacts, passwords, search)
│   ├── templates/         # Jinja2 templates
│   ├── static/           # Static files (CSS, JS, uploads)
│   └── backups/           # Database backups
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Module Architecture

The application uses a modular architecture where each feature module has its own:
- `models.py`: SQLAlchemy models
- `routes.py`: Flask route handlers
- Templates in `templates/modules/<module_name>/`

Modules are dynamically loaded on application startup.

## Database Migrations

The system includes automatic migration detection and application on startup. It will:
- Detect new columns in models and add them to the database
- Safely handle schema changes
- Only drop columns if explicitly removed from models (safety measure)

## Backup System

- **Automatic Backups**: Configurable weekly backups (default: Sunday at midnight)
- **Manual Backups**: Create backups on-demand from Settings
- **Backup Management**: View, download, and restore backups from the Settings page
- **Retention**: Configurable backup retention period (default: 30 days)

## Security Features

- Password encryption using Fernet
- CSRF protection (Flask-WTF)
- SQL injection prevention (SQLAlchemy parameterized queries)
- XSS prevention (Jinja2 auto-escaping)
- Activity logging with IP addresses
- Role-based access control at route and template level

## Development

To run in development mode:

```bash
python run.py
```

## License

[Your License Here]

# infogarden
