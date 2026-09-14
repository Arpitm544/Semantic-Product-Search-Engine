import './globals.css';

export const metadata = {
  title: 'Semantic Product Search | Vector & Hybrid AI Engine',
  description: 'Production-ready Semantic Product Search POC built with Sentence Transformers, FAISS, FastAPI, and Next.js',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
