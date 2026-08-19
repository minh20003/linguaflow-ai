"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, ChevronDown } from "lucide-react";
import { SUPPORTED_LANGUAGES, getLanguage } from "@/shared/lib/constants";
import styles from "./LanguagePicker.module.css";

interface LanguagePickerProps {
  value: string;
  onChange: (code: string) => void;
  /** Accessible name for the field. */
  label: string;
  /**
   * Codes from `GET /api/v1/languages`. Left out, the built-in list is used.
   * The backend owns the allowlist (docs/CONTRACT.md section 1).
   */
  codes?: string[];
  /** Ties the trigger to a visible `<label>`. */
  id?: string;
  disabled?: boolean;
}

/**
 * A language field as a droplist rather than a flat grid.
 *
 * Fourteen options laid out as chips filled a whole screen for one decision, so
 * the list is collapsed and capped at five visible rows, the rest reached by
 * scrolling.
 *
 * Built from a button and a listbox instead of `<select>`, for a reason found by
 * testing: a native select changes its value when the wheel passes over it, so
 * scrolling the settings page silently changed the language the account reads.
 * A listbox has no such behaviour, and it lets the row height be known — which
 * is what makes "exactly five rows" expressible.
 */
export default function LanguagePicker({
  value,
  onChange,
  label,
  codes,
  id,
  disabled = false,
}: LanguagePickerProps) {
  const generatedId = useId();
  const baseId = id ?? generatedId;
  const listId = `${baseId}-listbox`;

  const options = useMemo(
    () => (codes?.length ? codes.map((code) => getLanguage(code)) : SUPPORTED_LANGUAGES),
    [codes],
  );

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const typeAhead = useRef({ buffer: "", at: 0 });

  const selectedIndex = Math.max(0, options.findIndex((option) => option.code === value));
  const current = getLanguage(value);

  const openList = useCallback(() => {
    if (disabled) return;
    setActiveIndex(selectedIndex);
    setOpen(true);
  }, [disabled, selectedIndex]);

  const choose = useCallback((index: number) => {
    const option = options[index];
    if (option) onChange(option.code);
    setOpen(false);
  }, [onChange, options]);

  // Pointer down rather than click: a click that starts inside and ends outside
  // would otherwise leave the list open.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open]);

  // Keep the active row visible while arrowing through a list taller than the
  // five rows on screen.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector(`[data-index="${activeIndex}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open]);

  const onKeyDown = useCallback((event: React.KeyboardEvent) => {
    if (disabled) return;

    if (!open) {
      if (["ArrowDown", "ArrowUp", "Enter", " "].includes(event.key)) {
        event.preventDefault();
        openList();
      }
      return;
    }

    switch (event.key) {
      case "Escape":
        event.preventDefault();
        setOpen(false);
        return;
      case "Enter":
      case " ":
        event.preventDefault();
        choose(activeIndex);
        return;
      case "ArrowDown":
        event.preventDefault();
        setActiveIndex((index) => Math.min(index + 1, options.length - 1));
        return;
      case "ArrowUp":
        event.preventDefault();
        setActiveIndex((index) => Math.max(index - 1, 0));
        return;
      case "Home":
        event.preventDefault();
        setActiveIndex(0);
        return;
      case "End":
        event.preventDefault();
        setActiveIndex(options.length - 1);
        return;
      case "Tab":
        setOpen(false);
        return;
      default:
        break;
    }

    // Type-ahead. Letters typed close together search one string, so "ti" finds
    // Tiếng Việt rather than jumping to the first name starting with "i".
    if (event.key.length === 1) {
      const now = Date.now();
      const buffer = now - typeAhead.current.at < 700
        ? typeAhead.current.buffer + event.key
        : event.key;
      typeAhead.current = { buffer, at: now };
      const needle = buffer.toLocaleLowerCase();
      const found = options.findIndex((option) =>
        option.name.toLocaleLowerCase().startsWith(needle)
        || option.code.toLocaleLowerCase().startsWith(needle),
      );
      if (found >= 0) setActiveIndex(found);
    }
  }, [activeIndex, choose, disabled, open, openList, options]);

  return (
    <div className={styles.root} ref={rootRef}>
      <button
        type="button"
        id={baseId}
        className={styles.trigger}
        role="combobox"
        aria-expanded={open}
        aria-controls={listId}
        aria-haspopup="listbox"
        aria-label={label}
        aria-activedescendant={open ? `${baseId}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onClick={() => (open ? setOpen(false) : openList())}
        onKeyDown={onKeyDown}
      >
        <span className={styles.triggerText}>
          <span className={styles.code} aria-hidden="true">{current.display}</span>
          <span lang={current.code}>{current.name}</span>
        </span>
        <ChevronDown size={18} strokeWidth={1.8} aria-hidden="true" className={open ? styles.chevronOpen : undefined} />
      </button>

      {open && (
        <ul className={styles.list} id={listId} role="listbox" aria-label={label} ref={listRef}>
          {options.map((option, index) => (
            <li
              key={option.code}
              id={`${baseId}-option-${index}`}
              data-index={index}
              role="option"
              aria-selected={option.code === value}
              className={`${styles.option} ${index === activeIndex ? styles.optionActive : ""}`}
              onPointerDown={(event) => event.preventDefault()}
              onClick={() => choose(index)}
              onMouseEnter={() => setActiveIndex(index)}
            >
              <span className={styles.code} aria-hidden="true">{option.display}</span>
              <span lang={option.code}>{option.name}</span>
              {option.code === value && <Check size={16} strokeWidth={2} aria-hidden="true" />}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
