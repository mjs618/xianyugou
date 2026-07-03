import { describe, it, expect, beforeEach } from 'vitest';
import { mockApiFactory, resetMockApi, setMockResponse, getMockCalls } from '../mockApiClient';

vi.mock('@/services/apiClient', () => mockApiFactory());
import {
  listTemplates,
  listActiveTemplates,
  createTemplate,
  updateTemplate,
  deleteTemplate,
  toggleActive,
} from '@/services/productTemplateService';

const TPL = (over: any = {}) => ({
  id: 1, name: '软件激活码', default_cost: 30, default_sale_price: 128,
  category: '激活码', warranty_days: 30, is_active: true,
  created_at: '2026-06-01', updated_at: '2026-06-01', ...over,
});

describe('productTemplateService', () => {
  beforeEach(() => {
    resetMockApi();
  });

  it('createTemplate 应 POST 并带默认 warranty_days/is_active', async () => {
    setMockResponse('post', '/api/product-templates', TPL());
    const t = await createTemplate({ name: '软件激活码', default_cost: 30, default_sale_price: 128, category: '激活码' });
    expect(t.id).toBe(1);
    expect(t.created_at).toBeInstanceOf(Date);
    const body = getMockCalls('post', '/api/product-templates')[0].body as any;
    expect(body.warranty_days).toBe(30); // 默认
    expect(body.is_active).toBe(true);
  });

  it('createTemplate 自定义 warranty_days', async () => {
    setMockResponse('post', '/api/product-templates', TPL({ warranty_days: 180 }));
    await createTemplate({ name: '长期', default_cost: 100, warranty_days: 180 });
    expect((getMockCalls('post', '/api/product-templates')[0].body as any).warranty_days).toBe(180);
  });

  it('listTemplates 应 GET 并按 name 排序', async () => {
    setMockResponse('get', '/api/product-templates', [TPL({ id: 2, name: 'B' }), TPL({ id: 1, name: 'A' })]);
    const list = await listTemplates();
    expect(list[0].name).toBe('A');
    expect(list[1].name).toBe('B');
  });

  it('listActiveTemplates 应传 active_only', async () => {
    setMockResponse('get', '/api/product-templates', [TPL()], { active_only: true });
    await listActiveTemplates();
    expect((getMockCalls('get', '/api/product-templates')[0].params as any).active_only).toBe(true);
  });

  it('updateTemplate 应 PATCH', async () => {
    setMockResponse('patch', '/api/product-templates/1', TPL({ name: '新名称', default_cost: 50 }));
    await updateTemplate(1, { name: '新名称', default_cost: 50 });
    const body = getMockCalls('patch', '/api/product-templates/1')[0].body as any;
    expect(body.name).toBe('新名称');
  });

  it('toggleActive 应 POST /toggle', async () => {
    setMockResponse('post', '/api/product-templates/1/toggle', TPL({ is_active: false }));
    await toggleActive(1);
    expect(getMockCalls('post', '/api/product-templates/1/toggle').length).toBe(1);
  });

  it('deleteTemplate 应 DELETE', async () => {
    setMockResponse('delete', '/api/product-templates/1', { message: '已删除' });
    await deleteTemplate(1);
    expect(getMockCalls('delete', '/api/product-templates/1').length).toBe(1);
  });
});
