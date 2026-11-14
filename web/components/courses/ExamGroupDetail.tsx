"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Check,
  GraduationCap,
  Loader2,
  Plus,
  Save,
  Trash2,
  Upload,
} from "lucide-react";
import { Button } from "@/shared/ui/Button";
import { InlineAlert } from "@/shared/ui/InlineAlert";
import { setPendingPrompt } from "@/lib/pending-prompt";
import { scopedUrl } from "@/lib/workspace-scope";
import {
  deleteGroup,
  deleteGroupFile,
  getGroup,
  getGroupTree,
  updateGroup,
  uploadGroupFile,
  type ExamGroup,
  type ExamStatus,
  type ExamTopic,
  type ExamType,
  type FileTreeNode,
  type TopicStatus,
} from "@/lib/courses-api";
import { FileTree } from "./FileTree";

interface ExamGroupDetailProps {
  workspaceId: string;
  slug: string;
  onGroupUpdated: (group: ExamGroup) => void;
  onGroupDeleted: (slug: string) => void;
  onBackToList?: () => void; // Used on mobile to return to list
}

const EXAM_TYPES: { value: ExamType; label: string }[] = [
  { value: "class_test", label: "Class Test" },
  { value: "quiz", label: "Quiz" },
  { value: "viva", label: "Viva" },
  { value: "mid_term", label: "Mid-Term" },
  { value: "term_final", label: "Term Final" },
  { value: "assignment", label: "Assignment" },
  { value: "other", label: "Other" },
];

const EXAM_STATUSES: { value: ExamStatus; label: string }[] = [
  { value: "planned", label: "Planned" },
  { value: "preparing", label: "Preparing" },
  { value: "done", label: "Done" },
];

const TOPIC_STATUS_STYLES: Record<TopicStatus, string> = {
  todo: "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300",
  learning: "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300",
  known:
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
  skipped: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
};

