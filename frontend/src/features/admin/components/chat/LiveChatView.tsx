import React, { useState, useRef, useEffect } from 'react';
import {
  Send,
  Sparkles,
  Bot,
  User,
  ArrowRightLeft,
  Copy,
  Check,
  Lightbulb,
  ArrowLeft,
  RotateCcw,
  BookOpen,
} from 'lucide-react';
import { TermItem, LanguagePair, LanguageCode } from '../../types';

interface Message {
  id: string;
  sender: 'user' | 'bot';
  sourceText?: string;
  text: string;
  sourceLang: LanguageCode;
  targetLang: LanguageCode;
  model: string;
  latencyMs: number;
  inputTokens: number;
  outputTokens: number;
  matchedGlossaryTerms?: string[];
  timestamp: string;
}

interface LiveChatViewProps {
  terms: TermItem[];
  onBackToAdmin: () => void;
  onNewTranslationComplete: (log: {
    pair: LanguagePair;
    model: string;
    isFallback: boolean;
    latency: number;
    inputTokens: number;
    outputTokens: number;
    sourceText: string;
    targetText: string;
    matchedTerms: string[];
  }) => void;
  onSubmitSuggestion: (sug: {
    sourceText: string;
    currentAiTranslation: string;
    suggestedTranslation: string;
    sourceLang: LanguageCode;
    targetLang: LanguageCode;
    user: string;
    userEmail: string;
    reason: string;
  }) => void;
  onNotify: (message: string, type?: 'success' | 'info' | 'error') => void;
}

