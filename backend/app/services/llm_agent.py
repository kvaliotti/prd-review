from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langchain_core.tools import tool
from typing_extensions import Annotated, TypedDict

from app.core.config import settings
from app.models.message import Message
import logging
import time

logger = logging.getLogger(__name__)


class State(TypedDict):
    """State for the LangGraph agent"""
    messages: Annotated[list, add_messages]


@tool
def conversation_context_tool(question: str) -> str:
    """Tool to help maintain conversation context and provide relevant responses."""
    return f"Analyzing context for: {question}"


class EnhancedChatAgent:
    def __init__(self):
        # Initialize the OpenAI model
        self.model = ChatOpenAI(
            model="gpt-4.1",  # Using a more available model
            temperature=0.7,
            openai_api_key=settings.openai_api_key,
            max_tokens=1000
        )
        
        # Create tools for the agent
        self.tools = [conversation_context_tool]
        
        # Create the react agent using LangGraph
        self.agent = create_react_agent(
            model=self.model,
            tools=self.tools,
            state_modifier=self._get_system_prompt()
        )
        
        # Create a simple title generation model
        self.title_model = ChatOpenAI(
            model="gpt-4.1",
            temperature=0.5,
            openai_api_key=settings.openai_api_key,
            max_tokens=20
        )
    
    def generate_response(self, message_history: List[Message], new_message: str, user_context: Optional[Dict] = None) -> str:
        """Generate response using LangGraph agent"""
        try:
            # Prepare messages for the agent
            messages = []
            
            # Add conversation history (limit to last 10 messages for context)
            recent_history = message_history[-10:] if len(message_history) > 10 else message_history
            for msg in recent_history:
                if msg.role == "user":
                    messages.append(HumanMessage(content=msg.content))
                elif msg.role == "assistant":
                    messages.append(AIMessage(content=msg.content))
            
            # Add the new user message
            messages.append(HumanMessage(content=new_message))
            
            # Create the state
            state = {"messages": messages}
            
            # Invoke the agent
            result = self.agent.invoke(state)
            
            # Extract the AI response from the result
            if result and "messages" in result:
                last_message = result["messages"][-1]
                if hasattr(last_message, 'content'):
                    return last_message.content
            
            return "I apologize, but I couldn't generate a response."
            
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I apologize, but I encountered an error. Please try again."
    
    def generate_chat_title(self, first_message: str) -> str:
        """Generate a title for a chat based on the first message"""
        try:
            messages = [
                SystemMessage(content="Generate a concise, descriptive title (3-5 words) for this conversation based on the first message. Return only the title, no quotes or explanations."),
                HumanMessage(content=f"First message: {first_message}")
            ]
            
            response = self.title_model.invoke(messages)
            
            title = response.content.strip().strip('"\'')
            if len(title) > 50:
                title = title[:47] + "..."
            
            return title if title else "New Conversation"
            
        except Exception as e:
            logger.error(f"Error generating chat title: {e}")
            return "New Conversation"
    
    def analyze_conversation_context(self, messages: List[Message]) -> Dict[str, Any]:
        """Analyze conversation to extract context and insights"""
        try:
            if not messages:
                return {}
            
            context = {
                "message_count": len(messages),
                "user_messages": len([m for m in messages if m.role == "user"]),
                "assistant_messages": len([m for m in messages if m.role == "assistant"]),
                "topics": [],  # Could be enhanced with topic extraction
                "sentiment": "neutral",  # Could be enhanced with sentiment analysis
                "last_activity": messages[-1].created_at if messages else None
            }
            
            return context
            
        except Exception as e:
            logger.error(f"Error analyzing conversation context: {e}")
            return {}
    
    def _get_system_prompt(self, user_context: Optional[Dict] = None) -> str:
        """Get system prompt with user context"""
        base_prompt = """You are a helpful, knowledgeable, and friendly AI assistant.

Your characteristics:
- Provide clear, accurate, and helpful responses
- Be conversational but professional
- Ask clarifying questions when needed
- Admit when you don't know something
- Remember context from our conversation history
- Be concise unless detailed explanations are requested

Guidelines:
- Format code blocks with proper syntax highlighting
- Use markdown for better readability when appropriate
- Break down complex topics into digestible parts
- Provide examples when helpful
- Be encouraging and supportive

Remember: You're having a conversation with a user, so maintain context and refer back to previous messages when relevant."""
        
        if user_context:
            base_prompt += f"\n\nContext: You are chatting with {user_context.get('user_email', 'a user')} in a chat titled '{user_context.get('chat_title', 'Untitled Chat')}'."
        
        return base_prompt


# For backward compatibility, keep the original class names as well
SimpleChatAgent = EnhancedChatAgent
ChatAgent = EnhancedChatAgent 