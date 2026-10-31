
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();

  const handleLogout = () => {
    localStorage.removeItem("rag_access_token");
    localStorage.removeItem("rag_user_email");
    window.location.replace("/login");
  };
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
      const response = await fetch("http://localhost:8000/upload-pdf", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      const result: { detail?: string; message?: string } =
        await response.json().catch(() => ({}));

      if (!response.ok) {
        setUploadError(result.detail || "PDF upload failed.");
        return;
      }

      setUploadMessage(result.message || "PDF uploaded successfully!");

      const documentsResponse = await fetch(
        "http://localhost:8000/documents",
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
      setUploadError("Could not connect to the backend. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const [question, setQuestion] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [documentCount, setDocumentCount] = useState<number | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [authChecking, setAuthChecking] = useState(true);

  useEffect(() => {
    async function verifySession() {
      const token = localStorage.getItem("rag_access_token");

      if (!token) {
        router.replace("/login");
        return;
      }
      setUserEmail(localStorage.getItem("rag_user_email") || "");

      try {
        const response = await fetch("http://localhost:8000/me", {
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!response.ok) {
          localStorage.removeItem("rag_access_token");
          localStorage.removeItem("rag_user_email");
          router.replace("/login");
          return;
        }

        const documentsResponse = await fetch(
          "http://localhost:8000/documents",
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

        setAuthChecking(false);
      } catch {
        localStorage.removeItem("rag_access_token");
        localStorage.removeItem("rag_user_email");
        router.replace("/login");
      }
    }

    verifySession();
  }, [router]);

  if (authChecking) {
    return <div className="auth-loading">Checking your session...</div>;
  }

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
          <div className="topbar-actions">
            <span className="user-email">{userEmail}</span>

            <div className="user-avatar">
              {(userEmail || "U").charAt(0).toUpperCase()}
            </div>

            <button className="logout-button" onClick={handleLogout}>
              Log out
            </button>
          </div>
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
            <h3>{documentCount === null ? "Loading..." : documentCount}</h3>
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

              <h3>Upload your documents</h3>

              <p>
                Select a PDF document to add it to your knowledge base.
              </p>

              <label className="upload-button">
                {selectedFile ? "Change PDF" : "Choose PDF"}

                <input
                  type="file"
                  accept=".pdf,application/pdf"
                  hidden
                  onChange={(e) => {
                    const file = e.target.files?.[0] || null;
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
                  className="upload-button"
                  onClick={handleUpload}
                  disabled={uploading}
                >
                  {uploading ? "Uploading..." : "Upload PDF"}
                </button>
              )}

              {uploadMessage && (
                <div className="upload-success">
                  <span className="upload-success-icon">✓</span>
                  <div>
                    <strong>Upload complete</strong>
                    <p>{uploadMessage}</p>
                  </div>
                </div>
              )}

              {uploadError && (
                <div className="upload-error" role="alert">
                  <span className="upload-error-icon">!</span>
                  <div>
                    <strong>Upload failed</strong>
                    <p>{uploadError}</p>
                  </div>
                </div>
              )}
              {!selectedFile && (
                <span className="file-note">PDF files only · Maximum 10 MB</span>
              )}
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
