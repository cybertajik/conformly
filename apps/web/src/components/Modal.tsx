import { useEffect, useRef, type ReactNode } from "react";

/** A native top-layer dialog: focus containment, Escape, and focus restoration. */
export function Modal({ children, label, onClose }: { children: ReactNode; label: string; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const element = dialog.current;
    if (!element) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (typeof element.showModal === "function") element.showModal();
    else element.setAttribute("open", "");
    return () => {
      if (typeof element.close === "function") element.close();
      document.body.style.overflow = previousOverflow;
      previousFocus?.focus();
    };
  }, []);
  return <dialog ref={dialog} className="modal-root" aria-label={label} onCancel={event => { event.preventDefault(); onClose(); }}>{children}</dialog>;
}
