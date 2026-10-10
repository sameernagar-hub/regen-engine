import type { ReactNode } from "react";
import { ViewTransition } from "react";
import "./globals.css";
import "./v010.css";
import "./v011.css";
import { Backdrop } from "./backdrop";

export const metadata = {
  title: "REGEN · live",
  description: "The engine, watched live: what it's doing for you and what needs you.",
};

// Every page sits on the live neural field (backdrop.tsx) and navigations morph through React's ViewTransition:
// the page cross-fades, and elements that share a view-transition name (a job row and its submission header,
// a nav tab and its page title) morph into each other, so the pages read as one connected surface.
export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Backdrop />
        <ViewTransition default="page-swap">{children}</ViewTransition>
      </body>
    </html>
  );
}
