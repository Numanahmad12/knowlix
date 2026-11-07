import "./globals.css";

export const metadata = {
  title: "PDF Q&A Studio",
  description:
    "Upload a PDF and ask questions about it — answers are grounded in the document, with page citations.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
