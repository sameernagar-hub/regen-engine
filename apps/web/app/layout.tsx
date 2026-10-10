import type { ReactNode } from "react";
import "./globals.css";
import "./v010.css";

export const metadata = {
  title: "REGEN · live",
  description: "The engine, watched live: what it's doing for you and what needs you.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
