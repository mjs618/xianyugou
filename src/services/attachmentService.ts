import { db } from '@/db';
import type { Attachment } from '@/types';

// 单附件最大 5MB
export const MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024;

// 允许的图片 MIME 类型
export const ACCEPTED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];

// 新增附件（存储 Blob）
export async function addAttachment(file: File): Promise<Attachment> {
  if (file.size > MAX_ATTACHMENT_SIZE) {
    throw new Error(`附件大小不能超过 ${MAX_ATTACHMENT_SIZE / 1024 / 1024}MB`);
  }
  if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
    throw new Error('仅支持 JPG/PNG/WebP/GIF 图片格式');
  }
  const record: Attachment = {
    name: file.name,
    type: file.type,
    size: file.size,
    blob: file,
    created_at: new Date(),
  };
  const id = await db.attachments.add(record);
  return { ...record, id };
}

// 批量新增附件，返回 id 字符串数组（供 attachments 字段引用）
export async function addAttachments(files: File[]): Promise<string[]> {
  const ids: string[] = [];
  for (const file of files) {
    const att = await addAttachment(file);
    ids.push(String(att.id));
  }
  return ids;
}

// 获取单个附件
export async function getAttachment(id: number): Promise<Attachment | undefined> {
  return db.attachments.get(id);
}

// 按 id 字符串数组批量查询附件
export async function getAttachments(ids: string[]): Promise<Attachment[]> {
  if (ids.length === 0) return [];
  const numIds = ids.map((s) => Number(s)).filter((n) => !Number.isNaN(n));
  const list = await db.attachments.bulkGet(numIds);
  return list.filter((a): a is Attachment => !!a);
}

// 删除附件
export async function deleteAttachment(id: number): Promise<void> {
  await db.attachments.delete(id);
}

// 批量删除附件（按 id 字符串数组）
export async function deleteAttachments(ids: string[]): Promise<void> {
  const numIds = ids.map((s) => Number(s)).filter((n) => !Number.isNaN(n));
  await db.attachments.bulkDelete(numIds);
}

// 为附件生成预览 URL（调用方负责 revokeObjectURL）
export function createObjectURL(blob: Blob): string {
  return URL.createObjectURL(blob);
}

// 获取附件总数与占用空间
export async function getStorageStats(): Promise<{ count: number; totalSize: number }> {
  const all = await db.attachments.toArray();
  return {
    count: all.length,
    totalSize: all.reduce((s, a) => s + a.size, 0),
  };
}
