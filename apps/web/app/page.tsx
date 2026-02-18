import Link from "next/link";

export default function HomePage() {
  return (
    <main style={{ padding: "2rem", maxWidth: "48rem", margin: "0 auto" }}>
      <h1 style={{ marginBottom: "0.5rem" }}>AI Doctor</h1>
      <p style={{ marginBottom: "1.5rem", color: "#555" }}>
        General health information only. Not medical advice.
      </p>
      <Link
        href="/chat"
        style={{
          display: "inline-block",
          padding: "0.5rem 1rem",
          background: "#111",
          color: "#fff",
          borderRadius: "6px",
        }}
      >
        Go to Chat
      </Link>
    </main>
  );
}
