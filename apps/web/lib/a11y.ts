"use client";
// Small accessibility helpers shared by both views.
import { useEffect, useRef, type KeyboardEvent } from "react";

/** Make an SVG shape act like a button: focusable, labelled, Enter/Space activate. */
export function pressable(label: string, onPress: () => void) {
  return {
    role: "button",
    tabIndex: 0,
    "aria-label": label,
    onClick: onPress,
    onKeyDown: (e: KeyboardEvent) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onPress(); }
    },
  } as const;
}

/** A side panel that takes focus when it opens, closes on Escape, and returns focus where it came from. */
export function usePanel(onClose: () => void) {
  const ref = useRef<HTMLElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const esc = (e: globalThis.KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", esc);
    return () => { window.removeEventListener("keydown", esc); before?.focus?.(); };
  }, [onClose]);
  return ref;
}
