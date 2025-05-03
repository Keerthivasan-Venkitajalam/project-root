import React, { useState, useEffect, useRef } from 'react';
import './App.css';

function App() {
  const [connected, setConnected] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [taskStatus, setTaskStatus] = useState(null);
  const wsRef = useRef(null);
  const userId = useRef(`user-${Math.random().toString(36).substr(2, 9)}`);

  useEffect(() => {
    // Connect to the MCP server
    wsRef.current = new WebSocket('ws://localhost:8080');
    
    wsRef.current.onopen = () => {
      console.log('Connected to MCP server');
      setConnected(true);
      
      // Register as a user
      const registerMsg = {
        type: 'REGISTER',
        sender: userId.current,
        recipient: '',
        content: JSON.stringify(['USER']),
        timestamp: Date.now(),
        trace_id: crypto.randomUUID()
      };
      
      wsRef.current.send(JSON.stringify(registerMsg));
    };
    
    wsRef.current.onclose = () => {
      console.log('Disconnected from MCP server');
      setConnected(false);
    };
    
    wsRef.current.onmessage = (event) => {
      const message = JSON.parse(event.data);
      
      if (message.type === 'RESPONSE') {
        // Handle response from an agent
        setMessages(prev => [...prev, {
          id: crypto.randomUUID(),
          sender: message.sender,
          content: message.content,
          timestamp: new Date(message.timestamp * 1000).toLocaleTimeString(),
          isResponse: true
        }]);
        
        setTaskStatus('complete');
      }
    };
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);
  
  const sendTask = () => {
    if (!input.trim() || !connected) return;
    
    const taskId = crypto.randomUUID();
    const traceId = crypto.randomUUID();
    
    // Add user message to the chat
    setMessages(prev => [...prev, {
      id: taskId,
      sender: 'You',
      content: input,
      timestamp: new Date().toLocaleTimeString(),
      isResponse: false
    }]);
    
    // Create and send task message
    const taskMsg = {
      type: 'TASK',
      sender: userId.current,
      recipient: 'coordinator-agent', // Direct to coordinator
      content: JSON.stringify({
        task: input,
        context: {
          user_id: userId.current,
          timestamp: Date.now()
        }
      }),
      timestamp: Math.floor(Date.now() / 1000),
      trace_id: traceId,
      message_id: taskId
    };
    
    wsRef.current.send(JSON.stringify(taskMsg));
    setTaskStatus('processing');
    setInput('');
  };
  
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Multi-Agent Design Assistant</h1>
        <div className="connection-status">
          Status: <span className={connected ? 'connected' : 'disconnected'}>
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </header>
      
      <main className="chat-container">
        <div className="messages">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>No messages yet. Start by describing your design task!</p>
            </div>
          ) : (
            messages.map(msg => (
              <div 
                key={msg.id} 
                className={`message ${msg.isResponse ? 'response' : 'user'}`}
              >
                <div className="message-header">
                  <span className="sender">{msg.sender}</span>
                  <span className="timestamp">{msg.timestamp}</span>
                </div>
                <div className="message-content">
                  {msg.isResponse ? (
                    <div dangerouslySetInnerHTML={{ 
                      __html: msg.content
                        .replace(/\n/g, '<br>')
                        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                    }} />
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            ))
          )}
          
          {taskStatus === 'processing' && (
            <div className="processing-indicator">
              <div className="dot"></div>
              <div className="dot"></div>
              <div className="dot"></div>
              <p>Agents are working on your request...</p>
            </div>
          )}
        </div>
      </main>
      
      <footer className="input-container">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Describe your design task (e.g., 'Design a landing page for a fitness app with a modern aesthetic')..."
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              sendTask();
            }
          }}
        />
        <button 
          onClick={sendTask}
          disabled={!connected || !input.trim()}
        >
          Send
        </button>
      </footer>
    </div>
  );
}

export default App;