export const LiveChatView: React.FC<LiveChatViewProps> = ({
  terms,
  onBackToAdmin,
  onNewTranslationComplete,
  onSubmitSuggestion,
  onNotify,
}) => {
  const [inputText, setInputText] = useState('');
  const [sourceLang, setSourceLang] = useState<LanguageCode>('EN');
  const [targetLang, setTargetLang] = useState<LanguageCode>('VI');
  const [selectedModel, setSelectedModel] = useState<'GPT-4o mini' | 'Fallback Engine'>('GPT-4o mini');
  const [isTranslating, setIsTranslating] = useState(false);
  const [copiedMsgId, setCopiedMsgId] = useState<string | null>(null);

  // Suggestion modal state from chat
  const [suggestingMessage, setSuggestingMessage] = useState<Message | null>(null);
  const [userSuggestionText, setUserSuggestionText] = useState('');
  const [userReason, setUserReason] = useState('');

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const [messages, setMessages] = useState<Message[]>([
    {
      id: 'm-1',
      sender: 'user',
      text: 'Welcome to LinguaFlow live translation workspace.',
      sourceLang: 'EN',
      targetLang: 'VI',
      model: 'GPT-4o mini',
      latencyMs: 1420,
      inputTokens: 38,
      outputTokens: 14,
      timestamp: '16:12',
    },
    {
      id: 'm-2',
      sender: 'bot',
      sourceText: 'Welcome to LinguaFlow live translation workspace.',
      text: 'Chào mừng bạn đến với không gian làm việc dịch thuật trực tiếp LinguaFlow.',
      sourceLang: 'EN',
      targetLang: 'VI',
      model: 'GPT-4o mini',
      latencyMs: 1680,
      inputTokens: 38,
      outputTokens: 14,
      matchedGlossaryTerms: [],
      timestamp: '16:12',
    },
    {
      id: 'm-3',
      sender: 'user',
      text: 'We configured zero-shot inference pipeline with rate limiting.',
      sourceLang: 'EN',
      targetLang: 'VI',
      model: 'GPT-4o mini',
      latencyMs: 1720,
      inputTokens: 46,
      outputTokens: 18,
      timestamp: '16:14',
    },
    {
      id: 'm-4',
      sender: 'bot',
      sourceText: 'We configured zero-shot inference pipeline with rate limiting.',
      text: 'Chúng tôi đã cấu hình đường ống suy luận zero-shot kèm cơ chế giới hạn tần suất.',
      sourceLang: 'EN',
      targetLang: 'VI',
      model: 'GPT-4o mini',
      latencyMs: 1816,
      inputTokens: 46,
      outputTokens: 18,
      matchedGlossaryTerms: ['zero-shot inference', 'rate limiting'],
      timestamp: '16:14',
    },
  ]);

  const quickSamples = [
    { text: 'Deploy the distributed system to cloud cluster.', pair: 'EN → VI' },
    { text: 'Kiểm soát truy cập theo vai trò trong bảng điều khiển.', pair: 'VI → EN' },
    { text: 'The user churn rate decreased significantly this month.', pair: 'EN → VI' },
    { text: 'Data warehouse auto-scaling and fallback mechanism.', pair: 'EN → VI' },
  ];

  const handleSwapLanguages = () => {
    const temp = sourceLang;
    setSourceLang(targetLang);
    setTargetLang(temp);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isTranslating]);

  // Intelligent translation engine simulator using active glossary
  const performTranslation = (text: string, src: LanguageCode, tgt: LanguageCode) => {
    const isFallback = selectedModel === 'Fallback Engine';
    const latency = isFallback ? Math.floor(Math.random() * 2000 + 4000) : Math.floor(Math.random() * 600 + 1500);
    const inTokens = Math.max(12, Math.round(text.length * 1.3));
    const outTokens = Math.max(8, Math.round(text.length * 0.9));

    // Check glossary matches
    const activeGlossary = terms.filter((t) => t.status === 'active' && t.sourceLang === src && t.targetLang === tgt);
    const matchedTerms: string[] = [];

    let translatedResult = text;

    // Direct dictionary replace for matched glossary
    activeGlossary.forEach((term) => {
      const regex = new RegExp(term.sourceTerm, term.isStrict ? 'g' : 'gi');
      if (regex.test(text)) {
        matchedTerms.push(term.sourceTerm);
      }
    });

    // Mock realistic AI translation mapping
    if (src === 'EN' && tgt === 'VI') {
      if (text.toLowerCase().includes('distributed system')) {
        translatedResult = 'Triển khai hệ thống phân tán lên cụm máy chủ đám mây an toàn.';
      } else if (text.toLowerCase().includes('churn rate')) {
        translatedResult = 'Tỷ lệ rời bỏ của người dùng đã giảm đáng kể trong tháng này.';
      } else if (text.toLowerCase().includes('data warehouse')) {
        translatedResult = 'Kho dữ liệu tập trung tự động co giãn và kích hoạt cơ chế dự phòng.';
      } else if (text.toLowerCase().includes('zero-shot')) {
        translatedResult = 'Chúng ta đã khởi chạy đường ống suy luận zero-shot trên môi trường chính thức.';
      } else {
        translatedResult = `[Bản dịch AI] ${text} (Đã chuẩn hóa câu từ và ngữ pháp Tiếng Việt)`;
      }
    } else if (src === 'VI' && tgt === 'EN') {
      if (text.toLowerCase().includes('vai trò') || text.toLowerCase().includes('truy cập')) {
        translatedResult = 'Role-Based Access Control configured within the administration dashboard.';
      } else if (text.toLowerCase().includes('hệ thống phân tán')) {
        translatedResult = 'The distributed system architecture provides fault tolerance and high availability.';
      } else {
        translatedResult = `[AI Translation] ${text} (Standardized for English technical domain)`;
      }
    } else {
      translatedResult = text;
    }

    return {
      translatedResult,
      latency,
      inTokens,
      outTokens,
      matchedTerms,
      isFallback,
    };
  };

  const handleSend = () => {
    if (!inputText.trim() || isTranslating) return;

    const userMessage: Message = {
      id: `m-${Date.now()}-u`,
      sender: 'user',
      text: inputText.trim(),
      sourceLang,
      targetLang,
      model: selectedModel,
      latencyMs: 0,
      inputTokens: Math.max(12, Math.round(inputText.length * 1.3)),
      outputTokens: 0,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMessage]);
    const originalText = inputText.trim();
    setInputText('');
    setIsTranslating(true);

    setTimeout(() => {
      const result = performTranslation(originalText, sourceLang, targetLang);

      const botMessage: Message = {
        id: `m-${Date.now()}-b`,
        sender: 'bot',
        sourceText: originalText,
        text: result.translatedResult,
        sourceLang,
        targetLang,
        model: selectedModel,
        latencyMs: result.latency,
        inputTokens: result.inTokens,
        outputTokens: result.outTokens,
        matchedGlossaryTerms: result.matchedTerms,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, botMessage]);
      setIsTranslating(false);

      // Trigger admin metrics update
      onNewTranslationComplete({
        pair: `${sourceLang} → ${targetLang}` as LanguagePair,
        model: selectedModel,
        isFallback: result.isFallback,
        latency: result.latency,
        inputTokens: result.inTokens,
        outputTokens: result.outTokens,
        sourceText: originalText,
        targetText: result.translatedResult,
        matchedTerms: result.matchedTerms,
      });
    }, 900);
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedMsgId(id);
    setTimeout(() => setCopiedMsgId(null), 2000);
  };

  const handleOpenSuggestModal = (msg: Message) => {
    setSuggestingMessage(msg);
    setUserSuggestionText(msg.text);
    setUserReason('');
  };

  const handleSubmitSuggestionForm = (e: React.FormEvent) => {
    e.preventDefault();
    if (!suggestingMessage || !userSuggestionText.trim()) return;

    onSubmitSuggestion({
      sourceText: suggestingMessage.sourceText || suggestingMessage.text,
      currentAiTranslation: suggestingMessage.text,
      suggestedTranslation: userSuggestionText.trim(),
      sourceLang: suggestingMessage.sourceLang,
      targetLang: suggestingMessage.targetLang,
      user: 'Tester Quản trị viên',
      userEmail: 'admin.tester@linguaflow.ai',
      reason: userReason || 'Đề xuất từ phiên thử nghiệm trực tiếp trên giao diện Chat.',
    });

    onNotify('Đã gửi đề xuất chỉnh sửa đến Trung tâm Quản trị!', 'success');
    setSuggestingMessage(null);
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-xs flex flex-col h-[calc(100vh-140px)] min-h-[580px] overflow-hidden">
      {/* Chat Top Bar */}
      <div className="p-4 border-b border-gray-200 bg-gray-50/50 flex flex-wrap items-center justify-between gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <button
            id="btn-back-from-chat"
            onClick={onBackToAdmin}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white hover:bg-gray-50 text-gray-700 text-xs font-medium border border-gray-300 shadow-xs transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Quay lại Quản trị</span>
          </button>

          <div className="hidden sm:block h-5 w-px bg-gray-200" />

          {/* Language Pair Selector */}
          <div className="flex items-center gap-1.5 bg-white p-1 rounded-lg border border-gray-200 shadow-xs">
            <select
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value as LanguageCode)}
              className="py-1 px-2 text-xs font-semibold text-gray-900 bg-transparent outline-hidden cursor-pointer"
            >
              <option value="EN">English (EN)</option>
              <option value="VI">Tiếng Việt (VI)</option>
              <option value="JA">Japanese (JA)</option>
            </select>

            <button
              onClick={handleSwapLanguages}
              className="p-1 text-gray-400 hover:text-blue-600 rounded-md hover:bg-gray-50 transition-colors"
              title="Đảo ngược cặp ngôn ngữ"
            >
              <ArrowRightLeft className="w-3.5 h-3.5" />
            </button>

            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value as LanguageCode)}
              className="py-1 px-2 text-xs font-semibold text-blue-600 bg-transparent outline-hidden cursor-pointer"
            >
              <option value="VI">Tiếng Việt (VI)</option>
              <option value="EN">English (EN)</option>
              <option value="JA">Japanese (JA)</option>
            </select>
          </div>
        </div>

        {/* Model Selector & Live Status */}
        <div className="flex items-center gap-2 text-xs">
          <div className="flex items-center gap-1.5 bg-white px-2.5 py-1 rounded-lg border border-gray-200">
            <Bot className="w-3.5 h-3.5 text-blue-600" />
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value as 'GPT-4o mini' | 'Fallback Engine')}
              className="bg-transparent font-medium text-gray-700 outline-hidden cursor-pointer text-xs"
            >
              <option value="GPT-4o mini">GPT-4o mini (Primary)</option>
              <option value="Fallback Engine">Fallback Adapter (Simulated)</option>
            </select>
          </div>

          <button
            onClick={() => setMessages([])}
            className="p-1.5 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
            title="Xóa lịch sử chat"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Messages Stream Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 bg-gray-50/30">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-3 max-w-2xl ${
              msg.sender === 'user' ? 'ml-auto flex-row-reverse' : 'mr-auto'
            }`}
          >
            {/* Avatar */}
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold ${
                msg.sender === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-900 text-white'
              }`}
            >
              {msg.sender === 'user' ? <User className="w-3.5 h-3.5" /> : <Bot className="w-3.5 h-3.5 text-blue-400" />}
            </div>

            {/* Message Bubble */}
            <div
              className={`space-y-1.5 ${
                msg.sender === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`p-3.5 rounded-xl text-xs sm:text-sm leading-relaxed shadow-xs ${
                  msg.sender === 'user'
                    ? 'bg-blue-600 text-white rounded-tr-none'
                    : 'bg-white text-gray-900 border border-gray-200 rounded-tl-none'
                }`}
              >
                <p>{msg.text}</p>

                {/* Matched Glossary Terms badge if applicable */}
                {msg.matchedGlossaryTerms && msg.matchedGlossaryTerms.length > 0 && (
                  <div className="mt-2.5 pt-2 border-t border-gray-100 flex flex-wrap items-center gap-1.5">
                    <span className="text-[10px] font-semibold text-blue-600 flex items-center gap-1">
                      <BookOpen className="w-3 h-3" /> Thuật ngữ áp dụng:
                    </span>
                    {msg.matchedGlossaryTerms.map((term) => (
                      <span
                        key={term}
                        className="text-[10px] bg-blue-50 text-blue-700 font-medium px-2 py-0.5 rounded border border-blue-100"
                      >
                        {term}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Message Metadata & Quick Actions */}
              <div
                className={`flex items-center gap-2 px-1 text-[10px] text-gray-400 ${
                  msg.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <span>{msg.timestamp}</span>

                {msg.sender === 'bot' && (
                  <>
                    <span>•</span>
                    <span className="font-mono text-gray-500">{msg.latencyMs}ms</span>
                    <span>•</span>
                    <span className="font-mono text-gray-500">{msg.inputTokens}in / {msg.outputTokens}out</span>
                    <span>•</span>

                    {/* Copy text */}
                    <button
                      onClick={() => handleCopy(msg.id, msg.text)}
                      className="hover:text-blue-600 inline-flex items-center gap-0.5"
                    >
                      {copiedMsgId === msg.id ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </button>

                    <span>•</span>

                    {/* Submit Correction Suggestion */}
                    <button
                      onClick={() => handleOpenSuggestModal(msg)}
                      className="hover:text-amber-700 font-medium inline-flex items-center gap-1 text-amber-600"
                    >
                      <Lightbulb className="w-3 h-3" />
                      <span>Đề xuất sửa</span>
                    </button>
                  </>
                )}
              </div>
            </div>
          </div>
        ))}

        {isTranslating && (
          <div className="flex gap-3 max-w-md mr-auto">
            <div className="w-7 h-7 rounded-full bg-gray-900 text-white flex items-center justify-center shrink-0">
              <Bot className="w-3.5 h-3.5 text-blue-400 animate-spin" />
            </div>
            <div className="p-3 bg-white border border-gray-200 rounded-xl rounded-tl-none shadow-xs flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-600 animate-ping" />
              <span className="text-xs font-medium text-gray-600">
                LinguaFlow AI đang dịch và áp dụng quy tắc thuật ngữ...
              </span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts Samples */}
      <div className="p-2.5 px-4 bg-gray-50/80 border-t border-gray-200 flex items-center gap-2 overflow-x-auto text-[11px] shrink-0">
        <span className="text-gray-500 font-medium shrink-0 flex items-center gap-1">
          <Sparkles className="w-3 h-3 text-blue-600" /> Thử nhanh:
        </span>
        {quickSamples.map((sample, idx) => (
          <button
            key={idx}
            onClick={() => setInputText(sample.text)}
            className="px-2.5 py-1 bg-white hover:bg-gray-100 hover:text-gray-900 border border-gray-200 rounded-md text-gray-600 whitespace-nowrap transition-colors"
          >
            {sample.text}
          </button>
        ))}
      </div>

      {/* Input Box */}
      <div className="p-3 bg-white border-t border-gray-200 shrink-0">
        <div className="flex items-center gap-2 bg-gray-50 border border-gray-300 rounded-lg p-1.5 focus-within:border-blue-600 focus-within:bg-white transition-colors">
          <input
            id="chat-input-field"
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={`Nhập văn bản cần dịch (${sourceLang} → ${targetLang})...`}
            className="flex-1 px-3 py-1.5 text-xs sm:text-sm bg-transparent outline-hidden text-gray-900"
          />
          <button
            id="btn-send-translation"
            onClick={handleSend}
            disabled={!inputText.trim() || isTranslating}
            className="p-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-40 text-white rounded-md shadow-xs transition-colors shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Suggestion Submission Modal from Chat */}
      {suggestingMessage && (
        <div
          id="chat-suggestion-modal"
          className="fixed inset-0 bg-gray-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4"
          onClick={() => setSuggestingMessage(null)}
        >
          <div
            className="bg-white rounded-xl max-w-md w-full p-6 shadow-lg border border-gray-200 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3 pb-3 border-b border-gray-100">
              <div className="w-8 h-8 rounded-full bg-amber-50 text-amber-600 flex items-center justify-center">
                <Lightbulb className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">Gửi đề xuất sửa bản dịch</h3>
                <p className="text-xs text-gray-400">Đóng góp cải thiện chất lượng AI</p>
              </div>
            </div>

            <form onSubmit={handleSubmitSuggestionForm} className="space-y-3 text-xs">
              <div>
                <label className="font-medium text-gray-700 block mb-1">Văn bản gốc:</label>
                <div className="p-2.5 bg-gray-50 rounded-lg border border-gray-200 text-gray-800">
                  {suggestingMessage.sourceText || suggestingMessage.text}
                </div>
              </div>

              <div>
                <label className="font-medium text-gray-700 block mb-1">
                  Bản dịch đề xuất của bạn: <span className="text-rose-500">*</span>
                </label>
                <textarea
                  rows={2}
                  required
                  value={userSuggestionText}
                  onChange={(e) => setUserSuggestionText(e.target.value)}
                  className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900"
                />
              </div>

              <div>
                <label className="font-medium text-gray-700 block mb-1">Lý do điều chỉnh:</label>
                <input
                  type="text"
                  value={userReason}
                  onChange={(e) => setUserReason(e.target.value)}
                  placeholder="Ví dụ: Thuật ngữ chuyên ngành, diễn đạt tự nhiên hơn..."
                  className="w-full p-2 bg-white border border-gray-300 rounded-md outline-hidden focus:border-blue-600 text-gray-900"
                />
              </div>

              <div className="pt-2 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setSuggestingMessage(null)}
                  className="px-4 py-2 font-medium text-gray-700 hover:bg-gray-100 rounded-md"
                >
                  Hủy
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-xs"
                >
                  Gửi duyệt
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
