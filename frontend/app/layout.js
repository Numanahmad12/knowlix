import "./globals.css";

export const metadata = {
  title: "Knowlix — Enterprise AI Document Intelligence & Semantic Caching",
  description:
    "Next-generation PDF intelligence platform powered by ONNX embeddings, FAISS hybrid retrieval, Groq LLM, and document-aware semantic caching.",
  icons: { icon: "/icon.svg" },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
