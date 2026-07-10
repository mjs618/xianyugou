import type { Attachment } from '@/types';
import { apiClient, getApiUrl } from './apiClient';

export const MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024;
export const ACCEPTED_IMAGE_TYPES = [
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
];

type AttachmentResponse = Omit<Attachment, 'created_at'> & {
  created_at: string | Date;
};

function normalizeAttachment(item: AttachmentResponse): Attachment {
  return { ...item, created_at: new Date(item.created_at) };
}

export async function addAttachment(file: File): Promise<Attachment> {
  if (file.size > MAX_ATTACHMENT_SIZE) {
    throw new Error('附件大小不能超过 5MB');
  }
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    throw new Error('仅支持 JPG/PNG/WebP/GIF 图片格式');
  }
  const form = new FormData();
  form.append('file', file);
  const item = await apiClient.postForm<AttachmentResponse>(
    '/api/attachments',
    form,
  );
  return normalizeAttachment(item);
}

export async function getAttachments(ids: string[]): Promise<Attachment[]> {
  const numericIds = ids.map(Number).filter(Number.isInteger);
  if (numericIds.length === 0) return [];
  const items = await apiClient.post<AttachmentResponse[]>(
    '/api/attachments/batch',
    { ids: numericIds },
  );
  return items.map(normalizeAttachment);
}

export function getAttachmentContentUrl(id: number): string {
  return getApiUrl(`/api/attachments/${id}/content`);
}

export async function deleteAttachment(id: number): Promise<void> {
  await apiClient.delete(`/api/attachments/${id}`);
}
