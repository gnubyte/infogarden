"""
Gunicorn configuration for production deployment
"""
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('FLASK_PORT', '5000')}"
backlog = 2048

# Worker processes
# Handle empty string from environment variables
gunicorn_workers = os.getenv('GUNICORN_WORKERS', '').strip()
if gunicorn_workers:
    try:
        workers = int(gunicorn_workers)
    except ValueError:
        workers = multiprocessing.cpu_count() * 2 + 1
else:
    workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'sync'
worker_connections = 1000
timeout = 30
keepalive = 2

# Logging
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'infogarden'

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (if needed in future)
# keyfile = None
# certfile = None

def when_ready(server):
    """Called just after the server is started."""
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    """Called when a worker receives the INT or QUIT signal."""
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    """Called just before a worker is forked."""
    pass

def post_fork(server, worker):
    """Called just after a worker has been forked."""
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    """Called just before a new master process is forked."""
    server.log.info("Forking new master process")

def on_reload(server):
    """Called to recycle workers during a reload via SIGHUP."""
    server.log.info("Reloading: spawning new workers")

def worker_abort(worker):
    """Called when a worker times out."""
    worker.log.info("worker timed out")

