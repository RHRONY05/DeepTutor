"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  BookOpen,
  FileText,
  GraduationCap,
  Layers,
  Loader2,
  Plus,
} from "lucide-react";
import { FeaturePage } from "@/components/layout/FeaturePage";
import { Button } from "@/shared/ui/Button";
import { EmptyState } from "@/shared/ui/EmptyState";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import { rememberWorkspaceId } from "@/lib/workspace-scope";
import { listWorkspaces, type ChatWorkspaceRegistration } from "@/lib/workspaces-api";
import {
  listGroups,
  type ExamGroup,
} from "@/lib/courses-api";
import { ExamGroupList } from "@/components/courses/ExamGroupList";
import { ExamGroupDetail } from "@/components/courses/ExamGroupDetail";
import { NewExamGroupDialog } from "@/components/courses/NewExamGroupDialog";
import { CourseInstructionsPanel } from "@/components/courses/CourseInstructionsPanel";

export default function CourseWorkspacePage() {
  const params = useParams<{ workspaceId: string }>();
  const workspaceId = decodeURIComponent(params?.workspaceId || "");

  const [activeTab, setActiveTab] = useState<"exams" | "instructions">("exams");
  const [courseName, setCourseName] = useState<string>(workspaceId);
  const [groups, setGroups] = useState<ExamGroup[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Mobile navigation state
  const [showMobileDetail, setShowMobileDetail] = useState(false);

  // Dialog
  const [createOpen, setCreateOpen] = useState(false);

  useEffect(() => {
    if (workspaceId) {
      rememberWorkspaceId(workspaceId);
    }
  }, [workspaceId]);

  // Load Course Name from workspaces catalog
  useEffect(() => {
    if (!workspaceId) return;
    void listWorkspaces()
      .then((allWs: ChatWorkspaceRegistration[]) => {
        const match = allWs.find((w) => w.workspace_id === workspaceId);
        if (match?.display_name) {
          setCourseName(match.display_name);
        }
      })
      .catch(() => {
        // Fallback to workspaceId if catalog fetch fails
      });
  }, [workspaceId]);

  // Load Exam Groups
  const loadGroups = useCallback(async () => {
    if (!workspaceId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await listGroups(workspaceId);
      setGroups(data);
      if (data.length > 0) {
        setSelectedSlug((prev) =>
          prev && data.some((g) => g.slug === prev) ? prev : data[0].slug,
        );
      } else {
        setSelectedSlug(null);
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load exam groups.",
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceId]);

  useEffect(() => {
    void loadGroups();
  }, [loadGroups]);

  const handleGroupCreated = (newGroup: ExamGroup) => {
    setGroups((prev) => [newGroup, ...prev.filter((g) => g.slug !== newGroup.slug)]);
    setSelectedSlug(newGroup.slug);
    setShowMobileDetail(true);
  };

  const handleGroupUpdated = (updated: ExamGroup) => {
    setGroups((prev) =>
      prev.map((g) => (g.slug === updated.slug ? updated : g)),
    );
  };

  const handleGroupDeleted = (deletedSlug: string) => {
    setGroups((prev) => {
      const remaining = prev.filter((g) => g.slug !== deletedSlug);
      if (selectedSlug === deletedSlug) {
        setSelectedSlug(remaining.length > 0 ? remaining[0].slug : null);
        setShowMobileDetail(false);
      }
      return remaining;
    });
  };

  const handleSelectSlug = (slug: string) => {
    setSelectedSlug(slug);
    setShowMobileDetail(true);
  };

  return (
    <FeaturePage>
      {/* Page Header */}
      <div className="mb-6 flex flex-col gap-4">
        <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
          <Link
            href="/courses"
            className="flex items-center gap-1 hover:text-[var(--foreground)]"
          >
            <ArrowLeft size={13} />
            All Courses
          </Link>
          <span>/</span>
          <span className="truncate font-medium text-[var(--foreground)]">
            {courseName}
          </span>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-[var(--border)]/60 bg-[var(--card)] text-[var(--primary)] shadow-sm">
              <BookOpen size={20} />
            </span>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-[var(--foreground)] sm:text-2xl">
                {courseName}
              </h1>
              <p className="text-xs text-[var(--muted-foreground)]">
                Course workspace · {groups.length}{" "}
                {groups.length === 1 ? "exam group" : "exam groups"}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant="primary"
              size="sm"
              icon={<Plus size={14} />}
              onClick={() => setCreateOpen(true)}
              className="text-xs"
            >
              New exam group
            </Button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[var(--border)]">
          <button
            type="button"
            onClick={() => setActiveTab("exams")}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === "exams"
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <Layers size={14} />
            Exam groups
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("instructions")}
            className={`flex items-center gap-2 border-b-2 px-4 py-2.5 text-xs font-semibold transition-colors ${
              activeTab === "instructions"
                ? "border-[var(--primary)] text-[var(--primary)]"
                : "border-transparent text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            <FileText size={14} />
            Instructions
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-6">
          <InlineAlert tone="danger">{error}</InlineAlert>
        </div>
      )}

      {/* Instructions Tab Content */}
      {activeTab === "instructions" ? (
        <CourseInstructionsPanel workspaceId={workspaceId} />
      ) : (
        /* Exam Groups Tab Content */
        <div className="min-h-[550px] overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] shadow-sm">
          {loading ? (
            <div className="flex h-96 items-center justify-center text-sm text-[var(--muted-foreground)]">
              <Loader2
                size={22}
                className="mr-2 animate-spin text-[var(--primary)]"
              />
              Loading exam groups...
            </div>
          ) : groups.length === 0 ? (
            <div className="p-12">
              <EmptyState
                icon={<Layers size={22} />}
                title="No exam groups yet"
                description="Create exam groups (such as CT-01, Viva, Mid-term, or Final Exam) to organize your exam syllabus and study files."
                action={
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    icon={<Plus size={14} />}
                    onClick={() => setCreateOpen(true)}
                    className="mt-2 text-xs"
                  >
                    Create first exam group
                  </Button>
                }
              />
            </div>
          ) : (
            <div className="flex flex-col md:flex-row">
              {/* Left Column: Groups List */}
              <div
                className={`w-full border-b border-[var(--border)] md:w-80 md:shrink-0 md:border-b-0 md:border-r ${
                  showMobileDetail ? "hidden md:block" : "block"
                }`}
              >
                <ExamGroupList
                  groups={groups}
                  selectedSlug={selectedSlug}
                  onSelectSlug={handleSelectSlug}
                  onOpenCreate={() => setCreateOpen(true)}
                />
              </div>

              {/* Right Column: Group Detail */}
              <div
                className={`min-w-0 flex-1 ${
                  !showMobileDetail ? "hidden md:block" : "block"
                }`}
              >
                {selectedSlug ? (
                  <ExamGroupDetail
                    key={selectedSlug}
                    workspaceId={workspaceId}
                    slug={selectedSlug}
                    onGroupUpdated={handleGroupUpdated}
                    onGroupDeleted={handleGroupDeleted}
                    onBackToList={() => setShowMobileDetail(false)}
                  />
                ) : (
                  <div className="flex h-96 items-center justify-center text-xs text-[var(--muted-foreground)]">
                    Select an exam group from the left to view details and files.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* New Exam Group Dialog */}
      <NewExamGroupDialog
        open={createOpen}
        workspaceId={workspaceId}
        onClose={() => setCreateOpen(false)}
        onCreated={handleGroupCreated}
      />
    </FeaturePage>
  );
}
