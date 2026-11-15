"use client";

// Added in the RH.RONY fork of DeepTutor (Apache-2.0). Not part of upstream.

import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import {
  checkReadingDuplicates,
  importReadingUrls,
} from "@/lib/reading-workspace-api";
import { readingCollectionRoute } from "@/lib/learning-routes";

/**
 * Open a web lesson in Immersive Reading (the tutor sits beside it).
 * The first time imports the page into this course's library; after that the
 * same reading collection is reused.
 */
export function useOpenInReader(courseWorkspaceId: string) {
  const router = useRouter();
  const [busyUrl, setBusyUrl] = useState("");
  const [readerError, setReaderError] = useState<string | null>(null);

  const openInReader = useCallback(
    async (url: string, title: string) => {
      setBusyUrl(url);
      setReaderError(null);
      try {
        const matches = await checkReadingDuplicates({ urls: [url] });
        const existing = matches.find(
          (match) => match.query.url === url && match.collections.length > 0,
        );
        const collectionId = existing
          ? existing.collections[0].workspace_id
          : (await importReadingUrls({ urls: [url], workspace_title: title }))
              .workspace.workspace_id;
        router.push(readingCollectionRoute(collectionId, courseWorkspaceId));
      } catch (err) {
        setReaderError(
          err instanceof Error ? err.message : "Could not open the lesson in the reader.",
        );
      } finally {
        setBusyUrl("");
      }
    },
    [courseWorkspaceId, router],
  );

  return { openInReader, busyUrl, readerError };
}
