import { useEffect, useState } from "react";

interface Props {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

/** Debounced text input. */
export function SearchBar({ value, onChange, placeholder = "Search passages…", autoFocus }: Props) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  useEffect(() => {
    const handle = setTimeout(() => {
      if (text !== value) onChange(text);
    }, 300);
    return () => clearTimeout(handle);
  }, [text, value, onChange]);
  return (
    <div className="relative">
      <input className="input pr-8" value={text} onChange={(e) => setText(e.target.value)} placeholder={placeholder} autoFocus={autoFocus} aria-label={placeholder} />
      {text && (
        <button type="button" className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-ink" onClick={() => { setText(""); onChange(""); }} aria-label="Clear search">
          ×
        </button>
      )}
    </div>
  );
}
