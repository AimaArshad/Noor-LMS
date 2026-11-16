import * as React from "react";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface TextAreaFieldProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  id: string;
  label: string;
  /** Validation message; also sets `aria-invalid`. */
  error?: string | null;
  hint?: string;
}

/** Label + textarea + hint + error, wired together with `aria-describedby`. */
export const TextAreaField = React.forwardRef<HTMLTextAreaElement, TextAreaFieldProps>(
  ({ id, label, error, hint, className, ...props }, ref) => {
    const describedBy =
      [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
    return (
      <div className="space-y-2">
        <Label htmlFor={id}>
          {label}
          {props.required ? (
            <span aria-hidden="true" className="text-destructive">
              {" "}
              *
            </span>
          ) : null}
        </Label>
        <Textarea
          id={id}
          ref={ref}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(error && "border-destructive", className)}
          {...props}
        />
        {hint ? (
          <p id={`${id}-hint`} className="text-xs text-muted-foreground">
            {hint}
          </p>
        ) : null}
        {error ? (
          <p id={`${id}-error`} className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
TextAreaField.displayName = "TextAreaField";
