import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PasswordInput } from "./PasswordInput";

describe("PasswordInput", () => {
  it("shows and hides the existing value with an accessible toggle", () => {
    render(
      <PasswordInput
        id="password"
        name="password"
        autoComplete="current-password"
        value="correct horse battery staple"
        onChange={vi.fn()}
        placeholder="Enter password"
      />,
    );

    const input = screen.getByPlaceholderText("Enter password") as HTMLInputElement;
    expect(input.type).toBe("password");
    expect(input.value).toBe("correct horse battery staple");

    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(input.type).toBe("text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(input.value).toBe("correct horse battery staple");

    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input.type).toBe("password");
  });
});
