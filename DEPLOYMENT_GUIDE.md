# 🚀 Production Deployment Guide

This guide covers deploying the enhanced chat application with all production features including monitoring, logging, rate limiting, and Docker containerization.

## 📋 Prerequisites

- Docker and Docker Compose
- PostgreSQL 13+ (if not using Docker)
- Redis (if not using Docker) 
- OpenAI API key
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)

## 🔧 Environment Setup

### 1. Clone and Setup

```bash
git clone <repository-url>
cd prdreview
```

### 2. Environment Variables

Create `.env` file in the backend directory:

```env
# Required Environment Variables
DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/chatdb
SECRET_KEY=your-super-secret-key-change-in-production-minimum-32-characters
OPENAI_API_KEY=your-openai-api-key-here

# Environment Configuration
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Security
PASSWORD_MIN_LENGTH=8
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Rate Limiting
RATE_LIMIT_ENABLED=true
REDIS_URL=redis://localhost:6379

# Monitoring
METRICS_ENABLED=true
HEALTH_CHECK_INTERVAL=30

# Application Settings
MAX_MESSAGE_LENGTH=4000
CHAT_TITLE_MAX_LENGTH=100
MAX_CHAT_HISTORY=100
```

### 3. OpenAI API Key Setup

```bash
# Set your OpenAI API key
export OPENAI_API_KEY="your-openai-api-key-here"
```

## 🐳 Docker Deployment (Recommended)

### Quick Start with Docker Compose

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service status
docker-compose ps
```

### Services Included

- **PostgreSQL**: Database with persistent storage
- **Redis**: Rate limiting and caching
- **Backend**: FastAPI application with production optimizations
- **Frontend**: React application with nginx
- **Prometheus**: Metrics collection (optional)
- **Grafana**: Monitoring dashboards (optional)

### Service URLs

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **Metrics**: http://localhost:8000/metrics
- **Prometheus**: http://localhost:9090 (with monitoring profile)
- **Grafana**: http://localhost:3001 (with monitoring profile)

### Enable Monitoring Stack

```bash
# Start with monitoring services
docker-compose --profile monitoring up -d

# Access Grafana
# URL: http://localhost:3001
# Username: admin
# Password: admin
```

## 🛠️ Manual Deployment

### 1. Database Setup

```bash
# Install PostgreSQL
sudo apt-get install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql
CREATE DATABASE chatdb;
CREATE USER myuser WITH ENCRYPTED PASSWORD 'mypassword';
GRANT ALL PRIVILEGES ON DATABASE chatdb TO myuser;
\q
```

### 2. Redis Setup

```bash
# Install Redis
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start the application
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 4. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Serve with nginx or your preferred web server
# Or use serve for testing:
npx serve -s build -l 3000
```

## 📊 Monitoring and Observability

### Health Checks

```bash
# Application health
curl http://localhost:8000/health

# Detailed service status
curl http://localhost:8000/stats
```

### Metrics Collection

```bash
# Prometheus metrics
curl http://localhost:8000/metrics

# Key metrics monitored:
# - HTTP request rates and latencies
# - Database connection pool status
# - LLM request success/failure rates
# - Authentication attempt rates
# - Error rates by endpoint
```

### Logging

The application uses structured logging with different levels:

- **Production**: JSON format for log aggregation
- **Development**: Human-readable console format

Log categories:
- `auth`: Authentication events
- `chat`: Chat operations
- `llm`: LLM interactions
- `database`: Database operations
- `security`: Security events

### Database Monitoring

```bash
# Check database connection pool
curl http://localhost:8000/stats

# Monitor PostgreSQL performance
sudo -u postgres psql -d chatdb -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

## 🔒 Security Considerations

### 1. Production Security Checklist

- ✅ Use strong SECRET_KEY (minimum 32 characters)
- ✅ Enable HTTPS in production
- ✅ Configure proper CORS origins
- ✅ Use environment variables for secrets
- ✅ Enable rate limiting
- ✅ Regular security updates
- ✅ Database connection encryption
- ✅ Input validation and sanitization

### 2. Rate Limiting Configuration

```python
# Rate limits by endpoint:
# /auth/*: 5 requests/minute
# /chats/* (POST): 30 requests/minute
# General API: 100 requests/minute
```

### 3. JWT Token Security

- Access tokens expire after 15 minutes
- Refresh tokens expire after 7 days
- Tokens are signed with HS256 algorithm

## 🔄 Backup and Recovery

### Database Backup

```bash
# Create backup
pg_dump -U myuser -h localhost chatdb > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
psql -U myuser -h localhost chatdb < backup_file.sql
```

### Docker Volume Backup

```bash
# Backup PostgreSQL data
docker run --rm -v chatapp_postgres_data:/data -v $(pwd):/backup ubuntu tar czf /backup/postgres_backup.tar.gz /data

# Restore PostgreSQL data
docker run --rm -v chatapp_postgres_data:/data -v $(pwd):/backup ubuntu tar xzf /backup/postgres_backup.tar.gz -C /
```

## 📈 Performance Optimization

### Database Performance

- Connection pooling enabled (10 base connections, 20 overflow)
- Proper indexing on frequently queried columns
- Query performance monitoring with pg_stat_statements

### Application Performance

- Async operations throughout
- Efficient state management
- Response caching where appropriate
- Database query optimization

### Frontend Performance

- Production build optimization
- Gzip compression enabled
- Static asset caching
- Code splitting (React)

## 🚨 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check database status
   docker-compose logs postgres
   
   # Verify connection
   psql -U myuser -h localhost -d chatdb
   ```

2. **OpenAI API Errors**
   ```bash
   # Check API key configuration
   curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
   ```

3. **Rate Limiting Issues**
   ```bash
   # Check Redis status
   redis-cli ping
   
   # Disable rate limiting temporarily
   export RATE_LIMIT_ENABLED=false
   ```

4. **Memory Issues**
   ```bash
   # Monitor container resources
   docker stats
   
   # Adjust container limits in docker-compose.yml
   ```

### Log Analysis

```bash
# View application logs
docker-compose logs -f backend

# Filter by log level
docker-compose logs backend | grep ERROR

# Monitor specific operations
docker-compose logs backend | grep "chat_id"
```

## 🔧 Scaling Considerations

### Horizontal Scaling

- Use multiple backend instances behind a load balancer
- Redis for shared session storage
- Database connection pooling
- Stateless application design

### Vertical Scaling

- Increase container resource limits
- Optimize database performance
- Monitor and adjust pool sizes

### Production Deployment

```yaml
# Example production docker-compose override
version: '3.8'
services:
  backend:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
    environment:
      - WORKERS=8
      - LOG_LEVEL=WARNING
```

## 📞 Support and Maintenance

### Regular Maintenance Tasks

1. **Database Maintenance**
   ```bash
   # Run VACUUM ANALYZE weekly
   sudo -u postgres psql -d chatdb -c "VACUUM ANALYZE;"
   ```

2. **Log Rotation**
   ```bash
   # Configure logrotate for application logs
   sudo logrotate /etc/logrotate.d/chatapp
   ```

3. **Security Updates**
   ```bash
   # Update container images
   docker-compose pull
   docker-compose up -d
   ```

4. **Backup Verification**
   ```bash
   # Test backup restoration monthly
   ./scripts/test_backup_restore.sh
   ```

### Monitoring Alerts

Set up alerts for:
- High error rates (>5%)
- Database connection pool exhaustion
- High response times (>2s)
- Failed authentication attempts
- LLM API failures

This deployment guide ensures your chat application runs reliably in production with proper monitoring, security, and scalability features. 