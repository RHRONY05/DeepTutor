"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { Calendar, Plus } from "lucide-react";
import { Button } from "@/shared/ui/Button";
import type { ExamGroup } from "@/lib/courses-api";
import { ExamTypeBadge } from "./ExamTypeBadge";
import { ExamStatusBadge } from "./ExamStatusBadge";

interface ExamGroupListProps {
  groups: ExamGroup[];
  selectedSlug: string | null;
  onSelectSlug: (slug: string) => void;
  onOpenCreate: () => void;
}

function formatExamDate(dateStr: string): string {
  if (!dateStr) return "No date set";
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return dateStr;
  const examDate = new Date(y, m - 1, d);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  examDate.setHours(0, 0, 0, 0);

  const diffMs = examDate.getTime() - today.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  const formatted = examDate.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });

  if (diffDays === 0) return `${formatted} · today`;
  if (diffDays === 1) return `${formatted} · tomorrow`;
  if (diffDays > 1) return `${formatted} · in ${diffDays}d`;
  if (diffDays === -1) return `${formatted} · yesterday`;
  if (diffDays < -1) return `${formatted} · ${Math.abs(diffDays)}d ago`;
  return formatted;
}

export function ExamGroupList({
  groups,
  selectedSlug,
  onSelectSlug,
  onOpenCreate,
}: ExamGroupListProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">
            Exam Groups
          </h2>
          <span className="rounded-full bg-[var(--muted)] px-2 py-0.5 text-[11px] font-medium text-[var(--muted-foreground)]">
            {groups.length}
          </span>
        </div>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          icon={<Plus size={13} />}
          onClick={onOpenCreate}
          className="text-xs"
        >
          New group
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        {groups.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-6 text-center text-[var(--muted-foreground)]">
            <p className="text-xs">No exam groups created yet.</p>
            <Button
              type="button"
              size="sm"
              variant="primary"
              icon={<Plus size={13} />}
              onClick={onOpenCreate}
              className="mt-3 text-xs"
            >
              Create first group
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-1.5">
            {groups.map((group) => {
              const isSelected = selectedSlug === group.slug;
              const totalTopics = group.progress?.total ?? group.topics?.length ?? 0;
              const knownTopics = group.progress?.known ?? 0;
              const percent =
                totalTopics > 0
                  ? Math.round((knownTopics / totalTopics) * 100)
                  : 0;

              return (
                <button
                  key={group.slug}
                  type="button"
                  onClick={() => onSelectSlug(group.slug)}
                  className={`group relative flex w-full flex-col rounded-xl border p-3 text-left transition-all ${
                    isSelected
                      ? "border-[var(--primary)] bg-[var(--primary)]/5 shadow-sm"
                      : "border-[var(--border)] bg-[var(--card)] hover:border-[var(--foreground)]/25"
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="truncate text-sm font-semibold text-[var(--foreground)]">
                      {group.name}
                    </span>
                    <ExamStatusBadge status={group.status} />
                  </div>

                  <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                    <ExamTypeBadge type={group.type} />
                    {group.date && (
                      <span className="inline-flex items-center gap-1 text-[11px] text-[var(--muted-foreground)]">
                        <Calendar size={11} />
                        {formatExamDate(group.date)}
                      </span>
                    )}
                  </div>

                  {totalTopics > 0 && (
                    <div className="mt-2.5 w-full">
                      <div className="flex items-center justify-between text-[11px] text-[var(--muted-foreground)]">
                        <span>Topics</span>
                        <span>
                          {knownTopics}/{totalTopics} known ({percent}%)
                        </span>
                      </div>
                      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-[var(--muted)]">
                        <div
                          className="h-full rounded-full bg-[var(--primary)] transition-all duration-300"
                          style={{ width: `${percent}%` }}
                        />
                      </div>
                    </div>
                  )}

                  <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--muted-foreground)]/70">
                    <span>
                      {group.file_count}{" "}
                      {group.file_count === 1 ? "file" : "files"}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default ExamGroupList;
