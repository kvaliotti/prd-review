# Technical Specifications

## Stack Overview
- **Frontend**: React.js with TypeScript
- **Backend**: Python FastAPI
- **Database**: PostgreSQL
- **LLM Integration**: LangGraph with OpenAI GPT-4.1
- **Authentication**: JWT tokens

## Architecture Patterns

### Frontend (React)
- **State Management**: React Context + hooks
- **Routing**: React Router
- **Styling**: CSS Modules or Tailwind CSS
- **HTTP Client**: Axios
- **Type Safety**: TypeScript with strict mode

### Backend (FastAPI)
- **API Design**: RESTful endpoints
- **Authentication**: JWT with refresh tokens
- **Database**: SQLAlchemy ORM with Alembic migrations
- **LLM Integration**: LangGraph for conversation flow
- **Validation**: Pydantic models
- **CORS**: Configured for frontend integration

### Database Schema
```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chats table
CREATE TABLE chats (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Messages table
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER REFERENCES chats(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL, -- 'user' or 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## LangGraph Integration
- **Agent Type**: Conversational agent with memory
- **Memory**: Chat history stored in PostgreSQL
- **Tools**: Basic conversation tools
- **Model**: OpenAI GPT-4.1

## Security Requirements
- Password hashing with bcrypt
- JWT token expiration (15 min access, 7 days refresh)
- Input validation and sanitization
- SQL injection prevention via ORM
- CORS configuration

## Error Handling
- Consistent error response format
- Logging for debugging
- User-friendly error messages
- Graceful degradation

## Performance Considerations
- Database connection pooling
- Async/await patterns
- Response caching where appropriate
- Pagination for chat history 