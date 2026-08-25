"use client";

import { useState } from "react";
import { SCOPE_OPTIONS, type ScopeKind } from "@/shared/lib/glossary-scopes";
import type { UiTextKey } from "@/shared/lib/ui-text";
import { useUiText } from "@/shared/lib/use-ui-text";

/** The option value standing for "not on the list", which no scope may equal. */
const OTHER = "__other__";

type ScopeFieldProps = {
  id: string;
  kind: ScopeKind;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
};

/**
 * One scope column, picked from a list rather than typed.
 *
 * A list because the lookup compares scopes by equality: a term filed under a
 * word nothing else uses applies to nothing, and there is no failure to see —
 * the translation still arrives, shaped by the catch-all entry instead. The
 * free-text field is still reachable behind "Other…", because the column has
 * no check constraint and a scope this list has not learned about yet is a
 * real situation; it is just no longer the easiest thing to do by accident.
 *
 * Empty is a value, not a blank: it means "applies everywhere" and is the rank
 * the lookup falls back to, so it leads the list rather than reading as unset.
 */
export default function ScopeField({ id, kind, value, onChange, disabled }: ScopeFieldProps) {
  const t = useUiText();
  const options = SCOPE_OPTIONS[kind];
  // Whether the free-text field is showing. Derived from the value on the first
  // render — an entry already carrying an off-list scope has to open on it —
  // and owned by the reader afterwards, because choosing "Other…" clears the
  // value and a purely derived flag would snap straight back to the list.
  const [custom, setCustom] = useState(() => value !== "" && !options.includes(value));

  const choose = (next: string) => {
    if (next === OTHER) {
      setCustom(true);
      onChange("");
      return;
    }
    setCustom(false);
    onChange(next);
  };

  return (
    <>
      <select
        id={id}
        value={custom ? OTHER : value}
        onChange={(event) => choose(event.target.value)}
        disabled={disabled}
      >
        <option value="">{t("glossary.scopeAny")}</option>
        {options.map((option) => (
          <option key={option} value={option}>
            {t(`glossary.${kind}.${option}` as UiTextKey)}
          </option>
        ))}
        <option value={OTHER}>{t("glossary.scope.other")}</option>
      </select>
      {custom && (
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={t("glossary.scope.customLabel")}
          aria-label={t("glossary.scope.customLabel")}
          disabled={disabled}
        />
      )}
    </>
  );
}
