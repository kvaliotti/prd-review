-- Initialize Chat App Database
-- This script sets up the initial database structure and configurations

-- Set timezone
SET timezone = 'UTC';

-- Create extensions if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create indexes for better performance
-- Note: These will be created by Alembic migrations, but having them here as reference

-- Enable performance monitoring
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = 'all';

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Database configuration for chat application
COMMENT ON DATABASE chatdb IS 'Chat application database with LangGraph and GPT-4.1 integration';

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Chat App database initialized successfully';
END $$; 