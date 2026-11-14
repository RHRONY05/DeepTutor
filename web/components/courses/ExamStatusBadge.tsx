// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import type { ExamStatus } from "@/lib/courses-api";

interface ExamStatusBadgeProps {
  status: ExamStatus | string;
  className?: string;
}

const STATUS_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; dot: string }
> = {
  planned: {
    label: "Planned",
    bg: "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300",
    text: "text-zinc-700 dark:text-zinc-300",
    dot: "bg-zinc-400",
  },
  preparing: {
    label: "Preparing",
    bg: "bg-amber-500/10 text-amber-800 dark:text-amber-200",
    text: "text-amber-800 dark:text-amber-200",
    dot: "bg-amber-500",
  },
  done: {
    label: "Done",
    bg: "bg-emerald-500/10 text-emerald-800 dark:text-emerald-200",
    text: "text-emerald-800 dark:text-emerald-200",
    dot: "bg-emerald-500",
  },
};

export function ExamStatusBadge({
  status,
  className = "",
}: ExamStatusBadgeProps) {
  const conf = STATUS_CONFIG[status] ?? {
    label: status || "Unknown",
    bg: "bg-zinc-500/10 text-zinc-700 dark:text-zinc-300",
    text: "text-zinc-700 dark:text-zinc-300",
    dot: "bg-zinc-400",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium leading-none ${conf.bg} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${conf.dot}`} />
      {conf.label}
    </span>
  );
}

export default ExamStatusBadge;
