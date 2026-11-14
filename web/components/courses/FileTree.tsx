"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useState } from "react";
import {
  ChevronDown,
  ChevronRight,
  FileText,
  Folder,
  FolderOpen,
  Loader2,
  Trash2,
} from "lucide-react";
import type { FileTreeNode } from "@/lib/courses-api";

interface FileTreeProps {
  nodes: FileTreeNode[];
  onDeleteFile: (path: string) => Promise<void>;
  loading?: boolean;
}

function formatBytes(bytes: number): string {
  if (bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  const value = bytes / Math.pow(1024, i);
  return `${value < 10 && i > 0 ? value.toFixed(1) : Math.round(value)} ${units[i]}`;
}

interface TreeNodeItemProps {
  node: FileTreeNode;
  depth: number;
  onDeleteFile: (path: string) => Promise<void>;
  deletingPath: string | null;
  setDeletingPath: (path: string | null) => void;
}

function TreeNodeItem({
  node,
  depth,
  onDeleteFile,
  deletingPath,
  setDeletingPath,
}: TreeNodeItemProps) {
  const [open, setOpen] = useState(true);

  if (node.name === "EXAM.md") {
    // EXAM.md is the metadata and syllabus file managed by the editor
    return null;
  }

  if (node.type === "dir") {
    const visibleChildren = (node.children || []).filter(
      (c) => c.name !== "EXAM.md",
    );
    return (
      <div className="flex flex-col">
        <button
          type="button"
          onClick={() => setOpen(!open)}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
          className="flex w-full items-center gap-1.5 rounded-lg py-1.5 pr-2 text-left text-[13px] text-[var(--foreground)] hover:bg-[var(--muted)]/60"
        >
          <span className="text-[var(--muted-foreground)]">
            {open ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </span>
          <span className="text-[var(--muted-foreground)]">
            {open ? <FolderOpen size={15} /> : <Folder size={15} />}
          </span>
          <span className="truncate font-medium">{node.name}</span>
          <span className="ml-auto text-[11px] text-[var(--muted-foreground)]/60">
            {visibleChildren.length} item{visibleChildren.length === 1 ? "" : "s"}
          </span>
        </button>

        {open && visibleChildren.length > 0 && (
          <div className="flex flex-col">
            {visibleChildren.map((child) => (
              <TreeNodeItem
                key={child.path}
                node={child}
                depth={depth + 1}
                onDeleteFile={onDeleteFile}
                deletingPath={deletingPath}
                setDeletingPath={setDeletingPath}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const isDeleting = deletingPath === node.path;

  return (
    <div
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
      className="group flex items-center justify-between gap-2 rounded-lg py-1.5 pr-2 text-[13px] hover:bg-[var(--muted)]/60"
    >
      <div className="flex min-w-0 items-center gap-2">
        <FileText
          size={14}
          className="shrink-0 text-[var(--muted-foreground)]"
        />
        <span className="truncate font-mono text-[12.5px] text-[var(--foreground)]">
          {node.name}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2.5">
        <span className="text-[11px] text-[var(--muted-foreground)]">
          {formatBytes(node.size)}
        </span>
        <button
          type="button"
          disabled={isDeleting}
          onClick={async () => {
            const confirmed = window.confirm(
              `Delete "${node.name}" from this exam group?`,
            );
            if (!confirmed) return;
            setDeletingPath(node.path);
            try {
              await onDeleteFile(node.path);
            } finally {
              setDeletingPath(null);
            }
          }}
          className="rounded p-1 text-[var(--muted-foreground)] opacity-0 transition-opacity hover:bg-rose-50 hover:text-rose-600 group-hover:opacity-100 disabled:opacity-50 dark:hover:bg-rose-950/40"
          title={`Delete ${node.name}`}
          aria-label={`Delete ${node.name}`}
        >
          {isDeleting ? (
            <Loader2 size={13} className="animate-spin" />
          ) : (
            <Trash2 size={13} />
          )}
        </button>
      </div>
    </div>
  );
}

export function FileTree({ nodes, onDeleteFile, loading }: FileTreeProps) {
  const [deletingPath, setDeletingPath] = useState<string | null>(null);

  const visibleNodes = nodes.filter((n) => n.name !== "EXAM.md");

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8 text-sm text-[var(--muted-foreground)]">
        <Loader2 size={16} className="mr-2 animate-spin" />
        Loading files...
      </div>
    );
  }

  if (visibleNodes.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-[var(--border)] p-6 text-center text-xs text-[var(--muted-foreground)]">
        No files uploaded yet for this exam group.
      </div>
    );
  }

  return (
    <div className="flex flex-col divide-y divide-[var(--border)]/30 rounded-xl border border-[var(--border)] bg-[var(--background)] p-1.5">
      {visibleNodes.map((node) => (
        <TreeNodeItem
          key={node.path}
          node={node}
          depth={0}
          onDeleteFile={onDeleteFile}
          deletingPath={deletingPath}
          setDeletingPath={setDeletingPath}
        />
      ))}
    </div>
  );
}

export default FileTree;
