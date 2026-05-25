import * as React from "react";
import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

function Checkbox({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <span className="relative inline-flex size-4 shrink-0 items-center justify-center">
      <input
        type="checkbox"
        data-slot="checkbox"
        className={cn(
          "peer size-4 appearance-none rounded-[4px] border border-input bg-transparent shadow-xs outline-none transition-shadow",
          "checked:border-primary checked:bg-primary",
          "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]",
          "disabled:cursor-not-allowed disabled:opacity-50",
          className,
        )}
        {...props}
      />
      <Check
        className="pointer-events-none absolute size-3 text-primary-foreground opacity-0 transition-opacity peer-checked:opacity-100"
        strokeWidth={3}
      />
    </span>
  );
}

export { Checkbox };
