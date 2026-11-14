// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { apiFetch, apiUrl, asJsonOrThrow } from "@/lib/api";

export type ExamType =
  | "class_test"
  | "quiz"
  | "viva"
  | "mid_term"
  | "term_final"
  | "assignment"
  | "other";

export type ExamStatus = "planned" | "preparing" | "done";

export type TopicStatus = "todo" | "learning" | "known" | "skipped";

export interface ExamTopic {
  title: string;
  status: TopicStatus;
}

export interface ExamProgress {
  known: number;
  total: number;
}

export interface ExamGroup {
  slug: string;
  name: string;
  type: ExamType;
  date: string;
  status: ExamStatus;
  syllabus: string;
  topics: ExamTopic[];
  progress: ExamProgress;
  file_count: number;
  updated_at: string;
}

export interface CourseNextExam {
  slug: string;
  name: string;
  date: string;
}

export interface CourseInfo {
  workspace_id: string;
  display_name: string;
  kind: string;
  group_count: number;
  next_exam: CourseNextExam | null;
}

export interface CreateExamGroupPayload {
  name: string;
  type?: ExamType;
  date?: string;
  syllabus?: string;
}

export interface UpdateExamGroupPayload {
  name?: string;
  type?: ExamType;
  date?: string;
  status?: ExamStatus;
  syllabus?: string;
  topics?: ExamTopic[];
}

export interface FileTreeNode {
  name: string;
  path: string;
  type: "file" | "dir";
  size: number;
  children?: FileTreeNode[];
}

export interface UploadFileResponse {
  slug: string;
  path: string;
  size: number;
}

export interface CourseSettings {
  default_persona: string;
}

export async function listCourses(): Promise<CourseInfo[]> {
  const response = await apiFetch(apiUrl("/api/courses"), {
    cache: "no-store",
  });
  const data = await asJsonOrThrow(response);
  return Array.isArray(data?.courses) ? data.courses : [];
}

export async function listGroups(workspaceId: string): Promise<ExamGroup[]> {
  const response = await apiFetch(
    apiUrl(`/api/courses/${encodeURIComponent(workspaceId)}/groups`),
    {
      cache: "no-store",
    },
  );
  const data = await asJsonOrThrow(response);
  return Array.isArray(data?.groups) ? data.groups : [];
}

export async function getGroup(
  workspaceId: string,
  slug: string,
): Promise<ExamGroup> {
  const response = await apiFetch(
    apiUrl(
      `/api/courses/${encodeURIComponent(workspaceId)}/groups/${encodeURIComponent(slug)}`,
    ),
    {
      cache: "no-store",
    },
  );
  const data = await asJsonOrThrow(response);
  return data.group;
}

export async function createGroup(
  workspaceId: string,
  payload: CreateExamGroupPayload,
): Promise<ExamGroup> {
  const response = await apiFetch(
    apiUrl(`/api/courses/${encodeURIComponent(workspaceId)}/groups`),
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const data = await asJsonOrThrow(response);
  return data.group;
}

export async function updateGroup(
  workspaceId: string,
  slug: string,
  payload: UpdateExamGroupPayload,
): Promise<ExamGroup> {
  const response = await apiFetch(
    apiUrl(
      `/api/courses/${encodeURIComponent(workspaceId)}/groups/${encodeURIComponent(slug)}`,
    ),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const data = await asJsonOrThrow(response);
  return data.group;
}

export async function deleteGroup(
  workspaceId: string,
  slug: string,
  force = false,
): Promise<void> {
  const url = `/api/courses/${encodeURIComponent(workspaceId)}/groups/${encodeURIComponent(slug)}${force ? "?force=true" : ""}`;
  const response = await apiFetch(apiUrl(url), {
    method: "DELETE",
  });
  if (!response.ok) {
    await asJsonOrThrow(response);
  }
}

export async function getGroupTree(
  workspaceId: string,
  slug: string,
): Promise<FileTreeNode[]> {
  const response = await apiFetch(
    apiUrl(
      `/api/courses/${encodeURIComponent(workspaceId)}/groups/${encodeURIComponent(slug)}/tree`,
    ),
    {
      cache: "no-store",
    },
  );
  const data = await asJsonOrThrow(response);
  return Array.isArray(data?.tree) ? data.tree : [];
}

export async function uploadGroupFile(
  workspaceId: string,
  slug: string,
  file: File,
  folder?: string,
): Promise<UploadFileResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (folder && folder.trim()) {
    formData.append("folder", folder.trim());
  }

  const response = await apiFetch(
    apiUrl(
      `/api/courses/${encodeURIComponent(workspaceId)}/groups/${encodeURIComponent(slug)}/files`,
    ),
    {
      method: "POST",
      body: formData,
    },
  );
  return await asJsonOrThrow(response);
}

export async function deleteGroupFile(
  workspaceId: string,
  slug: string,
  path: string,
): Promise<void> {
  const response = await apiFetch(
    apiUrl(
      `/api/courses/${encodeURIComponent(workspaceId)}/groups/${encodeURIComponent(slug)}/files?path=${encodeURIComponent(path)}`,
    ),
    {
      method: "DELETE",
    },
  );
  if (!response.ok) {
    await asJsonOrThrow(response);
  }
}

export async function getCourseSettings(
  workspaceId: string,
): Promise<CourseSettings> {
  const response = await apiFetch(
    apiUrl(`/api/courses/${encodeURIComponent(workspaceId)}/settings`),
    {
      cache: "no-store",
    },
  );
  const data = await asJsonOrThrow(response);
  return data?.settings ?? { default_persona: "" };
}

export async function putCourseSettings(
  workspaceId: string,
  payload: { default_persona: string },
): Promise<CourseSettings> {
  const response = await apiFetch(
    apiUrl(`/api/courses/${encodeURIComponent(workspaceId)}/settings`),
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );
  const data = await asJsonOrThrow(response);
  return data?.settings ?? { default_persona: "" };
}
