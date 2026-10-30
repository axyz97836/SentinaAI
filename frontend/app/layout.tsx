import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const sans = localFont({ src: "./fonts/dm-sans.woff2", variable: "--font-ui", weight: "400 700", display: "swap", fallback: ["Arial", "sans-serif"] });
const display = localFont({ src: "./fonts/space-grotesk.woff2", variable: "--font-display", weight: "600 700", display: "swap", fallback: ["Arial", "sans-serif"] });
const editorial = localFont({ src: "./fonts/instrument-serif.woff2", variable: "--font-editorial", style: "italic", weight: "400", display: "swap", preload: false, fallback: ["Georgia", "serif"] });

export const metadata: Metadata = {
  title: { default: "SentinelAI", template: "%s | SentinelAI" },
  description: "Synthetic transaction risk intelligence and accountable investigation. Demonstration only.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${sans.variable} ${display.variable} ${editorial.variable}`}>
      <body><a className="skip-link" href="#main">Skip to main content</a>{children}</body>
    </html>
  );
}
