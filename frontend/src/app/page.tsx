
"use client";

import { useState } from "react";

export default function Home() {
  const [question, setQuestion] = useState("");

  return (
    <main className="dashboard">
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
          <a className="nav-item active" href="#overview">▦ Overview</a>
          <a className="nav-item" href="#documents">▤ Documents</a>
          <a className="nav-item" href="#assistant">✳ AI Assistant</a>
        </nav>

        <div className="sidebar-bottom">
          <div className="status-dot" />
          <span>RAG workspace</span>
          <small>Local environment</small>
        </div>
      </aside>

      <section className="main-content" id="overview">
        <header className="topbar">
          <div>
            <p className="eyebrow">WORKSPACE / OVERVIEW</p>
            <h1>Knowledge Dashboard</h1>
          </div>
          <div className="user-avatar">U</div>
        </header>

        <section className="welcome">
          <div>
            <p className="eyebrow light">YOUR KNOWLEDGE, CONNECTED</p>
            <h2>Ask your documents<br />anything.</h2>
            <p>
              Search your knowledge base and get answers grounded in your
              documents, with source references.
            </p>
            <a className="primary-button" href="#assistant">
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
            <div className="floating-chip">✳ Semantic search</div>
          </div>
        </section>

        <section className="stats-grid" aria-label="Workspace statistics">
          <article className="stat-card">
            <span className="stat-icon purple">▤</span>
            <p>Documents indexed</p>
            <h3>—</h3>
            <small>Connect your API to load data</small>
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
            <h3>Active UI</h3>
            <small>Backend connection comes next</small>
          </article>
        </section>

        <div className="content-grid">
          <section className="panel upload-panel" id="documents">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">KNOWLEDGE BASE</p>
                <h2>Documents</h2>
              </div>
              <span className="subtle-tag">PDF</span>
            </div>

            <div className="upload-zone">
              <div className="upload-icon">↑</div>
              <h3>Your documents will live here</h3>
              <p>
                PDF upload and document management will be connected to your
                FastAPI backend in the next stage.
              </p>
              <span className="file-note">PDF files · Backend integration pending</span>
            </div>

            <div className="empty-documents">
              <span>▤</span>
              <div>
                <strong>No live document data yet</strong>
                <p>This preview isn't connected to your API yet.</p>
              </div>
            </div>
          </section>

          <section className="panel assistant-panel" id="assistant">
            <div className="panel-heading">
              <div>
                <p className="eyebrow">RETRIEVAL AUGMENTED GENERATION</p>
                <h2>AI Assistant</h2>
              </div>
              <span className="online-tag"><span /> Ready</span>
            </div>

            <div className="chat-area">
              <div className="assistant-message">
                <div className="assistant-avatar">✳</div>
                <div>
                  <strong>RAG Assistant</strong>
                  <p>
                    Hello! Once connected, I can answer questions using your
                    uploaded documents and show the supporting source passages.
                  </p>
                </div>
              </div>
              <div className="suggestion-label">TRY ASKING</div>
              <button
                className="suggestion"
                onClick={() =>
                  setQuestion("Summarize the key points in my documents.")
                }
              >
                Summarize my documents <span>↗</span>
              </button>
              <button
                className="suggestion"
                onClick={() =>
                  setQuestion("What are the most important findings?")
                }
              >
                Find the most important findings <span>↗</span>
              </button>
            </div>

            <form
              className="question-form"
              onSubmit={(event) => {
                event.preventDefault();
                alert("We'll connect this question box to your FastAPI /query endpoint in the next stage.");
              }}
            >
              <input
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a question about your documents..."
                aria-label="Ask a question"
              />
              <button type="submit" disabled={!question.trim()}>
                ↑
              </button>
            </form>
            <p className="privacy-note">Answers will be grounded in retrieved document passages.</p>
          </section>
        </div>

        <footer className="footer">
          <span>Enterprise RAG Engine</span>
          <span>Powered by your knowledge base</span>
        </footer>
      </section>
    </main>
  );
}
