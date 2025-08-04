#!/bin/bash

# Create .env file for the backend
cat > .env << 'ENVEOF'
# Database Configuration
DATABASE_URL=postgresql://myuser:mypassword@localhost:5432/chatdb

# Security Configuration
SECRET_KEY=your-super-secret-key-change-in-production-minimum-32-characters-long
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# OpenAI Configuration - REPLACE WITH YOUR ACTUAL API KEY
OPENAI_API_KEY=your-openai-api-key-here

# Environment
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Rate Limiting
RATE_LIMIT_ENABLED=false
REDIS_URL=redis://localhost:6379

# Monitoring
METRICS_ENABLED=true
HEALTH_CHECK_INTERVAL=30

# Application Settings
MAX_MESSAGE_LENGTH=4000
CHAT_TITLE_MAX_LENGTH=100
MAX_CHAT_HISTORY=100
ENVEOF

echo ".env file created successfully!"
echo ""
echo "⚠️  IMPORTANT: You need to replace 'your-openai-api-key-here' with your actual OpenAI API key!"
echo ""
echo "To edit the .env file, run: nano .env"
echo "Or open it in your preferred text editor."
