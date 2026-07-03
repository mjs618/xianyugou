import { useState, useMemo, useEffect, useRef, useCallback } from 'react';
import { AutoComplete, Input, Space, Tag } from 'antd';
import { SearchOutlined, UserOutlined, ShoppingOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { listCustomers } from '@/services/customerService';
import { listTransactions } from '@/services/transactionService';
import { formatMoney } from '@/utils/format';
import type { Customer, Transaction } from '@/types';

/** 缓存 TTL（毫秒）：60 秒后过期重新加载 */
const CACHE_TTL = 60 * 1000;

interface SearchCache {
  customers: Customer[];
  transactions: Transaction[];
  loadedAt: number;
}

/** 全局数据缓存：避免每次输入都全量加载 */
let globalCache: SearchCache | null = null;

async function ensureCache(): Promise<SearchCache> {
  const now = Date.now();
  if (globalCache && now - globalCache.loadedAt < CACHE_TTL) {
    return globalCache;
  }
  const [customers, transactions] = await Promise.all([
    listCustomers(),
    listTransactions(),
  ]);
  globalCache = { customers, transactions, loadedAt: now };
  return globalCache;
}

/** 清除缓存（数据变更后调用） */
export function invalidateSearchCache() {
  globalCache = null;
}

export default function GlobalSearch() {
  const navigate = useNavigate();
  const [keyword, setKeyword] = useState('');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // 快捷键 Cmd+K / Ctrl+K 聚焦搜索框
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // 防抖搜索
  useEffect(() => {
    if (!keyword.trim()) {
      setCustomers([]);
      setTransactions([]);
      return;
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      const kw = keyword.trim().toLowerCase();
      try {
        const cache = await ensureCache();
        // 扩展搜索范围：客户（昵称、联系方式、备注）、交易（商品名、订单号）
        setCustomers(
          cache.customers
            .filter(
              (c) =>
                !c.deleted_at &&
                (c.xianyu_nickname.toLowerCase().includes(kw) ||
                  (c.contact_info || '').toLowerCase().includes(kw) ||
                  (c.notes || '').toLowerCase().includes(kw))
            )
            .slice(0, 5)
        );
        setTransactions(
          cache.transactions
            .filter(
              (t) =>
                !t.deleted_at &&
                (t.product_name.toLowerCase().includes(kw) ||
                  (t.xianyu_order_no || '').toLowerCase().includes(kw))
            )
            .slice(0, 5)
        );
      } catch (err) {
        console.error('全局搜索失败:', err);
      } finally {
        setLoading(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [keyword]);

  const options = useMemo(() => {
    const result: any[] = [];
    if (customers.length > 0) {
      result.push({
        label: <Space><UserOutlined style={{ color: 'var(--theme-primary)' }} /><span style={{ fontWeight: 600 }}>客户</span></Space>,
        options: customers.map((c) => ({
          value: `customer-${c.id}`,
          label: (
            <Space>
              <UserOutlined />
              <span>{c.xianyu_nickname}</span>
              {c.level === 'vip' && <Tag color="gold" style={{ fontSize: 10 }}>VIP</Tag>}
              {c.level === 'core' && <Tag color="red" style={{ fontSize: 10 }}>核心</Tag>}
            </Space>
          ),
        })),
      });
    }
    if (transactions.length > 0) {
      result.push({
        label: <Space><ShoppingOutlined style={{ color: 'var(--theme-primary)' }} /><span style={{ fontWeight: 600 }}>交易</span></Space>,
        options: transactions.map((t) => ({
          value: `transaction-${t.id}`,
          label: (
            <Space>
              <ShoppingOutlined />
              <span>{t.product_name}</span>
              <span style={{ color: 'var(--theme-primary)', fontSize: 12 }}>{formatMoney(t.sale_price)}</span>
            </Space>
          ),
        })),
      });
    }
    if (keyword.trim() && customers.length === 0 && transactions.length === 0 && !loading) {
      result.push({
        label: <span style={{ color: 'var(--color-text-secondary)' }}>未找到相关结果</span>,
        options: [],
      });
    }
    return result;
  }, [customers, transactions, keyword, loading]);

  const handleSelect = useCallback((value: string) => {
    if (value.startsWith('customer-')) {
      navigate(`/customers/${value.replace('customer-', '')}`);
    } else if (value.startsWith('transaction-')) {
      navigate(`/transactions/${value.replace('transaction-', '')}`);
    }
    setKeyword('');
  }, [navigate]);

  return (
    <AutoComplete
      className="global-search"
      style={{ width: 250 }}
      options={options}
      value={keyword}
      onChange={setKeyword}
      onSelect={handleSelect}
      placeholder="搜索客户、交易... (Ctrl+K)"
    >
      <Input
        ref={inputRef as any}
        size="middle"
        prefix={<SearchOutlined style={{ color: 'var(--color-text-secondary)' }} />}
        aria-label="全局搜索"
        onKeyDown={(e) => {
          if (e.key === 'Escape' && keyword) {
            e.preventDefault();
            setKeyword('');
            inputRef.current?.blur();
          }
        }}
      />
    </AutoComplete>
  );
}
