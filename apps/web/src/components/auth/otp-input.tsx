"use client";

import { useEffect, useRef } from "react";

interface OTPInputProps {
  length?: number;
  value: string;
  onChange: (v: string) => void;
  autoFocus?: boolean;
  disabled?: boolean;
}

/**
 * 6 格独立 OTP 输入 (Apple / Stripe 风):
 * - 输一格自动跳下一格
 * - Backspace 空格回上一格
 * - ArrowLeft/Right 切换 focus
 * - 支持粘贴整段数字 (任一格 paste 都按整段填充)
 */
export function OTPInput({
  length = 6,
  value,
  onChange,
  autoFocus,
  disabled,
}: OTPInputProps) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);

  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);

  const setDigits = (next: string) => {
    onChange(next.replace(/\D/g, "").slice(0, length));
  };

  const handleChange = (i: number, e: React.ChangeEvent<HTMLInputElement>) => {
    const raw = e.target.value.replace(/\D/g, "");
    if (!raw) {
      // 删除当前位
      const arr = value.split("");
      arr[i] = "";
      setDigits(arr.join(""));
      return;
    }
    if (raw.length === 1) {
      const arr = value.padEnd(length, " ").split("");
      arr[i] = raw;
      setDigits(arr.join("").replace(/ /g, ""));
      if (i < length - 1) refs.current[i + 1]?.focus();
    } else {
      // 粘贴多位数字: 从当前位置开始填充
      const arr = value.padEnd(length, " ").split("");
      raw
        .slice(0, length - i)
        .split("")
        .forEach((c, j) => {
          arr[i + j] = c;
        });
      const filled = arr.join("").replace(/ /g, "");
      setDigits(filled);
      const focusAt = Math.min(i + raw.length, length - 1);
      refs.current[focusAt]?.focus();
    }
  };

  const handleKey = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    const arr = value.split("");
    if (e.key === "Backspace" && !arr[i] && i > 0) {
      refs.current[i - 1]?.focus();
    } else if (e.key === "ArrowLeft" && i > 0) {
      e.preventDefault();
      refs.current[i - 1]?.focus();
    } else if (e.key === "ArrowRight" && i < length - 1) {
      e.preventDefault();
      refs.current[i + 1]?.focus();
    }
  };

  return (
    <div className="flex justify-center gap-2">
      {Array.from({ length }).map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={1}
          value={value[i] ?? ""}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKey(i, e)}
          disabled={disabled}
          className="h-14 w-12 rounded-xl border border-input bg-background text-center text-2xl font-bold tabular-nums shadow-sm transition-all focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
          aria-label={`验证码第 ${i + 1} 位`}
        />
      ))}
    </div>
  );
}
