
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// ============================================================
// TYPES
// ============================================================

type Source = {
    source: string;
    page: number;
    snippet: string;
};

type ChatMessage = {
    id: number;
    role: "user" | "assistant";
    content: string;
    sources?: Source[] | null;
};

type Conversation = {
    id: number;
    title: string;
    created_at: string;
    updated_at: string;
};

// ============================================================
// DASHBOARD
// ============================================================

export default function Home() {
    const router = useRouter();

    // ---------- State ----------

    const [question, setQuestion] = useState("");
    const [messages, setMessages] = useState<ChatMessage[]>([]);

    const [conversations, setConversations] = useState<Conversation[]>([]);
    const [conversationId, setConversationId] = useState<number | null>(null);

    const [asking, setAsking] = useState(false);
    const [loadingHistory, setLoadingHistory] = useState(false);

    const [queryError, setQueryError] = useState("");
    const [userEmail, setUserEmail] = useState("");

    const [documentCount, setDocumentCount] = useState<number | null>(null);

    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [uploading, setUploading] = useState(false);
    const [uploadMessage, setUploadMessage] = useState("");
    const [uploadError, setUploadError] = useState("");

    const [authChecking, setAuthChecking] = useState(true);

    // ---------- Authentication ----------

    const handleLogout = () => {
        localStorage.removeItem("rag_access_token");
        localStorage.removeItem("rag_user_email");
        window.location.replace("/login");
    };

    // ---------- Load Conversations ----------

    const loadConversations = async () => {
        const token = localStorage.getItem("rag_access_token");

        if (!token) return;

        try {
            const response = await fetch(
                "http://127.0.0.1:8000/conversations",
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (!response.ok) return;

            const data: Conversation[] = await response.json();
            setConversations(data);
        } catch (error) {
            console.error("Failed to load conversations:", error);
        }
    };

    // ---------- Start New Chat ----------

    const startNewChat = () => {
        if (asking) return;

        setConversationId(null);
        setMessages([]);
        setQuestion("");
        setQueryError("");
    };

    // ---------- Open Existing Conversation ----------

    const openConversation = async (id: number) => {
        const token = localStorage.getItem("rag_access_token");

        if (!token) {
            router.replace("/login");
            return;
        }

        if (asking) return;

        setLoadingHistory(true);
        setQueryError("");

        try {
            const response = await fetch(
                `http://127.0.0.1:8000/conversations/${id}`,
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            const data = await response.json();

            if (!response.ok) {
                setQueryError(
                    data.detail || "Could not load conversation."
                );
                return;
            }

            setConversationId(data.id);
            setMessages(data.messages || []);
            setQuestion("");
        } catch {
            setQueryError("Could not connect to the backend.");
        } finally {
            setLoadingHistory(false);
        }
    };

    // ---------- PDF Upload ----------

    const handleUpload = async () => {
        if (!selectedFile) {
            setUploadError("Please select a PDF file first.");
            return;
        }

        if (selectedFile.size > 10 * 1024 * 1024) {
            setUploadError("The PDF must be smaller than 10 MB.");
            return;
        }

        const token = localStorage.getItem("rag_access_token");

        if (!token) {
            router.replace("/login");
            return;
        }

        setUploading(true);
        setUploadMessage("");
        setUploadError("");

        const formData = new FormData();
        formData.append("file", selectedFile);

        try {
            const response = await fetch(
                "http://127.0.0.1:8000/upload-pdf",
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                    body: formData,
                }
            );

            const result = await response.json().catch(() => ({}));

            if (!response.ok) {
                setUploadError(result.detail || "PDF upload failed.");
                return;
            }

            setUploadMessage(
                result.message || "PDF uploaded successfully!"
            );

            const documentsResponse = await fetch(
                "http://127.0.0.1:8000/documents",
                {
                    headers: {
                        Authorization: `Bearer ${token}`,
                    },
                }
            );

            if (documentsResponse.ok) {
                const documentsData = await documentsResponse.json();
                setDocumentCount(documentsData.total);
            }

            setSelectedFile(null);
        } catch {
            setUploadError(
                "Could not connect to the backend. Please try again."
            );
        } finally {
            setUploading(false);
        }
    };

    // ---------- Ask Question ----------

    const handleAskQuestion = async () => {
        const currentQuestion = question.trim();

        if (!currentQuestion || asking) return;

        const token = localStorage.getItem("rag_access_token");

        if (!token) {
            router.replace("/login");
            return;
        }

        const previousMessages = messages;

        const temporaryUserMessage: ChatMessage = {
            id: Date.now(),
            role: "user",
            content: currentQuestion,
        };

        setAsking(true);
        setQueryError("");
        setQuestion("");

        setMessages((previous) => [
            ...previous,
            temporaryUserMessage,
        ]);

        try {
            const response = await fetch(
                "http://127.0.0.1:8000/query",
                {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({
                        question: currentQuestion,
                        conversation_id: conversationId,
                    }),
                }
            );

            const result = await response.json();

            if (!response.ok) {
                setMessages(previousMessages);
                setQuestion(currentQuestion);

                setQueryError(
                    result.detail ||
                    "Something went wrong while processing your question."
                );
                return;
            }

            if (!result.conversation_id) {
                throw new Error("Backend did not return conversation_id.");
            }

            const assistantMessage: ChatMessage = {
                id: Date.now() + 1,
                role: "assistant",
                content: result.answer || "",
                sources: result.sources || [],
            };

            setConversationId(result.conversation_id);

            setMessages((previous) => [
                ...previous,
                assistantMessage,
            ]);

            await loadConversations();

        } catch (error) {
            console.error("Query failed:", error);

            setMessages(previousMessages);
            setQuestion(currentQuestion);

            setQueryError(
                "Could not get an answer. Please check your backend connection."
            );
        } finally {
            setAsking(false);
        }
    };

    // ---------- Verify Session ----------

    useEffect(() => {
        async function verifySession() {
            const token = localStorage.getItem("rag_access_token");

            if (!token) {
                router.replace("/login");
                return;
            }

            setUserEmail(
                localStorage.getItem("rag_user_email") || ""
            );

            try {
                const response = await fetch(
                    "http://127.0.0.1:8000/me",
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                    }
                );

                if (!response.ok) {
                    localStorage.removeItem("rag_access_token");
                    localStorage.removeItem("rag_user_email");
                    router.replace("/login");
                    return;
                }

                const documentsResponse = await fetch(
                    "http://127.0.0.1:8000/documents",
                    {
                        headers: {
                            Authorization: `Bearer ${token}`,
                        },
                    }
                );

                if (documentsResponse.ok) {
                    const documentsData =
                        await documentsResponse.json();

                    setDocumentCount(documentsData.total);
                }

                await loadConversations();

                setAuthChecking(false);

            } catch {
                localStorage.removeItem("rag_access_token");
                localStorage.removeItem("rag_user_email");
                router.replace("/login");
            }
        }

        verifySession();
    }, [router]);

    // ---------- Loading Screen ----------

    if (authChecking) {
        return (
            <div className="auth-loading">
                Checking your session...
            </div>
        );
    }

    // ============================================================
    // UI
    // ============================================================

    return (
        <main className="dashboard">

            {/* SIDEBAR */}

            <aside className="sidebar">

                <div className="brand">
                    <div className="brand-icon">R</div>
                    <div>
                        <h2>RAG Engine</h2>
                        <span>Enterprise AI</span>
                    </div>
                </div>

                <p className="nav-label">WORKSPACE</p>

                <nav className="navigation">
                    <a className="nav-item active" href="#overview">
                        ▦ Overview
                    </a>

                    <a className="nav-item" href="#documents">
                        ▤ Documents
                    </a>

                    <a className="nav-item" href="#assistant">
                        ✳ AI Assistant
                    </a>
                </nav>

                {/* NEW CHAT */}

                <button
                    type="button"
                    className="new-chat-button"
                    onClick={startNewChat}
                    disabled={asking}
                >
                    + New Chat
                </button>

                {/* CONVERSATION HISTORY */}

                <p className="nav-label">CONVERSATIONS</p>

                <div className="conversation-list">

                    {conversations.map((conversation) => (
                        <button
                            key={conversation.id}
                            type="button"
                            className={`conversation-item ${
                                conversationId === conversation.id
                                    ? "active"
                                    : ""
                            }`}
                            onClick={() =>
                                openConversation(conversation.id)
                            }
                            disabled={asking || loadingHistory}
                            title={conversation.title}
                        >
                            {conversation.title}
                        </button>
                    ))}

                    {conversations.length === 0 && (
                        <p className="file-note">
                            No previous conversations.
                        </p>
                    )}

                </div>

                <div className="sidebar-bottom">
                    <div className="status-dot" />
                    <span>RAG workspace</span>
                    <small>Local environment</small>
                </div>

            </aside>

            {/* MAIN CONTENT */}

            <section className="main-content" id="overview">

                {/* HEADER */}

                <header className="topbar">

                    <div>
                        <p className="eyebrow">
                            WORKSPACE / OVERVIEW
                        </p>
                        <h1>Knowledge Dashboard</h1>
                    </div>

                    <div className="topbar-actions">

                        <span className="user-email">
                            {userEmail}
                        </span>

                        <div className="user-avatar">
                            {(userEmail || "U")
                                .charAt(0)
                                .toUpperCase()}
                        </div>

                        <button
                            className="logout-button"
                            onClick={handleLogout}
                        >
                            Log out
                        </button>

                    </div>

                </header>

                {/* WELCOME */}

                <section className="welcome">

                    <div>
                        <p className="eyebrow light">
                            YOUR KNOWLEDGE, CONNECTED
                        </p>

                        <h2>
                            Ask your documents
                            <br />
                            anything.
                        </h2>

                        <p>
                            Search your knowledge base and get answers
                            grounded in your documents, with source references.
                        </p>

                        <a
                            className="primary-button"
                            href="#assistant"
                        >
                            Ask a question <span>→</span>
                        </a>
                    </div>

                    <div className="welcome-art" aria-hidden="true">
                        <div className="orbit orbit-one" />
                        <div className="orbit orbit-two" />

                        <div className="document-illustration">
                            <div className="doc-fold" />
                            <span>AI</span>
                            <i />
                            <i />
                            <i />
                        </div>

                        <div className="floating-chip">
                            ✳ Semantic search
                        </div>
                    </div>

                </section>

                {/* STATISTICS */}

                <section
                    className="stats-grid"
                    aria-label="Workspace statistics"
                >

                    <article className="stat-card">
                        <span className="stat-icon purple">▤</span>
                        <p>Documents indexed</p>
                        <h3>
                            {documentCount === null
                                ? "Loading..."
                                : documentCount}
                        </h3>
                        <small>Your uploaded documents</small>
                    </article>

                    <article className="stat-card">
                        <span className="stat-icon green">✳</span>
                        <p>AI answers</p>
                        <h3>Ready</h3>
                        <small>Grounded in your documents</small>
                    </article>

                    <article className="stat-card">
                        <span className="stat-icon orange">⌁</span>
                        <p>Knowledge retrieval</p>
                        <h3>Active</h3>
                        <small>Backend connected</small>
                    </article>

                </section>

                {/* CONTENT */}

                <div className="content-grid">

                    {/* DOCUMENT UPLOAD */}

                    <section
                        className="panel upload-panel"
                        id="documents"
                    >

                        <div className="panel-heading">
                            <div>
                                <p className="eyebrow">
                                    KNOWLEDGE BASE
                                </p>
                                <h2>Documents</h2>
                            </div>

                            <span className="subtle-tag">PDF</span>
                        </div>

                        <div className="upload-zone">

                            <div className="upload-icon">↑</div>

                            <h3>Upload your documents</h3>

                            <p>
                                Select a PDF document to add it to your
                                knowledge base.
                            </p>

                            <label className="upload-button">
                                {selectedFile
                                    ? "Change PDF"
                                    : "Choose PDF"}

                                <input
                                    type="file"
                                    accept=".pdf,application/pdf"
                                    hidden
                                    onChange={(event) => {
                                        const file =
                                            event.target.files?.[0] || null;

                                        setSelectedFile(file);
                                        setUploadMessage("");
                                        setUploadError("");
                                    }}
                                />
                            </label>

                            {selectedFile && (
                                <p className="file-note">
                                    Selected: {selectedFile.name}
                                </p>
                            )}

                            {selectedFile && (
                                <button
                                    type="button"
                                    className="upload-button"
                                    onClick={handleUpload}
                                    disabled={uploading}
                                >
                                    {uploading
                                        ? "Uploading..."
                                        : "Upload PDF"}
                                </button>
                            )}

                            {uploadMessage && (
                                <div className="upload-success">
                                    <span className="upload-success-icon">
                                        ✓
                                    </span>

                                    <div>
                                        <strong>Upload complete</strong>
                                        <p>{uploadMessage}</p>
                                    </div>
                                </div>
                            )}

                            {uploadError && (
                                <div
                                    className="upload-error"
                                    role="alert"
                                >
                                    <span className="upload-error-icon">
                                        !
                                    </span>

                                    <div>
                                        <strong>Upload failed</strong>
                                        <p>{uploadError}</p>
                                    </div>
                                </div>
                            )}

                            {!selectedFile && (
                                <span className="file-note">
                                    PDF files only · Maximum 10 MB
                                </span>
                            )}

                        </div>

                        <div className="empty-documents">
                            <span>▤</span>

                            <div>
                                <strong>
                                    No live document list displayed
                                </strong>

                                <p>
                                    Document count is connected to your API.
                                </p>
                            </div>
                        </div>

                    </section>

                    {/* AI ASSISTANT */}

                    <section
                        className="panel assistant-panel"
                        id="assistant"
                    >

                        <div className="panel-heading">

                            <div>
                                <p className="eyebrow">
                                    RETRIEVAL AUGMENTED GENERATION
                                </p>
                                <h2>AI Assistant</h2>
                            </div>

                            <span className="online-tag">
                                <span /> Ready
                            </span>

                        </div>

                        {/* CHAT MESSAGES */}

                        <div className="chat-area">

                            {loadingHistory && (
                                <p>Loading conversation...</p>
                            )}

                            {!loadingHistory &&
                                messages.length === 0 && (
                                    <>
                                        <div className="assistant-message">
                                            <div className="assistant-avatar">
                                                ✳
                                            </div>

                                            <div>
                                                <strong>RAG Assistant</strong>

                                                <p>
                                                    Hello! Ask questions using
                                                    your uploaded documents.
                                                    Your conversation history
                                                    will be saved automatically.
                                                </p>
                                            </div>
                                        </div>

                                        <div className="suggestion-label">
                                            TRY ASKING
                                        </div>

                                        <button
                                            className="suggestion"
                                            type="button"
                                            onClick={() =>
                                                setQuestion(
                                                    "Summarize the key points in my documents."
                                                )
                                            }
                                        >
                                            Summarize my documents
                                            <span>↗</span>
                                        </button>

                                        <button
                                            className="suggestion"
                                            type="button"
                                            onClick={() =>
                                                setQuestion(
                                                    "What are the most important findings?"
                                                )
                                            }
                                        >
                                            Find the most important findings
                                            <span>↗</span>
                                        </button>
                                    </>
                                )}

                            {messages.map((message) => (
                                <div
                                    key={message.id}
                                    className={
                                        message.role === "user"
                                            ? "user-message"
                                            : "assistant-message"
                                    }
                                >

                                    {message.role === "assistant" && (
                                        <div className="assistant-avatar">
                                            ✳
                                        </div>
                                    )}

                                    <div className="message-content">

                                        <strong>
                                            {message.role === "user"
                                                ? "You"
                                                : "RAG Assistant"}
                                        </strong>

                                        <div className="answer-content">
                                            <ReactMarkdown
                                                remarkPlugins={[remarkGfm]}
                                            >
                                                {message.content.replace(
                                                    /\\([*_`~])/g,
                                                    "$1"
                                                )}
                                            </ReactMarkdown>
                                        </div>

                                        {message.role === "assistant" &&
                                            message.sources &&
                                            message.sources.length > 0 && (
                                                <div className="sources-section">
                                                    <h4>Sources</h4>

                                                    {message.sources.map(
                                                        (source, index) => (
                                                            <div
                                                                className="source-item"
                                                                key={`${source.source}-${source.page}-${index}`}
                                                            >
                                                                <div className="source-title">
                                                                    <span>▤</span>

                                                                    <strong>
                                                                        {source.source}
                                                                    </strong>

                                                                    <span className="source-page">
                                                                        Page {source.page}
                                                                    </span>
                                                                </div>

                                                                <p>
                                                                    {source.snippet}
                                                                </p>
                                                            </div>
                                                        )
                                                    )}
                                                </div>
                                            )}

                                    </div>

                                </div>
                            ))}

                            {asking && (
                                <p className="privacy-note">
                                    RAG Assistant is thinking...
                                </p>
                            )}

                        </div>

                        {/* QUESTION INPUT */}

                        <form
                            className="question-form"
                            onSubmit={(event) => {
                                event.preventDefault();
                                handleAskQuestion();
                            }}
                        >

                            <input
                                value={question}
                                onChange={(event) =>
                                    setQuestion(event.target.value)
                                }
                                placeholder="Ask a question about your documents..."
                                aria-label="Ask a question"
                                disabled={asking || loadingHistory}
                            />

                            <button
                                type="submit"
                                disabled={
                                    !question.trim() ||
                                    asking ||
                                    loadingHistory
                                }
                            >
                                {asking ? "..." : "↑"}
                            </button>

                        </form>

                        <p className="privacy-note">
                            Answers are grounded in retrieved document passages.
                        </p>

                        {queryError && (
                            <div
                                className="query-error"
                                role="alert"
                            >
                                <strong>Unable to get an answer</strong>
                                <p>{queryError}</p>
                            </div>
                        )}

                    </section>

                </div>

                {/* FOOTER */}

                <footer className="footer">
                    <span>Enterprise RAG Engine</span>
                    <span>Powered by your knowledge base</span>
                </footer>

            </section>

        </main>
    );
}
