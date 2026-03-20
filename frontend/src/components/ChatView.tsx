import { useEffect, useRef } from 'react';
import type { ChatMessage } from '../types';
import { Bot, User, AlertCircle, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

interface ChatViewProps {
    messages: ChatMessage[];
    isWaiting: boolean;
    isStreaming: boolean;
    isThinking: boolean;
    thinkingTick: number;
    isGameOver: boolean;
    onRetry: () => void;
}

export default function ChatView({ messages, isWaiting, isStreaming, isThinking, thinkingTick, isGameOver, onRetry }: ChatViewProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto scroll to bottom
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isStreaming, isThinking, thinkingTick]);

    // Strip [command]...[/command] from text
    const formatText = (text: string) => {
        return text.replace(/\[command\][\s\S]*?\[\/command\]/g, '').trim();
    };

    return (
        <div className="flex-1 overflow-y-auto p-3 md:p-6 space-y-4 md:space-y-6">
            {messages.map((msg, idx) => {
                const isUser = msg.role === 'user';
                const formatted = formatText(msg.text);

                // Hide empty system messages that were just pure commands
                if (!isUser && !formatted && !msg.isStreaming && !msg.isError) return null;

                return (
                    <div key={msg.id} className={clsx("flex gap-2.5 md:gap-4 max-w-3xl", isUser ? "ml-auto flex-row-reverse" : "mr-auto animate-fade-in")}>

                        <div className={clsx("flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center border",
                            isUser ? "bg-accent-primary/20 border-accent-primary/50 text-accent-primary" : "bg-slate-800/80 border-slate-700/50 text-slate-300"
                        )}>
                            {isUser ? <User className="w-4 h-4 md:w-5 md:h-5" /> : <Bot className="w-4 h-4 md:w-5 md:h-5" />}
                        </div>

                        <div className={clsx("px-3 py-3 md:px-5 md:py-4 rounded-2xl glass-panel text-[13px] md:text-[15px] leading-relaxed relative",
                            isUser ? "bg-accent-primary/10 border-accent-primary/20 rounded-tr-sm" : "bg-slate-900/40 border-slate-700/30 rounded-tl-sm",
                            msg.isError && "border-red-500/50 bg-red-500/10"
                        )}>
                            {msg.isError ? (
                                <div className="flex items-center gap-2 text-red-400">
                                    <AlertCircle className="w-5 h-5" />
                                    <span>{formatted || "Failed to communicate with the server."}</span>

                                    {/* Retry Button only on the latest failed system message */}
                                    {!isGameOver && (idx === messages.length - 1 || idx === messages.length - 2) && (
                                        <button
                                            onClick={onRetry}
                                            className="ml-4 flex items-center gap-1.5 px-3 py-1.5 rounded bg-red-500/20 hover:bg-red-500/30 transition shadow-sm text-sm"
                                        >
                                            <RefreshCw className="w-4 h-4" /> 回拉剧情重试
                                        </button>
                                    )}
                                </div>
                            ) : (
                                <div className="whitespace-pre-wrap font-serif text-slate-200">
                                    {formatted}
                                    {msg.isStreaming && <span className="inline-block w-2 h-4 ml-1 bg-accent-primary animate-pulse" />}
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
            {(isWaiting || isThinking) && (
                <div className="flex gap-2.5 md:gap-4 max-w-3xl mr-auto animate-fade-in">
                    <div className="flex-shrink-0 w-8 h-8 md:w-10 md:h-10 rounded-full flex items-center justify-center border bg-slate-800/80 border-slate-700/50 text-slate-300">
                        <Bot className="w-4 h-4 md:w-5 md:h-5" />
                    </div>
                    <div className="px-3 py-3 md:px-5 md:py-4 rounded-2xl rounded-tl-sm glass-panel text-[13px] md:text-[15px] leading-relaxed relative bg-slate-900/40 border-slate-700/30">
                        <div className="font-serif text-slate-200 flex items-center gap-2">
                            <span>{isThinking ? '思考中' : '等待中'}</span>
                            <span className="inline-flex gap-1">
                                <span className="w-1.5 h-1.5 rounded-full bg-accent-primary animate-pulse" />
                                <span className="w-1.5 h-1.5 rounded-full bg-accent-primary animate-pulse [animation-delay:120ms]" />
                                <span className="w-1.5 h-1.5 rounded-full bg-accent-primary animate-pulse [animation-delay:240ms]" />
                            </span>
                            {isThinking && <span className="text-xs text-slate-400 font-mono">#{thinkingTick}</span>}
                        </div>
                        {isThinking && (
                            <div className="mt-2 w-44 h-1.5 rounded bg-slate-700/50 overflow-hidden">
                                <div
                                    className="h-full bg-gradient-to-r from-cyan-400/70 to-accent-primary/80 transition-all duration-300"
                                    style={{ width: `${20 + (thinkingTick % 7) * 10}%` }}
                                />
                            </div>
                        )}
                    </div>
                </div>
            )}
            <div ref={bottomRef} className="h-4" />
        </div>
    );
}
