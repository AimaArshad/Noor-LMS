import { api } from "@/api/client";
import type { UploadedFile } from "@/types";

export const filesApi = {
  /** Multipart upload; `onProgress` receives 0-100. The server verifies type and content. */
  upload: (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return api
      .post<UploadedFile>("/files/upload", form, {
        timeout: 120_000,
        onUploadProgress: (event) => {
          if (event.total) onProgress?.(Math.round((event.loaded * 100) / event.total));
        },
      })
      .then((r) => r.data);
  },

  /** Uploader only, and only while the file is not attached to anything (else 409). */
  remove: (id: string) => api.delete(`/files/${id}`).then(() => undefined),

  /** Authenticated download as a Blob (an `<img src>` cannot send the bearer token). */
  blob: (id: string) => api.get<Blob>(`/files/${id}`, { responseType: "blob" }).then((r) => r.data),
};
