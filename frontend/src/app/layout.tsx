import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CairnBooks",
  description: "Open-source, multi-tenant bookkeeping for small businesses.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
