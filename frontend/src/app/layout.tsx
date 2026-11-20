import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Providers } from "@/components/providers";

import "./globals.css";

const inter = Inter({ variable: "--font-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Level 10",
  description: "Weekly Scorecard, Rocks, To-Dos, Issues and the Level 10 Meeting",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased`}>
      <body className="min-h-full bg-muted/40 font-sans text-foreground">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
