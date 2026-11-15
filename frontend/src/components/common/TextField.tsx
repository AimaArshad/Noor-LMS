import * as React from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  /** Validation message; also sets `aria-invalid`. */
  error?: string | null;
  hint?: string;
}

/** Label + input + hint + error, wired together with `aria-describedby`. */
export const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(
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
        <Input
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
TextField.displayName = "TextField";
