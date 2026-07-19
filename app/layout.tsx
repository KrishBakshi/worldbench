import type { Metadata } from "next";
import { Space_Grotesk, Inter } from "next/font/google";
import Header from "@/components/Header";
import "./globals.css";

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
});

const body = Inter({
  subsets: ["latin"],
  variable: "--font-body",
});

export const metadata: Metadata = {
  title: "worldbench",
  description: "One prompt, many models, floating biome islands compared side by side.",
  icons: {
    icon: "/world.png",
  },
};

const themeInitScript = `
  try {
    var theme = localStorage.getItem("worldbench-theme");
    if (theme === "day" || theme === "night") {
      document.documentElement.setAttribute("data-theme", theme);
    }
  } catch (e) {}
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body
        className={`${display.variable} ${body.variable} flex h-screen flex-col font-sans antialiased`}
      >
        <Header />
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </body>
    </html>
  );
}
