import { useState, useEffect, useRef, FormEvent } from 'react';
import ChatView from './components/ChatView';
import StatusPanel from './components/StatusPanel';
import LogViewer from './components/LogViewer';
import { startGame, API_ACTION_URL } from './api';
import { PlayerState, ChatMessage } from './types';
import { Terminal, Send, TerminalSquare } from 'lucide-react';
import clsx from 'clsx';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [playerState, setPlayerState] = useState<PlayerState | null>(null);
  const [inputText, setInputText] = useState('');

  const [isInitializing, setIsInitializing] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLogsOpen, setIsLogsOpen] = useState(false);

  const initGame = async () => {
    setIsInitializing(true);
    try {
      const { sessionId: sid, message, state } = await startGame();
      setSessionId(sid);
      setPlayerState(state);
      setMessages([{
        id: Math.random().toString(),
        role: 'system',
        text: message
      }]);
    } catch (err) {
      console.error(err);
      setMessages([{
        id: Math.random().toString(),
        role: 'system',
        text: 'Failed to connect to backend server. Please make sure FastAPI is running.',
        isError: true
      }]);
    } finally {
      setIsInitializing(false);
    }
  };

  useEffect(() => {
    initGame();
  }, []);

  const sendAction = async (action: string) => {
    if (!action.trim() || !sessionId || isStreaming || playerState?.game_over) return;

    const userMsgId = Math.random().toString();
    const sysMsgId = Math.random().toString();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: action },
      { id: sysMsgId, role: 'system', text: '', isStreaming: true }
    ]);
    setInputText('');
    setIsStreaming(true);

    try {
      const response = await fetch(API_ACTION_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, action_text: action })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');

      if (!reader) throw new Error("No response body");

      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: true });

          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.trim()) continue;
            try {
              const data = JSON.parse(line);
              if (data.type === 'chunk') {
                setMessages(prev => prev.map(m =>
                  m.id === sysMsgId ? { ...m, text: m.text + data.text } : m
                ));
              } else if (data.type === 'final') {
                setPlayerState(data.state);
              }
            } catch (e) {
              console.error("Failed to parse ndjson line", line, e);
            }
          }
        }
      }

      setMessages(prev => prev.map(m =>
        m.id === sysMsgId ? { ...m, isStreaming: false } : m
      ));
    } catch (err) {
      console.error(err);
      setMessages(prev => prev.map(m =>
        m.id === sysMsgId ? { ...m, isStreaming: false, isError: true, text: "网络断开或执行异常，请查看后台报错并可在此重试。" } : m
      ));
    } finally {
      setIsStreaming(false);
    }
  };

  const handleRetry = () => {
    // Find last user message
    const userMsg = [...messages].reverse().find(m => m.role === 'user');
    if (userMsg) {
      // Remove the errored system message
      setMessages(prev => prev.filter(m => !m.isError));
      sendAction(userMsg.text);
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendAction(inputText);
  };

  return (
    <div className="w-full h-full flex bg-[#0a0a0c] text-slate-200 font-sans overflow-hidden">

      {/* Left Chat Area 70% */}
      <div className="flex-[7] flex flex-col h-full relative border-r border-white/5 bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]">
        {/* Header */}
        <header className="h-16 shrink-0 flex items-center justify-between px-6 border-b border-white/5 bg-slate-900/60 backdrop-blur-md z-20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent-primary flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.5)]">
              <TerminalSquare className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white leading-tight">HF-Explore Runtime</h1>
              <p className="text-xs font-mono text-accent-primary uppercase tracking-wider">Neural Narrative Engine</p>
            </div>
          </div>
          <button
            onClick={() => setIsLogsOpen(true)}
            disabled={!sessionId}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50 text-sm font-medium"
          >
            <Terminal className="w-4 h-4" /> 后台巡航日志
          </button>
        </header>

        {/* Chat Stream */}
        {isInitializing ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4 text-accent-primary animate-pulse">
              <TerminalSquare className="w-12 h-12" />
              <p className="font-mono text-sm uppercase tracking-widest">初始化环境连接中...</p>
            </div>
          </div>
        ) : (
          <ChatView
            messages={messages}
            isStreaming={isStreaming}
            onRetry={handleRetry}
          />
        )}

        {/* Input Area */}
        <div className="p-6 pt-0 shrink-0 z-20">
          <form onSubmit={handleSubmit} className="relative group max-w-3xl mx-auto">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value.substring(0, 15))}
              disabled={isStreaming || playerState?.game_over || !sessionId}
              placeholder={playerState?.game_over ? "游戏已结束" : isStreaming ? "终端正在生成剧情..." : "输入你的指令动作 (最多15字)..."}
              className="w-full bg-slate-900/80 border border-slate-700 text-white rounded-2xl py-4 pl-6 pr-20 outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-all disabled:opacity-50 shadow-lg placeholder-slate-500 backdrop-blur-md"
            />

            <div className="absolute right-4 top-1/2 -translate-y-1/2 flex items-center gap-3">
              <span className={clsx("text-xs font-mono", inputText.length >= 15 ? "text-red-400" : "text-slate-500")}>
                {inputText.length}/15
              </span>

              <button
                type="submit"
                disabled={!inputText.trim() || isStreaming || playerState?.game_over}
                className="w-10 h-10 rounded-xl bg-accent-primary hover:bg-accent-hover text-white flex items-center justify-center transition-all disabled:opacity-50 disabled:hover:bg-accent-primary"
              >
                <Send className="w-5 h-5 -ml-0.5" />
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Right Status Panel 30% */}
      <div className="flex-[3] h-full relative bg-slate-950/80">
        <StatusPanel state={playerState} />
      </div>

      {/* Log Modal */}
      {isLogsOpen && sessionId && (
        <LogViewer sessionId={sessionId} onClose={() => setIsLogsOpen(false)} />
      )}
    </div>
  );
}

export default App;
