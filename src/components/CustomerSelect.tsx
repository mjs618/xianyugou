import { useEffect, useState } from 'react';
import { Select, Tag, message } from 'antd';
import { searchCustomers, getRecentCustomers } from '@/services/customerService';
import type { Customer } from '@/types';

interface Props {
  value?: number;
  onChange?: (value: number | undefined, customer?: Customer) => void;
  placeholder?: string;
  excludeId?: number;
  allowClear?: boolean;
}

export default function CustomerSelect({ value, onChange, placeholder = '搜索客户昵称或联系方式', excludeId, allowClear = true }: Props) {
  const [options, setOptions] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // 初始加载最近客户
    getRecentCustomers(20)
      .then((list) => {
        setOptions(list.filter((c) => c.id !== excludeId));
      })
      .catch((err: unknown) => {
        console.error('加载最近客户失败:', err);
        message.error('加载客户列表失败，请重试');
      });
  }, [excludeId]);

  const handleSearch = async (keyword: string) => {
    if (!keyword) {
      const list = await getRecentCustomers(20);
      setOptions(list.filter((c) => c.id !== excludeId));
      return;
    }
    setLoading(true);
    try {
      const list = await searchCustomers(keyword);
      setOptions(list.filter((c) => c.id !== excludeId));
    } finally {
      setLoading(false);
    }
  };

  return (
    <Select
      showSearch
      allowClear={allowClear}
      value={value}
      placeholder={placeholder}
      style={{ width: '100%' }}
      loading={loading}
      filterOption={false}
      onSearch={handleSearch}
      onChange={(v) => {
        const c = options.find((o) => o.id === v);
        onChange?.(v, c);
      }}
      options={options.map((c) => ({
        value: c.id,
        label: (
          <span>
            <span>{c.xianyu_nickname}</span>
            {c.is_blacklist && <Tag color="red" style={{ marginLeft: 8, fontSize: 11 }}>黑名单</Tag>}
            {c.level !== 'normal' && <Tag color={c.level === 'core' ? 'red' : 'gold'} style={{ marginLeft: 4, fontSize: 11 }}>{c.level === 'core' ? '核心' : 'VIP'}</Tag>}
          </span>
        ),
      }))}
    />
  );
}
