"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  BookOpen,
  Calendar,
  Layers,
  Loader2,
  Plus,
  Settings,
} from "lucide-react";
import {
  FeaturePage,
  PageHeader,
  pageGridClass,
} from "@/components/layout/FeaturePage";
import { Button } from "@/shared/ui/Button";
import { EmptyState } from "@/shared/ui/EmptyState";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import { selectWorkspace } from "@/lib/workspace-scope";
import { listCourses, type CourseInfo } from "@/lib/courses-api";

function formatRelativeDays(dateStr: string): string {
  if (!dateStr) return "";
  const parts = dateStr.split("-").map(Number);
  if (parts.length < 3) return dateStr;
  const [y, m, d] = parts;
  if (!y || !m || !d) return dateStr;
  const examDate = new Date(y, m - 1, d);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  examDate.setHours(0, 0, 0, 0);

  const diffMs = examDate.getTime() - today.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "tomorrow";
  if (diffDays > 1) return `in ${diffDays} days`;
  if (diffDays === -1) return "yesterday";
  if (diffDays < -1) return `${Math.abs(diffDays)} days ago`;
  return "";
}

export default function CoursesPage() {
  const router = useRouter();
  const [courses, setCourses] = useState<CourseInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadCourses = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await listCourses();
      setCourses(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load courses.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCourses();
  }, [loadCourses]);

  const handleSelectCourse = async (workspaceId: string) => {
    const dest = `/courses/${encodeURIComponent(workspaceId)}`;
    try {
      await selectWorkspace(workspaceId, dest);
    } catch {
      router.push(dest);
    }
  };

  return (
    <FeaturePage>
      <PageHeader
        title="Courses"
        icon={BookOpen}
        description="Each course workspace manages its own exam groups, syllabi, past papers, and prep materials."
        action={
          <Link href="/settings/workspace">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={<Settings size={14} />}
              className="text-xs"
            >
              Workspace settings
            </Button>
          </Link>
        }
      />

      {error && (
        <div className="mb-6">
          <InlineAlert tone="danger">{error}</InlineAlert>
        </div>
      )}

      {loading ? (
        <div className="flex h-64 items-center justify-center text-sm text-[var(--muted-foreground)]">
          <Loader2 size={24} className="mr-2 animate-spin text-[var(--primary)]" />
          Loading courses...
        </div>
      ) : courses.length === 0 ? (
        <EmptyState
          icon={<BookOpen size={24} />}
          title="No courses yet"
          description="In DeepTutor, each course is a workspace. Create one in Settings → Workspace to organize exams, syllabus topics, and course slides."
          action={
            <Link href="/settings/workspace">
              <Button
                type="button"
                variant="primary"
                size="md"
                icon={<Plus size={15} />}
                className="mt-2 text-xs"
              >
                Go to Workspace Settings
              </Button>
            </Link>
          }
        />
      ) : (
        <div className={pageGridClass(3)}>
          {courses.map((course) => {
            const nextExam = course.next_exam;
            const relativeDays = nextExam
              ? formatRelativeDays(nextExam.date)
              : "";

            return (
              <div
                key={course.workspace_id}
                role="button"
                tabIndex={0}
                onClick={() => void handleSelectCourse(course.workspace_id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    void handleSelectCourse(course.workspace_id);
                  }
                }}
                className="group relative flex flex-col justify-between rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm transition-all hover:border-[var(--primary)]/40 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]/40"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-8 w-8 items-center justify-center rounded-xl border border-[var(--border)]/60 bg-[var(--background)] text-[var(--primary)]">
                        <BookOpen size={16} />
                      </span>
                      <div className="min-w-0">
                        <h3 className="truncate text-base font-semibold text-[var(--foreground)] group-hover:text-[var(--primary)]">
                          {course.display_name || course.workspace_id}
                        </h3>
                        {course.kind === "general" && (
                          <span className="text-[11px] text-[var(--muted-foreground)]">
                            General Workspace
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 flex items-center gap-1.5 text-xs text-[var(--muted-foreground)]">
                    <Layers size={13} />
                    <span>
                      {course.group_count}{" "}
                      {course.group_count === 1
                        ? "exam group"
                        : "exam groups"}
                    </span>
                  </div>
                </div>

                <div className="mt-5 border-t border-[var(--border)]/40 pt-3">
                  {nextExam ? (
                    <div className="flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5 font-medium text-[var(--foreground)]">
                        <Calendar size={13} className="text-[var(--primary)]" />
                        <span className="truncate">{nextExam.name}</span>
                      </span>
                      <span className="shrink-0 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                        {relativeDays ? `${relativeDays}` : nextExam.date}
                      </span>
                    </div>
                  ) : (
                    <span className="text-[11px] italic text-[var(--muted-foreground)]/60">
                      No upcoming exams scheduled
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </FeaturePage>
  );
}
