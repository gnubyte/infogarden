# Docker Deployment Guide

This guide covers deploying InfoGarden using Docker, both with and without docker-compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Variables](#environment-variables)
- [Docker Compose Deployment](#docker-compose-deployment)
- [Standalone Docker Deployment](#standalone-docker-deployment)
- [Building and Pushing Images](#building-and-pushing-images)
- [Troubleshooting](#troubleshooting)

## Prerequisites

- Docker Engine 20.10+ and Docker Compose 2.0+
- (Optional) Docker Hub account for pushing images

## Environment Variables

InfoGarden supports flexible database connection configuration through environment variables. You can use either a full connection string or individual components.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Flask secret key for sessions | `your-secret-key-here` |
| `ENCRYPTION_KEY` | Fernet encryption key for password storage | Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### Database Connection Variables

You can configure the database connection in two ways:

#### Option 1: Full Connection String (DATABASE_URL)

```bash
DATABASE_URL=mysql+pymysql://user:password@host:port/database
```

**Example:**
```bash
DATABASE_URL=mysql+pymysql://infogarden:mypassword@db:3306/infogarden
```

#### Option 2: Individual Components (Recommended)

When `DATABASE_URL` is not set, the application will build the connection string from individual components:

| Variable | Description | Default | Example |
|----------|-------------|---------|---------|
| `DB_HOST` | Database hostname | `localhost` | `db` (docker-compose) or `192.168.1.100` |
| `DB_PORT` | Database port | `3306` | `3306` |
| `DB_USER` | Database username | `infogarden` | `infogarden` |
| `DB_PASSWORD` | Database password | `infogarden` | `secure_password` |
| `DB_NAME` | Database name | `infogarden` | `infogarden` |

**Example:**
```bash
DB_HOST=db
DB_PORT=3306
DB_USER=infogarden
DB_PASSWORD=secure_password
DB_NAME=infogarden
```

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Flask environment | `development` |
| `FLASK_PORT` | Port for web service | `5000` |
| `BACKUP_ENABLED` | Enable automatic backups | `true` |
| `BACKUP_DAY` | Day of week for backups | `sunday` |
| `BACKUP_HOUR` | Hour for backups (0-23) | `0` |
| `BACKUP_MINUTE` | Minute for backups (0-59) | `0` |
| `BACKUP_RETENTION_DAYS` | Days to keep backups | `30` |

## Docker Compose Deployment

Docker Compose is the easiest way to deploy InfoGarden with both the application and database.

### Quick Start

1. **Create a `.env` file** in the project root:

```bash
# Required
SECRET_KEY=your-secret-key-here
ENCRYPTION_KEY=your-encryption-key-here

# Database (using individual components)
DB_HOST=db
DB_PORT=3306
DB_USER=infogarden
DB_PASSWORD=secure_password
DB_NAME=infogarden

# Optional
FLASK_ENV=production
FLASK_PORT=5000
BACKUP_ENABLED=true
```

2. **Start the services:**

```bash
docker-compose up -d
```

3. **Check logs:**

```bash
docker-compose logs -f web
```

4. **Access the application:**

Open http://localhost:5000 in your browser.

### Docker Compose Services

- **`db`**: MySQL 8.0 database container
- **`web`**: InfoGarden Flask application

### Volumes

Docker Compose creates persistent volumes for:
- `mysql_data`: Database files
- `uploads_data`: User-uploaded files
- `backups_data`: Database backups

### Stopping Services

```bash
docker-compose down
```

To remove volumes (⚠️ **WARNING**: This deletes all data):

```bash
docker-compose down -v
```

## Standalone Docker Deployment

If you have an existing MySQL database or want to run the application container separately:

### 1. Build the Image

```bash
docker build -t infogarden:latest .
```

### 2. Run the Container

#### Using Individual Database Components

```bash
docker run -d \
  --name infogarden_web \
  -p 5000:5000 \
  -e SECRET_KEY=your-secret-key \
  -e ENCRYPTION_KEY=your-encryption-key \
  -e DB_HOST=your-db-host \
  -e DB_PORT=3306 \
  -e DB_USER=infogarden \
  -e DB_PASSWORD=your-password \
  -e DB_NAME=infogarden \
  -e FLASK_ENV=production \
  -v infogarden_uploads:/app/app/static/uploads \
  -v infogarden_backups:/app/app/backups \
  infogarden:latest
```

#### Using DATABASE_URL

```bash
docker run -d \
  --name infogarden_web \
  -p 5000:5000 \
  -e SECRET_KEY=your-secret-key \
  -e ENCRYPTION_KEY=your-encryption-key \
  -e DATABASE_URL=mysql+pymysql://user:password@host:port/database \
  -e FLASK_ENV=production \
  -v infogarden_uploads:/app/app/static/uploads \
  -v infogarden_backups:/app/app/backups \
  infogarden:latest
```

### 3. Using Environment File

Create a `.env` file and use it:

```bash
docker run -d \
  --name infogarden_web \
  -p 5000:5000 \
  --env-file .env \
  -v infogarden_uploads:/app/app/static/uploads \
  -v infogarden_backups:/app/app/backups \
  infogarden:latest
```

### Connecting to External Database

When connecting to a database outside Docker:

1. **If database is on the host machine:**
   ```bash
   DB_HOST=host.docker.internal  # macOS/Windows
   # or
   DB_HOST=172.17.0.1  # Linux (Docker bridge IP)
   ```

2. **If database is on another server:**
   ```bash
   DB_HOST=192.168.1.100  # Replace with actual IP/hostname
   ```

3. **Ensure network connectivity:**
   - Check firewall rules
   - Verify database allows remote connections
   - Test connection: `mysql -h DB_HOST -u DB_USER -p`

## Building and Pushing Images

### Build for Local Use

```bash
docker build -t infogarden:latest .
```

### Build with Tag

```bash
docker build -t infogarden:v1.0.0 .
docker build -t your-dockerhub-username/infogarden:v1.0.0 .
```

### Build for Linux x86_64 (amd64) using buildx

For cross-platform builds or to ensure compatibility with Linux servers:

```bash
# Build and tag for linux/amd64
docker buildx build --platform linux/amd64 \
  -t infogarden:latest \
  -t infogarden:$(git rev-parse --short HEAD) \
  -t infogarden:$(date +%Y%m%d) \
  --load .
```

### Push to Docker Hub

1. **Login to Docker Hub:**
   ```bash
   docker login
   ```

2. **Tag the image:**
   ```bash
   docker tag infogarden:latest your-dockerhub-username/infogarden:latest
   docker tag infogarden:latest your-dockerhub-username/infogarden:v1.0.0
   ```

3. **Push the image (single platform):**
   ```bash
   docker push your-dockerhub-username/infogarden:latest
   docker push your-dockerhub-username/infogarden:v1.0.0
   ```

4. **Build and push directly using buildx (recommended for linux/amd64):**
   ```bash
   docker buildx build --platform linux/amd64 \
     -t your-dockerhub-username/infogarden:latest \
     -t your-dockerhub-username/infogarden:$(git rev-parse --short HEAD) \
     -t your-dockerhub-username/infogarden:$(date +%Y%m%d) \
     --push .
   ```

### Pull and Run from Docker Hub

```bash
docker pull your-dockerhub-username/infogarden:latest
docker run -d --name infogarden_web -p 5000:5000 --env-file .env your-dockerhub-username/infogarden:latest
```

## Troubleshooting

### Database Connection Issues

**Problem:** Application can't connect to database

**Solutions:**
1. Verify database is running: `docker-compose ps` or `docker ps`
2. Check database credentials in environment variables
3. Test database connection:
   ```bash
   docker-compose exec db mysql -u infogarden -p infogarden
   ```
4. Check network connectivity (for external databases):
   ```bash
   docker run --rm -it --network host alpine ping your-db-host
   ```

### Container Won't Start

**Problem:** Container exits immediately

**Solutions:**
1. Check logs: `docker-compose logs web` or `docker logs infogarden_web`
2. Verify all required environment variables are set
3. Check if port 5000 is already in use:
   ```bash
   lsof -i :5000
   ```

### Permission Issues

**Problem:** Can't write to volumes

**Solutions:**
1. Check volume permissions:
   ```bash
   docker-compose exec web ls -la /app/app/static/uploads
   ```
2. Fix permissions if needed:
   ```bash
   docker-compose exec web chown -R $(id -u):$(id -g) /app/app/static/uploads
   ```

### Environment Variables Not Loading

**Problem:** Environment variables not being read

**Solutions:**
1. Ensure `.env` file is in the project root
2. For docker-compose, variables are automatically loaded from `.env`
3. For standalone docker, use `--env-file .env` flag
4. Verify variable names match exactly (case-sensitive)

### Database Migration Issues

**Problem:** Database schema not updating

**Solutions:**
1. Check migration logs in application logs
2. Verify database user has CREATE/ALTER permissions
3. Manually run migrations if needed (check `app/core/migration.py`)

## Best Practices

1. **Never commit `.env` files** - They contain sensitive information
2. **Use strong passwords** - Generate secure passwords for production
3. **Regular backups** - Enable automatic backups and test restore procedures
4. **Monitor logs** - Regularly check application and database logs
5. **Update regularly** - Keep Docker images and dependencies up to date
6. **Use secrets management** - For production, consider Docker secrets or external secret managers
7. **Network security** - Use Docker networks to isolate services
8. **Resource limits** - Set appropriate CPU and memory limits for containers

## Production Deployment Tips

1. **Use reverse proxy** (nginx/traefik) in front of the application
2. **Enable HTTPS** - Use Let's Encrypt or similar
3. **Set `FLASK_ENV=production`** - Disables debug mode
4. **Use managed database** - Consider RDS, Cloud SQL, or similar for production
5. **Implement monitoring** - Use tools like Prometheus, Grafana, or Datadog
6. **Set up log aggregation** - Use ELK stack or similar
7. **Regular security updates** - Keep base images and dependencies updated
8. **Backup strategy** - Test backup and restore procedures regularly


