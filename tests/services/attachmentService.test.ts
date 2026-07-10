import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  getMockCalls,
  mockApiFactory,
  resetMockApi,
  setMockResponse,
} from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  addAttachment,
  deleteAttachment,
  getAttachmentContentUrl,
  getAttachments,
} from '@/services/attachmentService';

describe('attachmentService', () => {
  beforeEach(resetMockApi);

  it('上传图片使用 multipart 并归一化时间', async () => {
    setMockResponse('postForm', '/api/attachments', {
      id: 7,
      name: 'a.png',
      type: 'image/png',
      size: 3,
      created_at: '2026-07-10T00:00:00Z',
    });
    const file = new File(['abc'], 'a.png', { type: 'image/png' });

    const result = await addAttachment(file);

    expect(result.created_at).toBeInstanceOf(Date);
    expect(getMockCalls('postForm', '/api/attachments')[0].body).toBeInstanceOf(
      FormData,
    );
  });

  it('批量加载附件元数据并保持后端顺序', async () => {
    setMockResponse('post', '/api/attachments/batch', [
      {
        id: 2,
        name: 'b.png',
        type: 'image/png',
        size: 2,
        created_at: '2026-07-10T00:00:00Z',
      },
      {
        id: 1,
        name: 'a.png',
        type: 'image/png',
        size: 1,
        created_at: '2026-07-10T00:00:00Z',
      },
    ]);

    const result = await getAttachments(['2', 'bad', '1']);

    expect(result.map((item) => item.id)).toEqual([2, 1]);
    expect(getMockCalls('post', '/api/attachments/batch')[0].body).toEqual({
      ids: [2, 1],
    });
  });

  it('生成统一后端内容 URL 并删除附件', async () => {
    setMockResponse('delete', '/api/attachments/3', { ok: true });

    expect(getAttachmentContentUrl(3)).toBe(
      'http://localhost:8000/api/attachments/3/content',
    );
    await deleteAttachment(3);

    expect(getMockCalls('delete', '/api/attachments/3')).toHaveLength(1);
  });
});
