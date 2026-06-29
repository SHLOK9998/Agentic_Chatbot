import React, { useState, useEffect, useRef } from 'react';
import { 
  MessageSquare, Plus, Trash2, Upload, Shield, Settings, 
  LogOut, Send, FileText, Lock, User, Mail, RefreshCw, 
  AlertCircle, CheckCircle2, FileUp, Sparkles, BookOpen 
} from 'lucide-react';

const API_BASE = "http://localhost:8000/api";

function App() {
  // --- Auth States ---
  const [user, setUser] = useState(() => {
    const saved = localStorage.getItem('chat_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [currentView, setCurrentView] = useState('chat'); // 'chat', 'admin', 'settings'
  const [authMode, setAuthMode] = useState('login'); // 'login', 'signup'
  const [signupForm, setSignupForm] = useState({ name: '', email: '', password: '', confirmPassword: '' });
  const [loginForm, setLoginForm] = useState({ email: '', password: '' });
  
  // --- Admin States ---
  const [adminKey, setAdminKey] = useState('');
  const [documents, setDocuments] = useState([]);
  const [uploadStatus, setUploadStatus] = useState({ type: '', message: '' });
  const [isUploading, setIsUploading] = useState(false);

  // --- Chat States ---
  const [threads, setThreads] = useState(() => {
    const saved = localStorage.getItem('chat_threads');
    return saved ? JSON.parse(saved) : [];
  });
  const [currentThreadId, setCurrentThreadId] = useState(() => {
    return localStorage.getItem('current_thread_id') || null;
  });
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [isSending, setIsSending] = useState(false);

  // --- Alert States ---
  const [alert, setAlert] = useState({ type: '', message: '' });

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);

  // --- Effects ---
  useEffect(() => {
    if (user) {
      localStorage.setItem('chat_user', JSON.stringify(user));
    } else {
      localStorage.removeItem('chat_user');
    }
  }, [user]);

  useEffect(() => {
    localStorage.setItem('chat_threads', JSON.stringify(threads));
  }, [threads]);

  useEffect(() => {
    if (currentThreadId) {
      localStorage.setItem('current_thread_id', currentThreadId);
      fetchMessages(currentThreadId);
    } else {
      localStorage.removeItem('current_thread_id');
      setMessages([]);
    }
  }, [currentThreadId]);

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (currentView === 'admin' && user?.role === 'admin') {
      fetchDocuments();
    }
  }, [currentView, user]);

  const showAlert = (type, message) => {
    setAlert({ type, message });
    setTimeout(() => setAlert({ type: '', message: '' }), 5000);
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // --- API Handlers ---

  const handleSignup = async (e) => {
    e.preventDefault();
    if (signupForm.password !== signupForm.confirmPassword) {
      showAlert('error', 'Passwords do not match');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: signupForm.name,
          email: signupForm.email,
          password: signupForm.password,
          confirm_password: signupForm.confirmPassword
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Signup failed');

      showAlert('success', 'Signup successful! Please log in.');
      setAuthMode('login');
      setLoginForm({ email: signupForm.email, password: '' });
      setSignupForm({ name: '', email: '', password: '', confirmPassword: '' });
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Login failed');

      setUser(data);
      showAlert('success', `Welcome back, ${data.name}!`);
      // Start a thread automatically if none exists
      if (threads.length === 0) {
        createThread(data.id);
      }
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  const handleLogout = () => {
    setUser(null);
    setThreads([]);
    setCurrentThreadId(null);
    setMessages([]);
    setCurrentView('chat');
    showAlert('success', 'Logged out successfully');
  };

  const handleVerifyAdminKey = async (e) => {
    e.preventDefault();
    if (!user) return;
    try {
      const res = await fetch(`${API_BASE}/auth/verify-admin?user_id=${user.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ admin_secret: adminKey })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Upgrade failed');

      const updatedUser = { ...user, role: 'admin' };
      setUser(updatedUser);
      showAlert('success', 'Admin access granted!');
      setAdminKey('');
      setCurrentView('admin');
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  const createThread = async (userId = user?.id) => {
    if (!userId) return;
    try {
      const res = await fetch(`${API_BASE}/threads`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: userId,
          title: `Chat ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to create thread');

      setThreads(prev => [data, ...prev]);
      setCurrentThreadId(data.id);
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  const fetchMessages = async (threadId) => {
    try {
      const res = await fetch(`${API_BASE}/threads/${threadId}/messages`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load messages');
      setMessages(data);
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || !currentThreadId || isSending) return;

    const userMessageText = chatInput;
    setChatInput('');
    setIsSending(true);

    // Optimistically update UI with user message
    const tempUserMsg = {
      id: Math.random().toString(),
      role: 'user',
      content: userMessageText,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: user.id,
          thread_id: currentThreadId,
          message: userMessageText
        })
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to fetch chatbot response');

      // Reload messages list from DB to get citations and exact message indices
      fetchMessages(currentThreadId);
    } catch (err) {
      showAlert('error', err.message);
    } finally {
      setIsSending(false);
    }
  };

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`);
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to load documents');
      setDocuments(data);
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || !user) return;

    setIsUploading(true);
    setUploadStatus({ type: 'info', message: 'Ingesting document...' });

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await fetch(`${API_BASE}/documents/upload?user_id=${user.id}`, {
        method: 'POST',
        body: formData
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to upload document');

      setUploadStatus({ type: 'success', message: data.message });
      fetchDocuments();
    } catch (err) {
      setUploadStatus({ type: 'error', message: err.message });
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteDocument = async (docId) => {
    if (!window.confirm("Are you sure you want to delete this document? All its parsed text and embeddings will be removed permanently.") || !user) return;

    try {
      const res = await fetch(`${API_BASE}/documents/${docId}?user_id=${user.id}`, {
        method: 'DELETE'
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Failed to delete document');

      showAlert('success', 'Document deleted successfully.');
      fetchDocuments();
    } catch (err) {
      showAlert('error', err.message);
    }
  };

  // --- Auth View Layout ---
  if (!user) {
    return (
      <div className="auth-container">
        <div className="auth-card glass-panel">
          <div className="auth-header">
            <h1>RAG Chatbot</h1>
            <p>{authMode === 'login' ? 'Sign in to access your chat console' : 'Create your free conversational account'}</p>
          </div>

          {alert.message && (
            <div className={`alert alert-${alert.type}`}>
              {alert.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
              <span>{alert.message}</span>
            </div>
          )}

          {authMode === 'login' ? (
            <form onSubmit={handleLogin}>
              <div className="form-group">
                <label>Email Address</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
                  <input 
                    type="email" 
                    className="form-input" 
                    style={{ paddingLeft: '38px', width: '100%' }}
                    placeholder="name@company.com" 
                    value={loginForm.email}
                    onChange={e => setLoginForm({...loginForm, email: e.target.value})}
                    required 
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Password</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
                  <input 
                    type="password" 
                    className="form-input" 
                    style={{ paddingLeft: '38px', width: '100%' }}
                    placeholder="••••••••" 
                    value={loginForm.password}
                    onChange={e => setLoginForm({...loginForm, password: e.target.value})}
                    required 
                  />
                </div>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '10px' }}>
                Sign In
              </button>
            </form>
          ) : (
            <form onSubmit={handleSignup}>
              <div className="form-group">
                <label>Name</label>
                <div style={{ position: 'relative' }}>
                  <User size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
                  <input 
                    type="text" 
                    className="form-input" 
                    style={{ paddingLeft: '38px', width: '100%' }}
                    placeholder="Shlok" 
                    value={signupForm.name}
                    onChange={e => setSignupForm({...signupForm, name: e.target.value})}
                    required 
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Email Address</label>
                <div style={{ position: 'relative' }}>
                  <Mail size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
                  <input 
                    type="email" 
                    className="form-input" 
                    style={{ paddingLeft: '38px', width: '100%' }}
                    placeholder="name@company.com" 
                    value={signupForm.email}
                    onChange={e => setSignupForm({...signupForm, email: e.target.value})}
                    required 
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Password</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
                  <input 
                    type="password" 
                    className="form-input" 
                    style={{ paddingLeft: '38px', width: '100%' }}
                    placeholder="Min 6 characters" 
                    value={signupForm.password}
                    onChange={e => setSignupForm({...signupForm, password: e.target.value})}
                    required 
                  />
                </div>
              </div>

              <div className="form-group">
                <label>Confirm Password</label>
                <div style={{ position: 'relative' }}>
                  <Lock size={16} style={{ position: 'absolute', left: '12px', top: '14px', color: 'var(--text-muted)' }} />
                  <input 
                    type="password" 
                    className="form-input" 
                    style={{ paddingLeft: '38px', width: '100%' }}
                    placeholder="Repeat password" 
                    value={signupForm.confirmPassword}
                    onChange={e => setSignupForm({...signupForm, confirmPassword: e.target.value})}
                    required 
                  />
                </div>
              </div>

              <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '10px' }}>
                Sign Up
              </button>
            </form>
          )}

          <div className="auth-footer">
            {authMode === 'login' ? (
              <span>Don't have an account? <span className="auth-link" onClick={() => setAuthMode('signup')}>Sign Up</span></span>
            ) : (
              <span>Already have an account? <span className="auth-link" onClick={() => setAuthMode('login')}>Log In</span></span>
            )}
          </div>
        </div>
      </div>
    );
  }

  // --- Main Layout ---
  return (
    <div className="app-layout">
      {/* --- Sidebar --- */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div className="brand" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={20} style={{ color: 'var(--accent-primary)' }} />
            <span>Best RAG</span>
          </div>
          <button 
            className="btn btn-secondary" 
            style={{ padding: '6px 10px', borderRadius: '8px' }}
            onClick={() => createThread()}
            title="New Conversation"
          >
            <Plus size={16} />
          </button>
        </div>

        <div className="sidebar-content">
          <div className="thread-list-title">Conversations</div>
          {threads.length === 0 ? (
            <div style={{ padding: '20px 10px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              No chat history yet.
            </div>
          ) : (
            threads.map(thread => (
              <div 
                key={thread.id} 
                className={`thread-item ${currentThreadId === thread.id ? 'active' : ''}`}
                onClick={() => {
                  setCurrentThreadId(thread.id);
                  setCurrentView('chat');
                }}
              >
                <MessageSquare size={16} />
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {thread.title}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="sidebar-footer">
          <div className="user-profile">
            <div className="user-avatar">
              {user.name.charAt(0).toUpperCase()}
            </div>
            <div className="user-details">
              <div className="user-name">{user.name}</div>
              <div className={`user-role-badge ${user.role === 'admin' ? 'admin' : ''}`}>
                {user.role}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button 
              className={`btn btn-secondary`} 
              style={{ flex: 1, padding: '8px', fontSize: '0.85rem', borderColor: currentView === 'settings' ? 'var(--accent-primary)' : '' }}
              onClick={() => setCurrentView(currentView === 'settings' ? 'chat' : 'settings')}
              title="Settings"
            >
              <Settings size={16} />
            </button>

            {user.role === 'admin' && (
              <button 
                className={`btn btn-secondary`} 
                style={{ flex: 1, padding: '8px', fontSize: '0.85rem', borderColor: currentView === 'admin' ? 'var(--success)' : '' }}
                onClick={() => setCurrentView(currentView === 'admin' ? 'chat' : 'admin')}
                title="Admin Console"
              >
                <Shield size={16} />
              </button>
            )}

            <button 
              className="btn btn-danger" 
              style={{ padding: '8px' }}
              onClick={handleLogout}
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>

      {/* --- Main Panels --- */}
      <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', overflow: 'hidden' }}>
        {alert.message && (
          <div className={`alert alert-${alert.type}`} style={{ margin: '15px 30px 0', zIndex: 10 }}>
            {alert.type === 'success' ? <CheckCircle2 size={18} /> : <AlertCircle size={18} />}
            <span>{alert.message}</span>
          </div>
        )}

        {/* --- CHAT VIEW --- */}
        {currentView === 'chat' && (
          <div className="chat-container">
            <div className="chat-header">
              <div className="chat-title">
                <h2>{threads.find(t => t.id === currentThreadId)?.title || "Conversational Assistant"}</h2>
                <p>Hybrid RAG pipeline backed by MongoDB Atlas</p>
              </div>
              <div className="nav-buttons">
                <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)', display: 'inline-block' }}></span>
                  MongoDB Atlas Connected
                </div>
              </div>
            </div>

            <div className="chat-messages">
              {messages.length === 0 ? (
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)', gap: '14px' }}>
                  <BookOpen size={48} style={{ opacity: 0.15 }} />
                  <p style={{ fontSize: '1rem', fontWeight: 500 }}>Ask a question about your files</p>
                  <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: '320px', textAlign: 'center' }}>
                    Type your query below. The router will choose RAG model matching if relevant documents are available.
                  </p>
                </div>
              ) : (
                messages.map(msg => (
                  <div key={msg.id} className={`message-bubble ${msg.role}`}>
                    <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
                    
                    {/* Render Citations/Sources if present */}
                    {msg.role === 'assistant' && msg.sources && msg.sources.length > 0 && (
                      <div className="sources-container">
                        <div className="sources-header">
                          <BookOpen size={12} />
                          <span>Sources ({msg.sources.length})</span>
                        </div>
                        <div className="source-badges">
                          {msg.sources.map((src, i) => (
                            <span 
                              key={i} 
                              className="source-badge" 
                              title={`Snippet: "${src.snippet}"`}
                            >
                              <span>{src.filename}</span>
                              {src.source_page && (
                                <span style={{ opacity: 0.6, fontSize: '0.75rem' }}>(Pg {src.source_page})</span>
                              )}
                              <span style={{ color: 'var(--accent-primary)', fontWeight: 600 }}>
                                {src.relevance_score ? `${Math.round(src.relevance_score * 100)}%` : ''}
                              </span>
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    
                    <span className="message-time">
                      {msg.created_at ? new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                    </span>
                  </div>
                ))
              )}
              {isSending && (
                <div className="message-bubble assistant" style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--text-secondary)' }}>
                  <RefreshCw className="spin" size={16} style={{ animation: 'spin 1.5s linear infinite' }} />
                  <span>Assistant is thinking...</span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            <div className="chat-input-area">
              <form onSubmit={handleSendMessage} className="chat-input-container">
                <input 
                  type="text" 
                  className="chat-input"
                  placeholder="Ask a question..."
                  value={chatInput}
                  onChange={e => setChatInput(e.target.value)}
                  disabled={!currentThreadId || isSending}
                />
                <button 
                  type="submit" 
                  className="btn btn-primary" 
                  style={{ borderRadius: '12px', padding: '10px' }}
                  disabled={!currentThreadId || !chatInput.trim() || isSending}
                >
                  <Send size={18} />
                </button>
              </form>
            </div>
          </div>
        )}

        {/* --- SETTINGS VIEW --- */}
        {currentView === 'settings' && (
          <div className="panel-container">
            <div className="panel-header">
              <h1>Settings</h1>
              <p>Configure account parameters and request higher system privileges.</p>
            </div>

            <div className="panel-section">
              <h3><User size={18} /> Account Details</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '12px', fontSize: '0.95rem', marginTop: '10px' }}>
                <span style={{ color: 'var(--text-secondary)' }}>Name:</span>
                <span>{user.name}</span>
                
                <span style={{ color: 'var(--text-secondary)' }}>Email:</span>
                <span>{user.email}</span>
                
                <span style={{ color: 'var(--text-secondary)' }}>Account Role:</span>
                <span style={{ textTransform: 'capitalize', fontWeight: 600 }}>{user.role}</span>
              </div>
            </div>

            {user.role !== 'admin' && (
              <div className="panel-section">
                <h3><Shield size={18} /> Admin Access Activation</h3>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                  If you are an administrator, paste the system secret key below to upgrade your role and unlock document uploading and index deletion.
                </p>
                <form onSubmit={handleVerifyAdminKey} style={{ display: 'flex', gap: '12px' }}>
                  <input 
                    type="password" 
                    className="form-input" 
                    style={{ flex: 1 }}
                    placeholder="Enter admin secret key"
                    value={adminKey}
                    onChange={e => setAdminKey(e.target.value)}
                    required
                  />
                  <button type="submit" className="btn btn-primary">
                    Verify Access
                  </button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* --- ADMIN DASHBOARD VIEW --- */}
        {currentView === 'admin' && user?.role === 'admin' && (
          <div className="panel-container">
            <div className="panel-header">
              <h1>Admin Console</h1>
              <p>Direct management of RAG document collections, indices, and vector embeddings.</p>
            </div>

            {/* Document Upload Area */}
            <div className="panel-section">
              <h3><Upload size={18} /> Add Files to RAG Index</h3>
              <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '16px' }}>
                Supported formats: PDF, DOCX, XLSX, TXT. Documents will be chunked and converted into dense vector embeddings immediately.
              </p>
              
              <div 
                className="drop-zone"
                onClick={() => fileInputRef.current?.click()}
              >
                <FileUp className="drop-zone-icon" size={32} />
                <p style={{ fontWeight: 500 }}>Click to select a file</p>
                <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>PDF, DOCX, XLSX, or TXT up to 10MB</p>
                <input 
                  type="file" 
                  ref={fileInputRef} 
                  style={{ display: 'none' }} 
                  onChange={handleFileUpload}
                  accept=".pdf,.docx,.xlsx,.txt"
                  disabled={isUploading}
                />
              </div>

              {uploadStatus.message && (
                <div style={{ 
                  marginTop: '16px', 
                  padding: '12px 16px', 
                  borderRadius: '8px', 
                  fontSize: '0.9rem',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  background: uploadStatus.type === 'error' ? 'rgba(239, 68, 68, 0.1)' : uploadStatus.type === 'success' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(255, 255, 255, 0.05)',
                  color: uploadStatus.type === 'error' ? '#fca5a5' : uploadStatus.type === 'success' ? '#6ee7b7' : 'var(--text-primary)',
                  border: `1px solid ${uploadStatus.type === 'error' ? 'rgba(239, 68, 68, 0.2)' : uploadStatus.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : 'var(--border-glass)'}`
                }}>
                  {isUploading && <RefreshCw className="spin" size={16} style={{ animation: 'spin 1.5s linear infinite' }} />}
                  <span>{uploadStatus.message}</span>
                </div>
              )}
            </div>

            {/* Document Collection List */}
            <div className="panel-section">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <h3 style={{ margin: 0 }}><FileText size={18} /> Ingested Document Collection</h3>
                <button 
                  className="btn btn-secondary" 
                  style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                  onClick={fetchDocuments}
                >
                  <RefreshCw size={12} /> Reload
                </button>
              </div>

              {documents.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
                  No documents have been indexed yet.
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table className="document-table">
                    <thead>
                      <tr>
                        <th>Filename</th>
                        <th>Type</th>
                        <th>Chunks</th>
                        <th>Status</th>
                        <th style={{ textAlign: 'right' }}>Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map(doc => (
                        <tr key={doc.id}>
                          <td style={{ fontWeight: 500 }}>{doc.filename}</td>
                          <td style={{ textTransform: 'uppercase', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{doc.file_type}</td>
                          <td>{doc.total_chunks || 0}</td>
                          <td>
                            <span className={`status-indicator ${doc.status}`}>
                              {doc.status}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            <button 
                              className="btn btn-danger" 
                              style={{ padding: '6px 10px', borderRadius: '6px' }}
                              onClick={() => handleDeleteDocument(doc.id)}
                              title="Delete document and chunks"
                            >
                              <Trash2 size={14} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
