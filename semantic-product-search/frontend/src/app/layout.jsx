import './globals.css';

export const metadata = {
  title: 'Semantic — A little meaning. A better find.',
  description: 'An original landing page for a more thoughtful approach to product discovery. Explore everyday inspiration, outdoor adventures, and the idea behind Semantic.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
