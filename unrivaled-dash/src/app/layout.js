import { Inter } from 'next/font/google';
import './globals.css';

// Load the Inter font with the desired subsets and weights
const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-inter',
});

export const metadata = {
  title: 'MODUEL Prop Confidence',
  description: 'Your sports betting analysis tool',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${inter.variable}`}>
      <head>
        {/* You can remove the manual link tag since next/font handles it */}
      </head>
      <body className="bg-gradient-to-b from-gray-900 to-gray-800">
        {children}
      </body>
    </html>
  );
}