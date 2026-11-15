import { useState } from "react";

interface PasswordInputProps {
  id: string;
  name: string;
  autoComplete: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  required?: boolean;
  minLength?: number;
  maxLength?: number;
}

export function PasswordInput({
  id,
  name,
  autoComplete,
  value,
  onChange,
  placeholder,
  required = false,
  minLength,
  maxLength,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false);
  const label = visible ? "Hide password" : "Show password";

  return (
    <div className="relative">
      <input
        id={id}
        name={name}
        type={visible ? "text" : "password"}
        autoComplete={autoComplete}
        required={required}
        minLength={minLength}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="w-full rounded-lg border border-line bg-white px-3.5 py-3 pr-12 text-sm outline-none transition focus:border-accent focus:ring-4 focus:ring-blue-100"
      />
      <button
        type="button"
        aria-label={label}
        aria-pressed={visible}
        onClick={() => setVisible((current) => !current)}
        className="absolute inset-y-0 right-0 inline-flex w-12 items-center justify-center rounded-r-lg text-muted transition hover:bg-slate-50 hover:text-ink focus-visible:z-10"
      >
        {visible ? <EyeOffIcon /> : <EyeIcon />}
      </button>
    </div>
  );
}

function EyeIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
      <circle cx="12" cy="12" r="2.7" stroke="currentColor" strokeWidth="1.7" />
    </svg>
  );
}

function EyeOffIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" className="h-5 w-5">
      <path d="m3 3 18 18M10.6 6.2A9.7 9.7 0 0 1 12 6c6.1 0 9.5 6 9.5 6a15 15 0 0 1-3 3.6M6.2 6.8C3.8 8.4 2.5 12 2.5 12s3.4 6 9.5 6c1.2 0 2.3-.2 3.3-.6" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
    </svg>
  );
}