export function ExamGroupDetail({
  workspaceId,
  slug,
  onGroupUpdated,
  onGroupDeleted,
  onBackToList,
}: ExamGroupDetailProps) {
  const router = useRouter();

  const [group, setGroup] = useState<ExamGroup | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Editable fields
  const [name, setName] = useState("");
  const [type, setType] = useState<ExamType>("class_test");
  const [date, setDate] = useState("");
  const [status, setStatus] = useState<ExamStatus>("planned");
  const [savingMeta, setSavingMeta] = useState(false);
  const [metaSaved, setMetaSaved] = useState(false);

  // Syllabus
  const [syllabus, setSyllabus] = useState("");
  const [savingSyllabus, setSavingSyllabus] = useState(false);
  const [syllabusSaved, setSyllabusSaved] = useState(false);

  // Topics
  const [newTopicTitle, setNewTopicTitle] = useState("");
  const [savingTopics, setSavingTopics] = useState(false);

  // Files & Tree
  const [treeNodes, setTreeNodes] = useState<FileTreeNode[]>([]);
  const [treeLoading, setTreeLoading] = useState(false);
  const [uploadFolder, setUploadFolder] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  // Deleting group
  const [deletingGroup, setDeletingGroup] = useState(false);

  const loadGroupData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const g = await getGroup(workspaceId, slug);
      setGroup(g);
      setName(g.name);
      setType(g.type);
      setDate(g.date || "");
      setStatus(g.status);
      setSyllabus(g.syllabus || "");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load exam group",
      );
    } finally {
      setLoading(false);
    }
  }, [workspaceId, slug]);

  const loadTree = useCallback(async () => {
    setTreeLoading(true);
    try {
      const nodes = await getGroupTree(workspaceId, slug);
      setTreeNodes(nodes);
    } catch (err) {
      // Tree error is non-fatal; folder might be empty
      setTreeNodes([]);
    } finally {
      setTreeLoading(false);
    }
  }, [workspaceId, slug]);

  useEffect(() => {
    void loadGroupData();
    void loadTree();
  }, [loadGroupData, loadTree]);

  // Save Meta
  const handleSaveMeta = async () => {
    if (!name.trim()) return;
    setSavingMeta(true);
    setError(null);
    try {
      const updated = await updateGroup(workspaceId, slug, {
        name: name.trim(),
        type,
        date: date || "",
        status,
      });
      setGroup(updated);
      onGroupUpdated(updated);
      setMetaSaved(true);
      setTimeout(() => setMetaSaved(false), 2000);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Failed to save exam group details.",
      );
    } finally {
      setSavingMeta(false);
    }
  };

  // Save Syllabus
  const handleSaveSyllabus = async () => {
    setSavingSyllabus(true);
    setError(null);
    try {
      const updated = await updateGroup(workspaceId, slug, {
        syllabus,
      });
      setGroup(updated);
      onGroupUpdated(updated);
      setSyllabusSaved(true);
      setTimeout(() => setSyllabusSaved(false), 2000);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to save syllabus.",
      );
    } finally {
      setSavingSyllabus(false);
    }
  };

  // Topics
  const handleAddTopic = async () => {
    if (!newTopicTitle.trim() || !group) return;
    const updatedTopics: ExamTopic[] = [
      ...(group.topics || []),
      { title: newTopicTitle.trim(), status: "todo" },
    ];
    setSavingTopics(true);
    try {
      const updated = await updateGroup(workspaceId, slug, {
        topics: updatedTopics,
      });
      setGroup(updated);
      onGroupUpdated(updated);
      setNewTopicTitle("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to add topic.",
      );
    } finally {
      setSavingTopics(false);
    }
  };

  const handleUpdateTopicStatus = async (
    index: number,
    newStatus: TopicStatus,
  ) => {
    if (!group) return;
    const updatedTopics = (group.topics || []).map((t, idx) =>
      idx === index ? { ...t, status: newStatus } : t,
    );
    setSavingTopics(true);
    try {
      const updated = await updateGroup(workspaceId, slug, {
        topics: updatedTopics,
      });
      setGroup(updated);
      onGroupUpdated(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to update topic status.",
      );
    } finally {
      setSavingTopics(false);
    }
  };

  const handleRemoveTopic = async (index: number) => {
    if (!group) return;
    const updatedTopics = (group.topics || []).filter((_, idx) => idx !== index);
    setSavingTopics(true);
    try {
      const updated = await updateGroup(workspaceId, slug, {
        topics: updatedTopics,
      });
      setGroup(updated);
      onGroupUpdated(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to remove topic.",
      );
    } finally {
      setSavingTopics(false);
    }
  };

  // Upload files
  const handleUploadFiles = async (files: FileList | File[]) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setUploadMessage(null);
    let successCount = 0;
    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        await uploadGroupFile(workspaceId, slug, file, uploadFolder || undefined);
        successCount++;
      }
      setUploadMessage(`Successfully uploaded ${successCount} file(s).`);
      setTimeout(() => setUploadMessage(null), 3000);
      void loadTree();
      void loadGroupData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to upload one or more files.",
      );
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteFile = async (filePath: string) => {
    try {
      await deleteGroupFile(workspaceId, slug, filePath);
      void loadTree();
      void loadGroupData();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to delete file.",
      );
    }
  };

  // Delete Group
  const handleDeleteGroup = async () => {
    const confirmed = window.confirm(
      `Are you sure you want to delete the exam group "${group?.name || slug}"?`,
    );
    if (!confirmed) return;

    setDeletingGroup(true);
    setError(null);
    try {
      await deleteGroup(workspaceId, slug, false);
      onGroupDeleted(slug);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      if (
        msg.toLowerCase().includes("file") ||
        msg.toLowerCase().includes("force") ||
        msg.toLowerCase().includes("not empty")
      ) {
        const forceDelete = window.confirm(
          `This exam group contains uploaded files. Delete all files and the group?`,
        );
        if (forceDelete) {
          try {
            await deleteGroup(workspaceId, slug, true);
            onGroupDeleted(slug);
            return;
          } catch (forceErr) {
            setError(
              forceErr instanceof Error
                ? forceErr.message
                : "Failed to force delete exam group.",
            );
          }
        }
      } else {
        setError(msg);
      }
    } finally {
      setDeletingGroup(false);
    }
  };

  // Study for this exam
  const handleStudyForExam = () => {
    if (!group) return;
    const prompt = group.date
      ? `I have ${group.name} on ${group.date}. Help me prepare.`
      : `I have ${group.name}. Help me prepare.`;
    setPendingPrompt(prompt);
    router.push(scopedUrl("/chat", workspaceId));
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center py-16 text-sm text-[var(--muted-foreground)]">
        <Loader2 size={20} className="mr-2 animate-spin" />
        Loading exam group...
      </div>
    );
  }

  if (error && !group) {
    return (
      <div className="p-6">
        <InlineAlert tone="danger">{error}</InlineAlert>
      </div>
    );
  }

  if (!group) return null;

  const isMetaDirty =
    name !== group.name ||
    type !== group.type ||
    date !== (group.date || "") ||
    status !== group.status;

  const isSyllabusDirty = syllabus !== (group.syllabus || "");

  const totalTopics = group.topics?.length ?? 0;
  const knownTopics =
    group.topics?.filter((t) => t.status === "known").length ?? 0;

  return (
    <div className="flex flex-col gap-6 p-4 sm:p-6">
      {/* Mobile Back Button */}
      {onBackToList && (
        <div className="flex md:hidden">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            icon={<ArrowLeft size={14} />}
            onClick={onBackToList}
            className="-ml-2 text-xs text-[var(--muted-foreground)]"
          >
            Back to exam groups
          </Button>
        </div>
      )}

      {error && <InlineAlert tone="danger">{error}</InlineAlert>}

      {/* Top Banner / Actions */}
      <div className="flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Exam Name"
              className="w-full bg-transparent text-xl font-bold tracking-tight text-[var(--foreground)] focus:outline-none focus:ring-0 sm:text-2xl"
            />
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="primary"
              size="sm"
              icon={<GraduationCap size={15} />}
              onClick={handleStudyForExam}
              className="text-xs"
            >
              Study for this exam
            </Button>

            <Button
              type="button"
              variant="secondary"
              size="sm"
              icon={
                savingMeta ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : metaSaved ? (
                  <Check size={13} className="text-emerald-500" />
                ) : (
                  <Save size={13} />
                )
              }
              disabled={!isMetaDirty || savingMeta}
              onClick={handleSaveMeta}
              className="text-xs"
            >
              {metaSaved ? "Saved" : "Save details"}
            </Button>

            <Button
              type="button"
              variant="ghost"
              size="sm"
              icon={
                deletingGroup ? (
                  <Loader2 size={13} className="animate-spin" />
                ) : (
                  <Trash2 size={13} />
                )
              }
              disabled={deletingGroup}
              onClick={handleDeleteGroup}
              className="text-xs text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:hover:bg-rose-950/30"
            >
              Delete
            </Button>
          </div>
        </div>

        {/* Editable Metadata Row */}
        <div className="grid grid-cols-1 gap-2.5 pt-2 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-[11px] font-medium text-[var(--muted-foreground)]">
              Type
            </label>
            <select
              value={type}
              onChange={(e) => setType(e.target.value as ExamType)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-xs text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none"
            >
              {EXAM_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-[var(--muted-foreground)]">
              Date
            </label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-xs text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none"
            />
          </div>

          <div>
            <label className="mb-1 block text-[11px] font-medium text-[var(--muted-foreground)]">
              Status
            </label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as ExamStatus)}
              className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-2.5 py-1.5 text-xs text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none"
            >
              {EXAM_STATUSES.map((s) => (
                <option key={s.value} value={s.value}>
                  {s.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Tutor Hint Line */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-blue-500/20 bg-blue-50/50 px-4 py-3 text-xs text-blue-900 dark:bg-blue-950/20 dark:text-blue-200">
        <p className="flex-1">
          💡 Every chat in this course can read these files. Tell the tutor
          e.g. &ldquo;I have {group.name}{' '}tomorrow&rdquo;.
        </p>
        <button
          type="button"
          onClick={handleStudyForExam}
          className="font-medium underline hover:opacity-80"
        >
          Study now →
        </button>
      </div>

      {/* Syllabus Section */}
      <div className="flex flex-col gap-2 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-[var(--foreground)]">
              Syllabus & Scope
            </h3>
            <p className="text-xs text-[var(--muted-foreground)]">
              The syllabus markdown stored in EXAM.md.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            variant="secondary"
            disabled={!isSyllabusDirty || savingSyllabus}
            loading={savingSyllabus}
            onClick={handleSaveSyllabus}
            className="text-xs"
          >
            {syllabusSaved ? "Saved" : "Save syllabus"}
          </Button>
        </div>
        <textarea
          value={syllabus}
          onChange={(e) => setSyllabus(e.target.value)}
          rows={6}
          placeholder="Paste or write the syllabus text, chapters, exam topics here..."
          className="mt-1 w-full rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 font-mono text-xs text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none"
        />
      </div>

      {/* Topic Progress Checklist */}
      <div className="flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-[var(--foreground)]">
              Topic Progress
            </h3>
            <p className="text-xs text-[var(--muted-foreground)]">
              Track mastery for this exam: {knownTopics}/{totalTopics} known
            </p>
          </div>
          {savingTopics && (
            <span className="flex items-center text-xs text-[var(--muted-foreground)]">
              <Loader2 size={12} className="mr-1 animate-spin" /> Updating...
            </span>
          )}
        </div>

        {/* Add topic form */}
        <div className="flex gap-2">
          <input
            type="text"
            value={newTopicTitle}
            onChange={(e) => setNewTopicTitle(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                void handleAddTopic();
              }
            }}
            placeholder="Add a topic (e.g. Uninformed search)..."
            className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-1.5 text-xs text-[var(--foreground)] focus:border-[var(--primary)] focus:outline-none"
          />
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={handleAddTopic}
            disabled={!newTopicTitle.trim() || savingTopics}
            icon={<Plus size={13} />}
            className="text-xs"
          >
            Add topic
          </Button>
        </div>

        {/* Topics list */}
        <div className="flex flex-col divide-y divide-[var(--border)]/30 rounded-lg border border-[var(--border)] bg-[var(--background)]">
          {(!group.topics || group.topics.length === 0) ? (
            <div className="p-4 text-center text-xs text-[var(--muted-foreground)]">
              No topics added yet. Add topics to track your exam readiness.
            </div>
          ) : (
            group.topics.map((topic, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between gap-3 px-3 py-2 text-xs"
              >
                <span className="truncate font-medium text-[var(--foreground)]">
                  {topic.title}
                </span>

                <div className="flex shrink-0 items-center gap-2">
                  <select
                    value={topic.status}
                    onChange={(e) =>
                      handleUpdateTopicStatus(
                        idx,
                        e.target.value as TopicStatus,
                      )
                    }
                    className={`rounded-md border-0 px-2 py-0.5 text-[11px] font-medium leading-none focus:outline-none ${
                      TOPIC_STATUS_STYLES[topic.status] || ""
                    }`}
                  >
                    <option value="todo">To Do</option>
                    <option value="learning">Learning</option>
                    <option value="known">Known</option>
                    <option value="skipped">Skipped</option>
                  </select>

                  <button
                    type="button"
                    onClick={() => void handleRemoveTopic(idx)}
                    className="rounded p-1 text-[var(--muted-foreground)] hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-950/40"
                    title="Remove topic"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Files & Folder Tree */}
      <div className="flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 shadow-sm">
        <div>
          <h3 className="text-sm font-semibold text-[var(--foreground)]">
            Exam Resources & Files
          </h3>
          <p className="text-xs text-[var(--muted-foreground)]">
            Upload slides, past papers (PYQ), notes, and photos for this exam.
          </p>
        </div>

        {/* Drag & drop upload area */}
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragOver(true);
          }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setIsDragOver(false);
            if (e.dataTransfer.files) {
              void handleUploadFiles(e.dataTransfer.files);
            }
          }}
          className={`relative flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition-colors ${
            isDragOver
              ? "border-[var(--primary)] bg-[var(--primary)]/5"
              : "border-[var(--border)] hover:border-[var(--foreground)]/30"
          }`}
        >
          <input
            type="file"
            multiple
            id="exam-group-file-upload"
            onChange={(e) => {
              if (e.target.files) {
                void handleUploadFiles(e.target.files);
              }
            }}
            className="absolute inset-0 cursor-pointer opacity-0"
          />
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--muted)] text-[var(--muted-foreground)]">
            {uploading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Upload size={18} />
            )}
          </div>
          <p className="mt-2 text-xs font-medium text-[var(--foreground)]">
            {uploading
              ? "Uploading files..."
              : "Drag & drop files here, or click to browse"}
          </p>
          <p className="mt-0.5 text-[11px] text-[var(--muted-foreground)]">
            PDFs, slides, past papers, notes (up to 50 MB each)
          </p>

          <div
            onClick={(e) => e.stopPropagation()}
            className="mt-3 flex items-center gap-2"
          >
            <label className="text-[11px] text-[var(--muted-foreground)]">
              Subfolder (optional):
            </label>
            <input
              type="text"
              value={uploadFolder}
              onChange={(e) => setUploadFolder(e.target.value)}
              placeholder="e.g. pyq, slides"
              className="w-36 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 py-0.5 text-xs text-[var(--foreground)]"
            />
          </div>
        </div>

        {uploadMessage && (
          <InlineAlert tone="success">{uploadMessage}</InlineAlert>
        )}

        {/* File Tree */}
        <div className="mt-1">
          <FileTree
            nodes={treeNodes}
            onDeleteFile={handleDeleteFile}
            loading={treeLoading}
          />
        </div>
      </div>
    </div>
  );
}

export default ExamGroupDetail;
