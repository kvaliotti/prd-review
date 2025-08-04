# Chat Application with GPT-4.1 and LangGraph

A full-stack chat application built with React.js frontend, FastAPI backend, PostgreSQL database, and LangGraph integration for conversational AI using OpenAI GPT-4.1.

## Features

- 🔐 **User Authentication**: Secure signup/login with JWT tokens
- 💬 **Multi-Chat Support**: Create and manage multiple chat conversations
- 🤖 **AI Integration**: GPT-4.1 powered responses via LangGraph
- 📚 **Chat History**: Persistent conversation history with context awareness
- 🎨 **Modern UI**: Clean, responsive React interface
- 🔒 **Secure**: Protected routes and proper authentication flow

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   React.js      │    │   FastAPI       │    │  PostgreSQL     │
│   Frontend      │◄──►│   Backend       │◄──►│   Database      │
│                 │    │                 │    │                 │
│ • Auth Forms    │    │ • JWT Auth      │    │ • Users         │
│ • Chat UI       │    │ • Chat API      │    │ • Chats         │
│ • Routing       │    │ • LangGraph     │    │ • Messages      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   OpenAI        │
                       │   GPT-4.1       │
                       └─────────────────┘
```

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **LangGraph**: Conversation flow management
- **SQLAlchemy**: ORM for database operations
- **PostgreSQL**: Primary database
- **JWT**: Authentication tokens
- **OpenAI API**: GPT-4.1 integration

### Frontend
- **React.js**: User interface framework
- **TypeScript**: Type-safe JavaScript
- **React Router**: Client-side routing
- **Axios**: HTTP client for API calls
- **CSS Modules**: Component styling

## Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL 13+
- OpenAI API key

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd prdreview
```

### 2. Database Setup

```bash
# Install PostgreSQL and create a database
createdb chatdb

# Or using PostgreSQL CLI
psql -U postgres
CREATE DATABASE chatdb;
\q
```

### 3. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Environment Configuration

Create a `.env` file in the `backend` directory:

```env
DATABASE_URL=postgresql://username:password@localhost:5432/chatdb
SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
OPENAI_API_KEY=your-openai-api-key-here
```

### 5. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install
```

## Running the Application

### Start the Backend

```bash
cd backend
source venv/bin/activate  # Activate virtual environment
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio
```

The backend will be available at: `http://localhost:8000`

### Start the Frontend

```bash
cd frontend
npm start
```

The frontend will be available at: `http://localhost:3000`

## Usage

1. **Register**: Create a new account at `/register`
2. **Login**: Sign in at `/login`
3. **Create Chat**: Click "New Chat" to start a conversation
4. **Chat**: Send messages and receive AI responses
5. **Switch Chats**: Use the sidebar to navigate between conversations

## API Endpoints

### Authentication
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info

### Chat Management
- `GET /chats` - Get user's chats
- `POST /chats` - Create new chat
- `GET /chats/{id}/messages` - Get chat messages
- `POST /chats/{id}/messages` - Send message

## Project Structure

```
prdreview/
├── backend/
│   ├── app/
│   │   ├── core/           # Configuration and security
│   │   ├── crud/           # Database operations
│   │   ├── database/       # Database connection
│   │   ├── models/         # SQLAlchemy models
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business logic (LangGraph)
│   │   └── main.py         # FastAPI application
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── context/        # React contexts
│   │   ├── services/       # API services
│   │   └── types.ts        # TypeScript types
│   └── package.json
└── docs/                   # Project documentation
```

## Key Features Explained

### LangGraph Integration
The application uses LangGraph to manage conversation flow with the AI. Each chat maintains its history, providing context-aware responses.

### Authentication Flow
- JWT tokens for secure authentication
- Refresh token mechanism for extended sessions
- Protected routes requiring authentication

### Chat Management
- Multiple conversations per user
- Persistent message history
- Real-time message updates

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Verify PostgreSQL is running
   - Check DATABASE_URL in .env file
   - Ensure database exists

2. **OpenAI API Error**
   - Verify OPENAI_API_KEY is correct
   - Check API quota and billing

3. **Frontend Not Loading**
   - Ensure backend is running on port 8000
   - Check CORS configuration in FastAPI

### Environment Variables

Ensure all required environment variables are set:
- `DATABASE_URL`: PostgreSQL connection string
- `SECRET_KEY`: JWT signing key
- `OPENAI_API_KEY`: OpenAI API access key

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions, please refer to the project documentation in the `docs/` directory or create an issue in the repository. 