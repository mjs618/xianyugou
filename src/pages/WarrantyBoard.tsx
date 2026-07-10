import { useEffect, useState } from 'react';
import { Card, Row, Col, Empty, Spin, Button, Tag, Space, Segmented, message, Modal, InputNumber, Input, Tabs, Calendar, Badge } from 'antd';
import { ExportOutlined, ClockCircleOutlined, PlusOutlined, ToolOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { getAllWarrantyTransactions, getUrgentTransactions, getExpiredTransactions, extendWarranty, endWarrantyEarly } from '@/services/warrantyService';
import { db } from '@/db';
import { createAfterSales } from '@/services/afterSalesService';
import { exportTransactionsCSV, downloadFile } from '@/utils/export';
import { formatMoney } from '@/utils/format';
import { formatDate, formatDateTime } from '@/utils/date';
import WarrantyTag from '@/components/WarrantyTag';
import AttachmentUpload from '@/components/AttachmentUpload';
import { getWarrantyStartLabel, getWarrantyStatus } from '@/utils/warranty';
import dayjs from 'dayjs';
import type { Transaction, Customer } from '@/types';

type ViewType = 'board' | 'list' | 'calendar';
type FilterType = 'all' | 'urgent' | 'active' | 'expired';

export default function WarrantyBoard() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<ViewType>('board');
  const [filter, setFilter] = useState<FilterType>('all');
  const [all, setAll] = useState<Transaction[]>([]);
  const [customers, setCustomers] = useState<Map<number, Customer>>(new Map());
  const [extendModal, setExtendModal] = useState<{ open: boolean; tx?: Transaction }>({ open: false });
  const [extendDays, setExtendDays] = useState(30);
  const [endModal, setEndModal] = useState<{ open: boolean; tx?: Transaction }>({ open: false });
  const [endReason, setEndReason] = useState('');
  const [aftersalesModal, setAftersalesModal] = useState<{ open: boolean; tx?: Transaction }>({ open: false });
  const [aftersalesIssue, setAftersalesIssue] = useState('');
  const [aftersalesAttachments, setAftersalesAttachments] = useState<string[]>([]);

  const loadData = async () => {
    setLoading(true);
    try {
      const list = await getAllWarrantyTransactions();
      // 批量加载关联客户（一次查询，避免 N+1）
      const ids = Array.from(new Set(list.map((t) => t.customer_id)));
      const cs = await db.customers.bulkGet(ids);
      const map = new Map<number, Customer>();
      cs.forEach((c) => { if (c) map.set(c.id!, c); });
      setCustomers(map);
      list.sort((a, b) => new Date(a.warranty_end!).getTime() - new Date(b.warranty_end!).getTime());
      setAll(list);
    } catch (err) {
      console.error('质保数据加载失败:', err);
      message.error('数据加载失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const urgent = all.filter((t) => {
    const ws = getWarrantyStatus(t.warranty_end);
    return ws.type === 'urgent';
  });
  const active = all.filter((t) => {
    const ws = getWarrantyStatus(t.warranty_end);
    return ws.type === 'active';
  });
  const expired = all.filter((t) => {
    const ws = getWarrantyStatus(t.warranty_end);
    return ws.type === 'expired';
  });

  const handleExport = () => {
    const csv = exportTransactionsCSV(all);
    downloadFile(csv, `质保明细_${dayjs().format('YYYYMMDD')}.csv`, 'text/csv');
    message.success(`已导出 ${all.length} 条`);
  };

  // 按筛选条件过滤
  const filtered = all.filter((t) => {
    const ws = getWarrantyStatus(t.warranty_end);
    if (filter === 'all') return true;
    return ws.type === filter;
  });

  const handleExtendWarranty = async () => {
    if (!extendModal.tx) return;
    try {
      await extendWarranty(extendModal.tx.id!, extendDays);
      message.success(`质保已延长 ${extendDays} 天`);
      setExtendModal({ open: false });
      setExtendDays(30);
      loadData();
    } catch (err) {
      console.error('延长质保失败:', err);
      message.error(err instanceof Error ? err.message : '延长质保失败');
    }
  };

  const handleEndWarranty = async () => {
    if (!endModal.tx) return;
    try {
      await endWarrantyEarly(endModal.tx.id!, endReason.trim() || undefined);
      message.success('质保已提前结束');
      setEndModal({ open: false });
      setEndReason('');
      loadData();
    } catch (err) {
      console.error('提前结束质保失败:', err);
      message.error(err instanceof Error ? err.message : '操作失败');
    }
  };

  const handleCreateAftersales = async () => {
    if (!aftersalesModal.tx || !aftersalesIssue.trim()) {
      message.warning('请填写问题描述');
      return;
    }
    try {
      await createAfterSales({
        transaction_id: aftersalesModal.tx.id!,
        issue_desc: aftersalesIssue.trim(),
        attachments: aftersalesAttachments,
      });
      message.success('售后工单已创建');
      setAftersalesModal({ open: false });
      setAftersalesIssue('');
      setAftersalesAttachments([]);
      loadData();
    } catch (err) {
      console.error('创建售后工单失败:', err);
      message.error(err instanceof Error ? err.message : '创建售后工单失败');
    }
  };

  const renderCard = (t: Transaction) => {
    const c = customers.get(t.customer_id);
    const ws = getWarrantyStatus(t.warranty_end);
    const borderColor = ws.type === 'urgent' ? 'var(--color-danger)' : ws.type === 'active' ? 'var(--color-success)' : '#ced4da';
    return (
      <Card
        key={t.id}
        size="small"
        style={{ marginBottom: 12, borderLeft: `3px solid ${borderColor}` }}
        hoverable
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Tag color={ws.color === 'red' ? 'red' : ws.color === 'green' ? 'green' : 'default'}>{ws.label}</Tag>
          <span style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>{formatDate(t.warranty_end)}</span>
        </div>
        <div style={{ marginTop: 8, fontWeight: 500, cursor: 'pointer' }} onClick={() => navigate(`/transactions/${t.id}`)}>{t.product_name}</div>
        <div style={{ fontSize: 12, color: 'var(--color-text-secondary)', marginTop: 4 }}>
          {c?.xianyu_nickname || '-'} · {formatMoney(t.sale_price)}
        </div>
        <div style={{ fontSize: 12, color: 'var(--color-text-tertiary)', marginTop: 2 }}>
          起算：{getWarrantyStartLabel(t, formatDateTime)}
        </div>
        <Space size={4} style={{ marginTop: 8 }}>
          <Button size="small" type="link" icon={<PlusOutlined />} onClick={(e) => { e.stopPropagation(); setExtendModal({ open: true, tx: t }); }}>延长</Button>
          <Button size="small" type="link" onClick={(e) => { e.stopPropagation(); setEndModal({ open: true, tx: t }); }}>提前结束</Button>
          <Button size="small" type="link" icon={<ToolOutlined />} onClick={(e) => { e.stopPropagation(); setAftersalesModal({ open: true, tx: t }); }}>售后</Button>
        </Space>
      </Card>
    );
  };

  if (loading) return <div style={{ textAlign: 'center', padding: 80 }}><Spin size="large" /></div>;

  return (
    <Card
      title="质保监控（按发货时间起算）"
      extra={
        <Space>
          <Segmented value={view} onChange={(v) => setView(v as ViewType)} options={[{ label: '看板', value: 'board' }, { label: '列表', value: 'list' }, { label: '日历', value: 'calendar' }]} />
          <Button icon={<ExportOutlined />} onClick={handleExport}>导出</Button>
        </Space>
      }
    >
      {view !== 'calendar' && (
        <Tabs
          activeKey={filter}
          onChange={(k) => setFilter(k as FilterType)}
          items={[
            { key: 'all', label: `全部 (${all.length})` },
            { key: 'active', label: <span style={{ color: 'var(--color-success)' }}>质保中 ({active.length})</span> },
            { key: 'urgent', label: <span style={{ color: 'var(--color-danger)' }}>即将到期 ({urgent.length})</span> },
            { key: 'expired', label: <span style={{ color: 'var(--color-text-tertiary)' }}>已过期 ({expired.length})</span> },
          ]}
          style={{ marginBottom: 16 }}
        />
      )}

      {view === 'calendar' ? (
        <div>
          <div style={{ marginBottom: 12, fontSize: 12, color: 'var(--color-text-secondary)' }}>
            日历中标注质保到期日：质保从发货时间开始计算；红色=即将到期（3天内）、绿色=质保中、灰色=已过期。点击日期查看当日到期交易。
          </div>
          <Calendar
            cellRender={(date) => {
              const dayTrades = filtered.filter((t) => {
                if (!t.warranty_end) return false;
                return dayjs(t.warranty_end).isSame(date, 'day');
              });
              if (dayTrades.length === 0) return null;
              return (
                <div style={{ padding: '0 4px' }}>
                  {dayTrades.slice(0, 3).map((t) => {
                    const ws = getWarrantyStatus(t.warranty_end);
                    const badgeColor = ws.type === 'urgent' ? 'error' : ws.type === 'active' ? 'success' : 'default';
                    const c = customers.get(t.customer_id);
                    return (
                      <div
                        key={t.id}
                        style={{ cursor: 'pointer', marginBottom: 2 }}
                        onClick={() => navigate(`/transactions/${t.id}`)}
                        title={`${c?.xianyu_nickname || '-'} - ${t.product_name}`}
                      >
                        <Badge status={badgeColor as any} text={<span style={{ fontSize: 11 }}>{c?.xianyu_nickname || t.product_name}</span>} />
                      </div>
                    );
                  })}
                  {dayTrades.length > 3 && (
                    <div style={{ fontSize: 11, color: 'var(--color-text-tertiary)', paddingLeft: 4 }}>+{dayTrades.length - 3} 笔</div>
                  )}
                </div>
              );
            }}
          />
        </div>
      ) : view === 'board' ? (
        filter === 'all' ? (
          <Row gutter={[16, 16]}>
            <Col xs={24} lg={8}>
              <h3 style={{ color: 'var(--color-danger)', fontSize: 14, fontWeight: 600 }}>即将到期（3天内）{urgent.length > 0 && `(${urgent.length})`}</h3>
              {urgent.length === 0 ? <Empty description="暂无" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : urgent.map(renderCard)}
            </Col>
            <Col xs={24} lg={8}>
              <h3 style={{ color: 'var(--color-success)', fontSize: 14, fontWeight: 600 }}>质保中{active.length > 0 && `(${active.length})`}</h3>
              {active.length === 0 ? <Empty description="暂无" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : active.map(renderCard)}
            </Col>
            <Col xs={24} lg={8}>
              <h3 style={{ color: 'var(--color-text-tertiary)', fontSize: 14, fontWeight: 600 }}>已过期{expired.length > 0 && `(${expired.length})`}</h3>
              {expired.length === 0 ? <Empty description="暂无" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : expired.map(renderCard)}
            </Col>
          </Row>
        ) : (
          <Row gutter={[16, 16]}>
            <Col span={24}>
              {filtered.length === 0 ? <Empty description="暂无" image={Empty.PRESENTED_IMAGE_SIMPLE} /> : filtered.map(renderCard)}
            </Col>
          </Row>
        )
      ) : (
        <div>
          {filtered.map((t) => {
            const c = customers.get(t.customer_id);
            return (
              <div
                key={t.id}
                style={{ display: 'flex', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--color-border)', cursor: 'pointer' }}
                onClick={() => navigate(`/transactions/${t.id}`)}
              >
                <Space>
                  <WarrantyTag warrantyEnd={t.warranty_end} status={t.status} />
                  <span style={{ fontWeight: 500 }}>{t.product_name}</span>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{c?.xianyu_nickname}</span>
                </Space>
                <Space>
                  <span className="tabular-nums">{formatMoney(t.sale_price)}</span>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>起算 {getWarrantyStartLabel(t, formatDateTime)}</span>
                  <span style={{ color: 'var(--color-text-secondary)', fontSize: 12 }}>{formatDateTime(t.warranty_end)}</span>
                  <Button size="small" type="link" onClick={(e) => { e.stopPropagation(); setExtendModal({ open: true, tx: t }); }}>延长</Button>
                  <Button size="small" type="link" onClick={(e) => { e.stopPropagation(); setEndModal({ open: true, tx: t }); }}>提前结束</Button>
                  <Button size="small" type="link" onClick={(e) => { e.stopPropagation(); setAftersalesModal({ open: true, tx: t }); }}>售后</Button>
                </Space>
              </div>
            );
          })}
          {filtered.length === 0 && <Empty description="暂无质保数据" />}
        </div>
      )}

      <Modal
        title="延长质保"
        open={extendModal.open}
        onOk={handleExtendWarranty}
        onCancel={() => setExtendModal({ open: false })}
        okText="确认延长"
      >
        {extendModal.tx && (
          <div>
            <p>商品：{extendModal.tx.product_name}</p>
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>当前到期：{formatDateTime(extendModal.tx.warranty_end)}</p>
            <div style={{ marginTop: 12 }}>
              <span>延长天数：</span>
              <InputNumber min={1} max={365} value={extendDays} onChange={(v) => setExtendDays(v || 30)} style={{ width: 120 }} />
              <Space style={{ marginLeft: 8 }}>
                {[7, 30, 90, 180].map((d) => (
                  <Button key={d} size="small" onClick={() => setExtendDays(d)}>{d}天</Button>
                ))}
              </Space>
            </div>
          </div>
        )}
      </Modal>

      <Modal
        title="提前结束质保"
        open={endModal.open}
        onOk={handleEndWarranty}
        onCancel={() => { setEndModal({ open: false }); setEndReason(''); }}
        okText="确认结束"
        okButtonProps={{ danger: true }}
      >
        {endModal.tx && (
          <div>
            <p>商品：{endModal.tx.product_name}</p>
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>当前到期：{formatDateTime(endModal.tx.warranty_end)}</p>
            <p style={{ color: 'var(--color-danger)', fontSize: 13, marginTop: 8 }}>警告：提前结束后质保将立即失效，此操作不可撤销。</p>
            <Input.TextArea
              placeholder="请输入提前结束原因（可选）"
              value={endReason}
              onChange={(e) => setEndReason(e.target.value)}
              rows={3}
              style={{ marginTop: 8 }}
            />
          </div>
        )}
      </Modal>

      <Modal
        title="创建售后工单"
        open={aftersalesModal.open}
        onOk={handleCreateAftersales}
        onCancel={() => { setAftersalesModal({ open: false }); setAftersalesIssue(''); setAftersalesAttachments([]); }}
        okText="创建工单"
      >
        {aftersalesModal.tx && (
          <div>
            <p>商品：{aftersalesModal.tx.product_name}</p>
            <p style={{ fontSize: 12, color: 'var(--color-text-secondary)' }}>客户：{customers.get(aftersalesModal.tx.customer_id)?.xianyu_nickname || '-'}</p>
            <Input.TextArea
              placeholder="请描述售后问题..."
              value={aftersalesIssue}
              onChange={(e) => setAftersalesIssue(e.target.value)}
              rows={4}
              style={{ marginTop: 8 }}
            />
            <div style={{ marginTop: 12 }}>
              <div style={{ marginBottom: 4, fontSize: 13 }}>问题截图/附件</div>
              <AttachmentUpload value={aftersalesAttachments} onChange={setAftersalesAttachments} maxCount={6} />
            </div>
          </div>
        )}
      </Modal>
    </Card>
  );
}
