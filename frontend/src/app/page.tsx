
import Link from "next/link";

const features = [
  {
    icon: "⌕",
    title: "Smart Document Search",
    description:
      "Find relevant information across your uploaded documents without searching manually.",
  },
  {
    icon: "✦",
    title: "AI-Powered Answers",
    description:
      "Ask questions in natural language and receive answers grounded in your documents.",
  },
  {
    icon: "▤",
    title: "Source Citations",
    description:
      "See the source document and page number behind your AI-generated answers.",
  },
  {
    icon: "♧",
    title: "Secure Workspace",
    description:
      "Keep your knowledge base private with authenticated, user-specific access.",
  },
];

export default function LandingPage() {
  return (
    <main className="landing-page">
      <header className="landing-header">
        <Link href="/" className="landing-brand">
          <span className="landing-brand-icon">✦</span>
          <span>Enterprise RAG</span>
        </Link>

        <nav className="landing-nav">
          <a href="#features">Features</a>
          <a href="#how-it-works">How it works</a>
        </nav>

        <div className="landing-header-actions">
          <Link href="/login" className="landing-login">
            Log in
          </Link>
          <Link href="/login" className="landing-primary-button">
            Get Started <span>→</span>
          </Link>
        </div>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-content">
          <span className="landing-eyebrow">
            AI-POWERED DOCUMENT INTELLIGENCE
          </span>

          <h1>
            Turn your documents into{" "}
            <span>intelligent knowledge.</span>
          </h1>

          <p>
            Your documents contain valuable knowledge. Make it accessible
            with AI-powered search, intelligent answers, and reliable
            source citations.
          </p>

          <div className="landing-hero-actions">
            <Link href="/login" className="landing-primary-button">
              Get Started <span>→</span>
            </Link>

            <a href="#features" className="landing-secondary-button">
              Explore Features
            </a>
          </div>

          <div className="landing-trust-note">
            <span>✓</span> Your documents. Your knowledge. Your workspace.
          </div>
        </div>

        <div className="landing-preview">
          <div className="preview-window">
            <div className="preview-topbar">
              <div className="preview-dots">
                <span />
                <span />
                <span />
              </div>
              <span>Knowledge Assistant</span>
            </div>

            <div className="preview-body">
              <div className="preview-sidebar">
                <div className="preview-logo">✦</div>
                <div className="preview-sidebar-item active">▤</div>
                <div className="preview-sidebar-item">⌕</div>
                <div className="preview-sidebar-item">⚙</div>
              </div>

              <div className="preview-main">
                <span className="preview-label">YOUR KNOWLEDGE BASE</span>
                <h3>Good morning!</h3>
                <p>What would you like to know today?</p>

                <div className="preview-document">
                  <span className="preview-file-icon">PDF</span>
                  <div>
                    <strong>Business Documentation.pdf</strong>
                    <small>Document indexed successfully</small>
                  </div>
                  <span className="preview-check">✓</span>
                </div>

                <div className="preview-question">
                  <span>Ask a question about your documents...</span>
                  <span className="preview-send">↑</span>
                </div>

                <div className="preview-answer">
                  <span className="preview-ai-icon">✦</span>
                  <div>
                    <strong>AI Assistant</strong>
                    <p>
                      Ask questions and receive contextual answers
                      supported by your document sources.
                    </p>
                    <small>Sources · Document, Page 12</small>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="preview-decoration preview-decoration-one" />
          <div className="preview-decoration preview-decoration-two" />
        </div>
      </section>

      <section className="landing-features" id="features">
        <div className="landing-section-heading">
          <span className="landing-eyebrow">BUILT FOR YOUR KNOWLEDGE</span>
          <h2>Everything you need to work smarter</h2>
          <p>
            A smarter way to organize, search, and understand your
            business documents.
          </p>
        </div>

        <div className="landing-feature-grid">
          {features.map((feature) => (
            <article className="landing-feature-card" key={feature.title}>
              <div className="landing-feature-icon">{feature.icon}</div>
              <h3>{feature.title}</h3>
              <p>{feature.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="landing-how" id="how-it-works">
        <div className="landing-section-heading">
          <span className="landing-eyebrow">SIMPLE WORKFLOW</span>
          <h2>From documents to answers in three steps</h2>
        </div>

        <div className="landing-steps">
          <article>
            <span className="landing-step-number">01</span>
            <h3>Upload your documents</h3>
            <p>Add your PDF documents to your private knowledge base.</p>
          </article>

          <article>
            <span className="landing-step-number">02</span>
            <h3>Let AI understand them</h3>
            <p>Your documents are processed and indexed for retrieval.</p>
          </article>

          <article>
            <span className="landing-step-number">03</span>
            <h3>Ask and discover</h3>
            <p>Ask questions and get answers with supporting citations.</p>
          </article>
        </div>
      </section>

      <section className="landing-cta">
        <span className="landing-eyebrow">READY TO GET STARTED?</span>
        <h2>Your knowledge deserves a smarter way to work.</h2>
        <p>Create your account and start exploring your documents with AI.</p>
        <Link href="/login" className="landing-primary-button">
          Create Your Account <span>→</span>
        </Link>
      </section>

      <footer className="landing-footer">
        <Link href="/" className="landing-brand">
          <span className="landing-brand-icon">✦</span>
          <span>Enterprise RAG</span>
        </Link>
        <p>Intelligent document knowledge, made accessible.</p>
        <span>© 2026 Enterprise RAG Engine</span>
      </footer>
    </main>
  );
}
