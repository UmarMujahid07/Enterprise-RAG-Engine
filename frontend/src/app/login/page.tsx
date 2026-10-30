
"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

const API_URL = "http://localhost:8000";

export default function LoginPage() {
  const router = useRouter();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");



async function handleSubmit(event: FormEvent<HTMLFormElement>) {
  event.preventDefault();
  setError("");
  setMessage("");
  setLoading(true);

  try {
    if (mode === "register") {
      const response = await fetch(`${API_URL}/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Registration failed.");
      }

      setMessage("Account created successfully. Please sign in.");
      setMode("login");
      setPassword("");
      return;
    }

    // Only the Sign in mode reaches this section.
    const loginResponse = await fetch(`${API_URL}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: new URLSearchParams({
        username: email,
        password,
      }),
    });

    const loginData = await loginResponse.json();

    if (!loginResponse.ok) {
      throw new Error(loginData.detail || "Sign in failed.");
    }

    const token = loginData.access_token;

    const meResponse = await fetch(`${API_URL}/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });

    if (!meResponse.ok) {
      throw new Error("Session verification failed. Please sign in again.");
    }

    localStorage.setItem("rag_access_token", token);
    localStorage.setItem("rag_user_email", email);

    router.push("/");
  } catch (err) {
    setError(
      err instanceof Error ? err.message : "Something went wrong."
    );
  } finally {
    setLoading(false);
  }
}



  return (
    <main className="auth-page">
      <section className="auth-card">
        <a href="/" className="auth-brand">
          <span className="auth-brand-icon">R</span>
          <span>
            <strong>RAG Engine</strong>
            <small>Enterprise AI Workspace</small>
          </span>
        </a>

        <div className="auth-heading">
          <p className="eyebrow">YOUR KNOWLEDGE WORKSPACE</p>
          <h1>
            {mode === "login" ? "Welcome back" : "Create your account"}
          </h1>
          <p>
            {mode === "login"
              ? "Sign in to explore your document knowledge base."
              : "Register to start working with your documents."}
          </p>
        </div>

        <div className="auth-tabs">
          <button
            type="button"
            className={mode === "login" ? "auth-tab selected" : "auth-tab"}
            onClick={() => {
              setMode("login");
              setError("");
              setMessage("");
            }}
          >
            Sign in
          </button>
          <button
            type="button"
            className={mode === "register" ? "auth-tab selected" : "auth-tab"}
            onClick={() => {
              setMode("register");
              setError("");
              setMessage("");
            }}
          >
            Register
          </button>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@company.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={
              mode === "login" ? "current-password" : "new-password"
            }
            placeholder="At least 8 characters"
            minLength={8}
            maxLength={72}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
          />

          {error && <p className="auth-error" role="alert">{error}</p>}
          {message && <p className="auth-success" role="status">{message}</p>}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading
              ? "Please wait..."
              : mode === "login"
                ? "Sign in to workspace →"
                : "Create account →"}
          </button>
        </form>

        <p className="auth-footnote">
          Your credentials are sent to your FastAPI backend over the local
          development connection.
        </p>
      </section>

      <aside className="auth-aside">
        <div className="auth-aside-content">
          <span className="auth-decoration">✳</span>
          <p className="eyebrow light">ENTERPRISE KNOWLEDGE, SIMPLIFIED</p>
          <h2>Answers grounded in your own documents.</h2>
          <p>
            Upload knowledge, ask questions in natural language, and trace
            responses back to their source passages.
          </p>
          <div className="auth-feature">
            <span>01</span>
            <div>
              <strong>Your documents</strong>
              <p>Keep your knowledge organized.</p>
            </div>
          </div>
          <div className="auth-feature">
            <span>02</span>
            <div>
              <strong>Context-aware answers</strong>
              <p>Retrieve relevant document passages.</p>
            </div>
          </div>
          <div className="auth-feature">
            <span>03</span>
            <div>
              <strong>Traceable sources</strong>
              <p>Review the evidence behind responses.</p>
            </div>
          </div>
        </div>
      </aside>
    </main>
  );
}
