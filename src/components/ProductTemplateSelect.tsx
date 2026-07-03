import { useEffect, useState } from 'react';
import { Select } from 'antd';
import { listTemplates } from '@/services/productTemplateService';
import type { ProductTemplate } from '@/types';

interface Props {
  value?: number;
  onChange?: (value: number | undefined, template?: ProductTemplate) => void;
  placeholder?: string;
}

export default function ProductTemplateSelect({ value, onChange, placeholder = '选择商品模板（自动填充成本）' }: Props) {
  const [templates, setTemplates] = useState<ProductTemplate[]>([]);

  useEffect(() => {
    listTemplates().then(setTemplates);
  }, []);

  return (
    <Select
      allowClear
      showSearch
      value={value}
      placeholder={placeholder}
      style={{ width: '100%' }}
      filterOption={(input, option) => (option?.label ?? '').toLowerCase().includes(input.toLowerCase())}
      onChange={(v) => {
        const t = templates.find((t) => t.id === v);
        onChange?.(v, t);
      }}
      options={templates.map((t) => ({
        value: t.id,
        label: `${t.name}（成本¥${t.default_cost}${t.default_sale_price ? `/建议¥${t.default_sale_price}` : ''}）`,
      }))}
    />
  );
}
