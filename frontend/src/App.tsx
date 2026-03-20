import { useState, useEffect, useRef, useCallback } from 'react';
import type { FormEvent } from 'react';
import ChatView from './components/ChatView';
import StatusPanel from './components/StatusPanel';
import LogViewer from './components/LogViewer';
import { startGame, fetchState, API_ACTION_URL } from './api';
import type { PlayerState, ChatMessage } from './types';
import { Terminal, Send, TerminalSquare, MessageSquare, Shield as ShieldIcon } from 'lucide-react';
import clsx from 'clsx';

const getStored = (key: string, fallback: string): string => {
  if (typeof window === 'undefined') return fallback;
  return window.localStorage.getItem(key) ?? fallback;
};

const PROVIDERS = ['gemini', 'openai'] as const;
type Provider = (typeof PROVIDERS)[number];
const REASONING_LEVELS = ['minimal', 'low', 'medium', 'high'] as const;
type ReasoningLevel = (typeof REASONING_LEVELS)[number];

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [playerState, setPlayerState] = useState<PlayerState | null>(null);
  const [inputText, setInputText] = useState('');
  const [providerInput, setProviderInput] = useState<Provider>(() => {
    const saved = getStored('hf_provider', 'gemini');
    return PROVIDERS.includes(saved as Provider) ? (saved as Provider) : 'gemini';
  });
  const [apiKeyInput, setApiKeyInput] = useState(() => getStored('hf_api_key', ''));
  const [baseUrlInput, setBaseUrlInput] = useState(() => getStored('hf_base_url', ''));
  const [modelInput, setModelInput] = useState(() => getStored('hf_model', 'gemini-3-flash-preview'));
  const [reasoningEffort, setReasoningEffort] = useState<ReasoningLevel>(() => {
    const saved = getStored('hf_reasoning_effort', 'minimal');
    return REASONING_LEVELS.includes(saved as ReasoningLevel) ? (saved as ReasoningLevel) : 'minimal';
  });

  const [isInitializing, setIsInitializing] = useState(true);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [thinkingTick, setThinkingTick] = useState(0);
  const [pendingResumeHint, setPendingResumeHint] = useState<string | null>(null);
  const [isLogsOpen, setIsLogsOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<'chat' | 'status'>('chat');
  const hasInitializedRef = useRef(false);

  const initGame = useCallback(async () => {
    setIsInitializing(true);
    setSessionId(null);
    setPlayerState(null);
    setMessages([]);
    setInputText('');
    setPendingResumeHint(null);
    setIsThinking(false);
    setThinkingTick(0);
    try {
      const { sessionId: sid, message, state } = await startGame({
        provider: providerInput,
        apiKey: apiKeyInput.trim() || undefined,
        baseUrl: baseUrlInput.trim() || undefined,
        model: modelInput.trim() || undefined,
        reasoningEffort,
      });
      setSessionId(sid);
      setPlayerState(state);
      setMessages([{
        id: Math.random().toString(),
        role: 'system',
        text: message
      }]);
    } catch (err) {
      console.error(err);
      const errMsg = err instanceof Error ? err.message : 'Failed to connect to backend server.';
      setMessages([{
        id: Math.random().toString(),
        role: 'system',
        text: errMsg,
        isError: true
      }]);
    } finally {
      setIsInitializing(false);
    }
  }, [providerInput, apiKeyInput, baseUrlInput, modelInput, reasoningEffort]);

  useEffect(() => {
    if (hasInitializedRef.current) return;
    hasInitializedRef.current = true;
    initGame();
  }, [initGame]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('hf_provider', providerInput);
  }, [providerInput]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('hf_api_key', apiKeyInput);
  }, [apiKeyInput]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('hf_base_url', baseUrlInput);
  }, [baseUrlInput]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('hf_model', modelInput);
  }, [modelInput]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem('hf_reasoning_effort', reasoningEffort);
  }, [reasoningEffort]);

  useEffect(() => {
    if (!isThinking) return;
    const timer = window.setInterval(() => {
      setThinkingTick((prev) => prev + 1);
    }, 700);
    return () => window.clearInterval(timer);
  }, [isThinking]);

  const syncLatestState = async () => {
    if (!sessionId) return;
    try {
      const latest = await fetchState(sessionId);
      setPlayerState(latest);
    } catch (err) {
      console.error('Failed to sync latest state', err);
    }
  };

  const sendAction = async (action: string, opts?: { isRetry?: boolean }) => {
    if (!action.trim() || !sessionId || isStreaming || playerState?.game_over) return;

    const userMsgId = Math.random().toString();
    const sysMsgId = Math.random().toString();

    setMessages(prev => [
      ...prev,
      { id: userMsgId, role: 'user', text: action },
      { id: sysMsgId, role: 'system', text: '', isStreaming: false }
    ]);
    setInputText('');
    setIsStreaming(true);
    setIsWaiting(true);
    setIsThinking(false);
    setThinkingTick(0);
    const resumeHintForRequest = pendingResumeHint;
    let streamedNarrativeText = '';

    try {
      const response = await fetch(API_ACTION_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          action_text: action,
          resume_hint: resumeHintForRequest ?? undefined,
          is_retry: Boolean(opts?.isRetry),
        })
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder('utf-8');

      if (!reader) throw new Error("No response body");

      let done = false;
      let buffer = '';
      let hasReceivedNarrativeChunk = false;
      let hasReceivedFinalState = false;
      let finalInterrupted = false;
      type StreamEvent = {
        type?: string;
        text?: string;
        state?: PlayerState;
        status?: string;
        tick?: number;
        interrupted?: boolean;
        errors?: string[];
      };

      const applyStreamEvent = (data: StreamEvent) => {
        setIsWaiting(false);
        if (data.type === 'thinking') {
          if (hasReceivedNarrativeChunk) {
            setIsThinking(false);
            return;
          }
          const status = data.status ?? 'tick';
          if (status === 'start') {
            setIsThinking(true);
            setThinkingTick(Math.max(1, Number(data.tick ?? 1)));
          } else if (status === 'tick') {
            setIsThinking(true);
            setThinkingTick(prev => {
              const incoming = Number(data.tick ?? 0);
              return incoming > 0 ? incoming : prev + 1;
            });
          } else {
            setIsThinking(false);
          }
        } else if (data.type === 'chunk') {
          if ((data.text ?? '').length > 0) {
            hasReceivedNarrativeChunk = true;
            streamedNarrativeText += data.text ?? '';
          }
          setIsThinking(false);
          setMessages(prev => prev.map(m =>
            m.id === sysMsgId ? { ...m, text: m.text + (data.text ?? ''), isStreaming: true } : m
          ));
        } else if (data.type === 'state') {
          if (data.state) {
            setPlayerState(data.state);
            hasReceivedFinalState = true;
          }
        } else if (data.type === 'final') {
          setIsThinking(false);
          finalInterrupted = Boolean(data.interrupted);
          if (data.state) {
            setPlayerState(data.state);
            hasReceivedFinalState = true;
          }
          if (!hasReceivedNarrativeChunk) {
            const finalText = (data.text ?? '').trim();
            if (finalText) {
              hasReceivedNarrativeChunk = true;
              streamedNarrativeText += finalText;
              setMessages(prev => prev.map(m =>
                m.id === sysMsgId ? { ...m, text: m.text + finalText, isStreaming: true } : m
              ));
            } else {
              setMessages(prev => prev.map(m =>
                m.id === sysMsgId
                  ? {
                      ...m,
                      text: finalInterrupted ? '本轮输出中断，可点击重试。' : '本轮未生成可见剧情，可点击重试。',
                      isError: true,
                      isStreaming: false
                    }
                  : m
              ));
            }
          }
        }
      };

      const extractPackedObjects = (input: string): { objects: string[]; rest: string } => {
        const objects: string[] = [];
        let start = -1;
        let depth = 0;
        let inString = false;
        let escaped = false;

        for (let i = 0; i < input.length; i += 1) {
          const ch = input[i];

          if (start === -1) {
            if (ch === '{') {
              start = i;
              depth = 1;
              inString = false;
              escaped = false;
            }
            continue;
          }

          if (inString) {
            if (escaped) {
              escaped = false;
            } else if (ch === '\\') {
              escaped = true;
            } else if (ch === '"') {
              inString = false;
            }
            continue;
          }

          if (ch === '"') {
            inString = true;
            continue;
          }

          if (ch === '{') {
            depth += 1;
            continue;
          }

          if (ch === '}') {
            depth -= 1;
            if (depth === 0) {
              objects.push(input.slice(start, i + 1));
              start = -1;
            }
          }
        }

        return {
          objects,
          rest: start === -1 ? '' : input.slice(start),
        };
      };

      const applyJsonText = (jsonText: string, source: string) => {
        try {
          applyStreamEvent(JSON.parse(jsonText) as StreamEvent);
          return;
        } catch {
          // Fallback for packed JSON objects on one line from legacy backend responses.
        }

        const packed = extractPackedObjects(jsonText);
        if (packed.objects.length > 0 && !packed.rest.trim()) {
          for (const objText of packed.objects) {
            try {
              applyStreamEvent(JSON.parse(objText) as StreamEvent);
            } catch (e) {
              console.error(`Failed to parse packed stream object from ${source}`, objText, e);
            }
          }
          return;
        }

        const literalNdjson = jsonText.replace(/\\n(?=\s*\{)/g, '\n');
        if (literalNdjson !== jsonText) {
          const fragments = literalNdjson.split('\n').map((x) => x.trim()).filter(Boolean);
          if (fragments.length > 1) {
            for (const fragment of fragments) {
              applyJsonText(fragment, `${source} literal-ndjson`);
            }
            return;
          }
        }

        console.error(`Failed to parse stream line from ${source}`, jsonText);
      };

      const consumeNdjsonBuffer = (source: string) => {
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;
          applyJsonText(trimmed, source);
        }
      };

      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          consumeNdjsonBuffer('stream chunk');
        }
      }

      buffer += decoder.decode();
      consumeNdjsonBuffer('stream tail');

      if (buffer.trim()) {
        applyJsonText(buffer.trim(), 'stream tail fragment');
      }

      // Always force one state sync when model output is done, so UI reflects latest time/hp/cards immediately.
      if (!hasReceivedFinalState) {
        await syncLatestState();
      } else {
        void syncLatestState();
      }

      setMessages(prev => prev.map(m =>
        m.id === sysMsgId ? { ...m, isStreaming: false } : m
      ));
      if (finalInterrupted && streamedNarrativeText.trim()) {
        setPendingResumeHint(streamedNarrativeText.trim().slice(-260));
      } else {
        setPendingResumeHint(null);
      }
    } catch (err) {
      console.error(err);
      setIsThinking(false);
      const recoveryTail = streamedNarrativeText.trim();
      if (recoveryTail) {
        setPendingResumeHint(recoveryTail.slice(-260));
        setMessages(prev => prev.map(m =>
          m.id === sysMsgId ? { ...m, isStreaming: false } : m
        ));
        void syncLatestState();
      } else {
        setMessages(prev => prev.map(m =>
          m.id === sysMsgId ? { ...m, isStreaming: false, isError: true, text: "网络断开或执行异常，请查看后台报错并可在此重试。" } : m
        ));
        void syncLatestState();
      }
    } finally {
      setIsThinking(false);
      setIsStreaming(false);
    }
  };

  const handleRetry = () => {
    if (playerState?.game_over) return;
    // Find last user message
    const userMsg = [...messages].reverse().find(m => m.role === 'user');
    if (userMsg) {
      // Remove the errored system message
      setMessages(prev => prev.filter(m => !m.isError));
      sendAction(userMsg.text, { isRetry: true });
    }
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    sendAction(inputText, { isRetry: false });
  };

  const handleApplyConfig = () => {
    if (isStreaming) return;
    initGame();
  };

  return (
    <div className="w-full h-full flex flex-col md:flex-row bg-[#0a0a0c] text-slate-200 font-sans overflow-hidden">

      {/* Left Chat Area - full on mobile, 70% on desktop */}
      <div className={clsx(
        "flex flex-col relative border-white/5 bg-[url('https://www.transparenttextures.com/patterns/dark-matter.png')]",
        "md:flex-[7] md:h-full md:border-r",
        mobileTab === 'chat' ? "flex-1 min-h-0" : "hidden md:flex"
      )}>
        {/* Header */}
        <header className="h-14 md:h-16 shrink-0 flex items-center justify-between px-3 md:px-6 border-b border-white/5 bg-slate-900/60 backdrop-blur-md z-20">
          <div className="flex items-center gap-2 md:gap-3">
            <div className="w-7 h-7 md:w-8 md:h-8 rounded-lg bg-accent-primary flex items-center justify-center shadow-[0_0_15px_rgba(139,92,246,0.5)]">
              <TerminalSquare className="w-4 h-4 md:w-5 md:h-5 text-white" />
            </div>
            <div>
              <h1 className="text-base md:text-lg font-bold text-white leading-tight">HF-Explore Runtime</h1>
              <p className="text-[10px] md:text-xs font-mono text-accent-primary uppercase tracking-wider">Neural Narrative Engine</p>
            </div>
          </div>
          <button
            onClick={() => setIsLogsOpen(true)}
            disabled={!sessionId}
            className="flex items-center gap-1.5 md:gap-2 px-2.5 md:px-4 py-1.5 md:py-2 rounded-lg bg-slate-800 border border-slate-700 hover:bg-slate-700 hover:text-white transition-colors disabled:opacity-50 text-xs md:text-sm font-medium"
          >
            <Terminal className="w-3.5 h-3.5 md:w-4 md:h-4" /> <span className="hidden sm:inline">后台记录</span><span className="sm:hidden">日志</span>
          </button>
        </header>

        <div className="px-3 md:px-6 py-2 md:py-3 border-b border-white/5 bg-slate-950/70">
          <div className="grid grid-cols-2 md:grid-cols-2 xl:grid-cols-6 gap-1.5 md:gap-2">
            <select
              value={providerInput}
              onChange={(e) => setProviderInput(e.target.value as Provider)}
              disabled={isStreaming || isInitializing}
              className="px-2 md:px-3 py-1.5 md:py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs md:text-sm text-slate-100 outline-none focus:border-accent-primary"
            >
              {PROVIDERS.map((provider) => (
                <option key={provider} value={provider}>
                  {`provider: ${provider}`}
                </option>
              ))}
            </select>
            <input
              type="password"
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              placeholder={providerInput === 'openai' ? "OpenAI API Key" : "Gemini API Key"}
              disabled={isStreaming || isInitializing}
              className="px-2 md:px-3 py-1.5 md:py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs md:text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-accent-primary"
            />
            <input
              type="text"
              value={baseUrlInput}
              onChange={(e) => setBaseUrlInput(e.target.value)}
              placeholder={providerInput === 'openai' ? "Base URL (e.g. https://api.uniapi.io/v1)" : "Base URL (optional)"}
              disabled={isStreaming || isInitializing}
              className="px-2 md:px-3 py-1.5 md:py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs md:text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-accent-primary"
            />
            <input
              type="text"
              value={modelInput}
              onChange={(e) => setModelInput(e.target.value)}
              placeholder={providerInput === 'openai' ? "Model (e.g. doubao-seed-1-6-251015)" : "Model (e.g. gemini-3-flash-preview)"}
              disabled={isStreaming || isInitializing}
              className="px-2 md:px-3 py-1.5 md:py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs md:text-sm text-slate-100 placeholder-slate-500 outline-none focus:border-accent-primary"
            />
            <select
              value={reasoningEffort}
              onChange={(e) => setReasoningEffort(e.target.value as ReasoningLevel)}
              disabled={isStreaming || isInitializing}
              className="px-2 md:px-3 py-1.5 md:py-2 rounded-lg bg-slate-900 border border-slate-700 text-xs md:text-sm text-slate-100 outline-none focus:border-accent-primary"
            >
              {REASONING_LEVELS.map((level) => (
                <option key={level} value={level}>
                  {`reasoning: ${level}`}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleApplyConfig}
              disabled={isStreaming || isInitializing}
              className="px-3 md:px-4 py-1.5 md:py-2 rounded-lg bg-accent-primary hover:bg-accent-hover text-xs md:text-sm text-white font-medium disabled:opacity-50"
            >
              应用并重开
            </button>
          </div>
        </div>

        {/* Chat Stream */}
        {isInitializing ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-4 text-accent-primary animate-pulse">
              <TerminalSquare className="w-12 h-12" />
              <p className="font-mono text-sm uppercase tracking-widest">鍒濆鍖栫幆澧冭繛鎺ヤ腑...</p>
            </div>
          </div>
        ) : (
          <ChatView
            messages={messages}
            isWaiting={isWaiting}
            isStreaming={isStreaming}
            isThinking={isThinking}
            thinkingTick={thinkingTick}
            isGameOver={Boolean(playerState?.game_over)}
            onRetry={handleRetry}
          />
        )}

        {/* Input Area */}
        <div className="p-3 md:p-6 pt-0 shrink-0 z-20">
          <form onSubmit={handleSubmit} className="relative group max-w-3xl mx-auto">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value.substring(0, 15))}
              disabled={isStreaming || playerState?.game_over || !sessionId}
              placeholder={
                playerState?.game_over
                  ? "游戏已结束"
                  : isStreaming
                    ? "终端正在生成剧情..."
                    : "输入你的行动（最多15字）"
              }
              className="w-full bg-slate-900/80 border border-slate-700 text-white rounded-2xl py-3 md:py-4 pl-4 md:pl-6 pr-16 md:pr-20 outline-none focus:border-accent-primary focus:ring-1 focus:ring-accent-primary transition-all disabled:opacity-50 shadow-lg placeholder-slate-500 backdrop-blur-md text-sm md:text-base"
            />

            <div className="absolute right-3 md:right-4 top-1/2 -translate-y-1/2 flex items-center gap-2 md:gap-3">
              <span className={clsx("text-xs font-mono", inputText.length >= 15 ? "text-red-400" : "text-slate-500")}>
                {inputText.length}/15
              </span>

              <button
                type="submit"
                disabled={!inputText.trim() || isStreaming || playerState?.game_over}
                className="w-8 h-8 md:w-10 md:h-10 rounded-xl bg-accent-primary hover:bg-accent-hover text-white flex items-center justify-center transition-all disabled:opacity-50 disabled:hover:bg-accent-primary"
              >
                <Send className="w-4 h-4 md:w-5 md:h-5 -ml-0.5" />
              </button>
            </div>
          </form>
        </div>
      </div>

      {/* Right Status Panel - full on mobile when selected, 30% on desktop */}
      <div className={clsx(
        "min-h-0 overflow-hidden relative bg-slate-950/80 flex flex-col",
        "md:flex-[3] md:h-full",
        mobileTab === 'status' ? "flex-1" : "hidden md:flex"
      )}>
        <StatusPanel state={playerState} />
      </div>

      {/* Mobile Bottom Tab Bar */}
      <div className="md:hidden shrink-0 flex border-t border-white/10 bg-slate-900/95 backdrop-blur-md z-30">
        <button
          onClick={() => setMobileTab('chat')}
          className={clsx(
            "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors",
            mobileTab === 'chat' ? "text-accent-primary border-t-2 border-accent-primary" : "text-slate-400"
          )}
        >
          <MessageSquare className="w-4 h-4" /> 剧情
        </button>
        <button
          onClick={() => setMobileTab('status')}
          className={clsx(
            "flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors",
            mobileTab === 'status' ? "text-accent-primary border-t-2 border-accent-primary" : "text-slate-400"
          )}
        >
          <ShieldIcon className="w-4 h-4" /> 状态
        </button>
      </div>

      {/* Log Modal */}
      {isLogsOpen && sessionId && (
        <LogViewer sessionId={sessionId} onClose={() => setIsLogsOpen(false)} />
      )}
    </div>
  );
}

export default App;
