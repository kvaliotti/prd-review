import React, { useState, useEffect, useRef } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { chatAPI } from '../services/api';
import { Chat, Message } from '../types';
import './ChatInterface.css';

const ChatInterface: React.FC = () => {
  const { user, logout } = useAuth();
  const [chats, setChats] = useState<Chat[]>([]);
  const [selectedChat, setSelectedChat] = useState<Chat | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [newChatTitle, setNewChatTitle] = useState('');
  const [showNewChatModal, setShowNewChatModal] = useState(false);
  const [showChatSettings, setShowChatSettings] = useState(false);
  const [regeneratingTitle, setRegeneratingTitle] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetchChats();
    checkHealth();
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const checkHealth = async () => {
    try {
      const response = await chatAPI.healthCheck();
      console.log('API Health:', response.data);
    } catch (error) {
      console.error('Health check failed:', error);
    }
  };

  const fetchChats = async () => {
    try {
      const response = await chatAPI.getChats();
      setChats(response.data);
    } catch (error) {
      console.error('Failed to fetch chats:', error);
    }
  };

  const fetchMessages = async (chatId: number) => {
    try {
      const response = await chatAPI.getChatMessages(chatId);
      setMessages(response.data);
    } catch (error) {
      console.error('Failed to fetch messages:', error);
    }
  };

  const handleChatSelect = (chat: Chat) => {
    setSelectedChat(chat);
    setShowChatSettings(false);
    fetchMessages(chat.id);
  };

  const handleCreateChat = async () => {
    if (!newChatTitle.trim()) return;

    try {
      const response = await chatAPI.createChat(newChatTitle);
      setChats([response.data, ...chats]);
      setSelectedChat(response.data);
      setMessages([]);
      setNewChatTitle('');
      setShowNewChatModal(false);
    } catch (error) {
      console.error('Failed to create chat:', error);
    }
  };

  const handleRegenerateTitle = async () => {
    if (!selectedChat) return;

    setRegeneratingTitle(true);
    try {
      const response = await chatAPI.generateChatTitle(selectedChat.id);
      const newTitle = response.data.title;
      
      // Update selected chat
      setSelectedChat({ ...selectedChat, title: newTitle });
      
      // Update chat in the list
      setChats(prevChats => 
        prevChats.map(chat => 
          chat.id === selectedChat.id 
            ? { ...chat, title: newTitle }
            : chat
        )
      );
      
      setShowChatSettings(false);
    } catch (error) {
      console.error('Failed to regenerate title:', error);
    } finally {
      setRegeneratingTitle(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedChat || !newMessage.trim()) return;

    const userMessage = newMessage;
    setNewMessage('');
    setLoading(true);

    // Add user message to UI immediately
    const tempMessage: Message = {
      id: Date.now(),
      chat_id: selectedChat.id,
      role: 'user',
      content: userMessage,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempMessage]);

    try {
      const response = await chatAPI.sendMessage(selectedChat.id, userMessage);
      
      // Refresh messages to get the actual saved messages
      await fetchMessages(selectedChat.id);
      await fetchChats(); // Update chat list to reflect new activity
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove the temporary message on error
      setMessages(prev => prev.filter(msg => msg.id !== tempMessage.id));
    } finally {
      setLoading(false);
    }
  };

  const formatMessageTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const diffDays = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else if (diffDays === 1) {
      return 'Yesterday ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } else {
      return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
  };

  return (
    <div className="chat-container">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>Conversations</h2>
          <button onClick={() => setShowNewChatModal(true)}>New Chat</button>
        </div>
        <div className="chat-list">
          {chats.map((chat) => (
            <div
              key={chat.id}
              className={`chat-item ${selectedChat?.id === chat.id ? 'active' : ''}`}
              onClick={() => handleChatSelect(chat)}
            >
              <div className="chat-title" title={chat.title}>{chat.title}</div>
              <div className="chat-meta">
                {chat.message_count} messages • {formatMessageTime(chat.updated_at)}
              </div>
            </div>
          ))}
          {chats.length === 0 && (
            <div className="no-chats">
              <p>No chats yet. Create your first chat to get started!</p>
            </div>
          )}
        </div>
        <div className="sidebar-footer">
          <div className="nav-links">
            <Link to="/knowledge-base">Knowledge Base</Link>
            <Link to="/settings">Settings</Link>
          </div>
          {user && (
            <div className="user-info">
              <span>{user.email}</span>
              <button onClick={logout}>Logout</button>
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="chat-main">
        {selectedChat ? (
          <>
            <div className="chat-header">
              <div className="chat-header-content">
                <h2>{selectedChat.title}</h2>
                <div className="chat-actions">
                  <button 
                    onClick={() => setShowChatSettings(!showChatSettings)}
                    className="settings-btn"
                    title="Chat settings"
                  >
                    ⚙️
                  </button>
                </div>
              </div>
              
              {showChatSettings && (
                <div className="chat-settings">
                  <button 
                    onClick={handleRegenerateTitle}
                    disabled={regeneratingTitle}
                    className="regenerate-title-btn"
                  >
                    {regeneratingTitle ? 'Generating...' : '🔄 Regenerate Title'}
                  </button>
                  <div className="chat-info">
                    <small>
                      Created: {formatMessageTime(selectedChat.created_at)} • 
                      Last updated: {formatMessageTime(selectedChat.updated_at)}
                    </small>
                  </div>
                </div>
              )}
            </div>

            <div className="messages-container">
              {messages.length === 0 && (
                <div className="no-messages">
                  <div className="welcome-message">
                    <h3>Welcome to your chat!</h3>
                    <p>Start a conversation by typing a message below.</p>
                  </div>
                </div>
              )}
              
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={`message ${message.role}`}
                >
                  <div className="message-content">
                    {message.content}
                  </div>
                  <div className="message-time">
                    {formatMessageTime(message.created_at)}
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="message assistant">
                  <div className="message-content">
                    <div className="typing-indicator">
                      <span></span>
                      <span></span>
                      <span></span>
                      AI is thinking...
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <form onSubmit={handleSendMessage} className="message-form">
              <input
                type="text"
                value={newMessage}
                onChange={(e) => setNewMessage(e.target.value)}
                placeholder="Type your message..."
                disabled={loading}
                className="message-input"
              />
              <button 
                type="submit" 
                disabled={loading || !newMessage.trim()}
                className="send-btn"
              >
                {loading ? '...' : 'Send'}
              </button>
            </form>
          </>
        ) : (
          <div className="no-chat-selected">
            <div className="welcome-screen">
              <h2>Welcome to Chat App</h2>
              <p>Select a chat from the sidebar to start messaging, or create a new chat to begin.</p>
              <button 
                onClick={() => setShowNewChatModal(true)}
                className="welcome-new-chat-btn"
              >
                Create Your First Chat
              </button>
            </div>
          </div>
        )}
      </div>

      {/* New Chat Modal */}
      {showNewChatModal && (
        <div className="modal-overlay" onClick={() => setShowNewChatModal(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>Create New Chat</h3>
            <input
              type="text"
              value={newChatTitle}
              onChange={(e) => setNewChatTitle(e.target.value)}
              placeholder="Enter chat title..."
              className="modal-input"
              autoFocus
              onKeyPress={(e) => e.key === 'Enter' && handleCreateChat()}
            />
            <div className="modal-buttons">
              <button 
                onClick={() => setShowNewChatModal(false)}
                className="modal-btn cancel"
              >
                Cancel
              </button>
              <button 
                onClick={handleCreateChat}
                className="modal-btn create"
                disabled={!newChatTitle.trim()}
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChatInterface; 