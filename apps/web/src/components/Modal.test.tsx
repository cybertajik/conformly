import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

afterEach(cleanup);
describe("Modal", () => {
  it("opens with an accessible name and delegates Escape cancellation", () => {
    const close = vi.fn();
    render(<Modal label="Create evidence" onClose={close}><div className="modal-dialog"><label htmlFor="title">Title</label><input id="title"/></div></Modal>);
    const dialog = screen.getByRole("dialog", {name:"Create evidence"});
    expect(dialog).toHaveAttribute("open");
    fireEvent(dialog, new Event("cancel", {cancelable:true}));
    expect(close).toHaveBeenCalledOnce();
  });
  it("restores scrolling on unmount", () => {
    const {unmount} = render(<Modal label="Review" onClose={vi.fn()}><button>Close</button></Modal>);
    expect(document.body.style.overflow).toBe("hidden");
    unmount();
    expect(document.body.style.overflow).toBe("");
  });
});
