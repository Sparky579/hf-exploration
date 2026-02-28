import { useEffect, useRef } from 'react';
import { ChatMessage } from '../types';
import { Bot, User, AlertCircle, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

interface ChatViewProps {
    messages: ChatMessage[];
    isStreaming: boolean;
    onRetry: () => void;
}

export default function ChatView({ messages, isStreaming, onRetry }: ChatViewProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto scroll to bottom
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isStreaming]);

    // Strip [command]...[/command] from text
    const formatText = (text: string) => {
        return text.replace(/\[command\][\s\S]*?\[\/command\]/g, '').trim();
    };

    return (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {messages.map((msg, idx) => {
                const isUser = msg.role === 'user';
                const formatted = formatText(msg.text);

                // Hide empty system messages that were just pure commands
                if (!isUser && !formatted && !msg.isStreaming && !msg.isError) return null;

                return (
                    <div key={msg.id} className={clsx("flex gap-4 max-w-3xl", isUser ? "ml-auto flex-row-reverse" : "mr-auto animate-fade-in")}>

                        <div className={clsx("flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center border",
                            isUser ? "bg-accent-primary/20 border-accent-primary/50 text-accent-primary" : "bg-slate-800/80 border-slate-700/50 text-slate-300"
                        )}>
                            {isUser ? <User className="w-5 h-5" /> : <Bot className="w-5 h-5" />}
                        </div>

                        <div className={clsx("px-5 py-4 rounded-2xl glass-panel text-[15px] leading-relaxed relative",
                            isUser ? "bg-accent-primary/10 border-accent-primary/20 rounded-tr-sm" : "bg-slate-900/40 border-slate-700/30 rounded-tl-sm",
                            msg.isError && "border-red-500/50 bg-red-500/10"
                        )}>
                            {msg.isError ? (
                                <div className="flex items-center gap-2 text-red-400">
                                    <AlertCircle className="w-5 h-5" />
                                    <span>{formatted || "Failed to communicate with the server."}</span>

                                    {/* Retry Button only on the latest failed system message */}
                                    {(idx === messages.length - 1 || idx === messages.length - 2) && (
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
            <div ref={bottomRef} className="h-4" />
        </div>
    );
}
