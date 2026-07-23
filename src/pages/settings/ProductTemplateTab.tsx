import { useEffect, useState } from 'react';
import {
  Alert,
  Button,
  Col,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Segmented,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  CloudDownloadOutlined,
  CloudUploadOutlined,
  DeleteOutlined,
  EditOutlined,
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { listTemplates, createTemplate, updateTemplate, deleteTemplate } from '@/services/productTemplateService';
import { getErrorMessage, isValidationError } from '@/utils/error';
import {
  filterXianyuItemsByTemplateProjection,
  importXianyuItemsAsTemplates,
  listAccounts as listXianyuAccounts,
  listItems as listXianyuItems,
  syncItems as syncXianyuItems,
} from '@/services/xianyuService';
import type { XianyuItemTemplateProjectionFilter } from '@/services/xianyuService';
import { getWarrantyDaysLabel } from '@/utils/warranty';
import ProductImage from '@/components/ProductImage';
import dayjs from 'dayjs';
import type { ProductTemplate, XianyuAccount, XianyuItem } from '@/types';

const { Text } = Typography;

interface ProductTemplateTabProps {
  /** 新增模板时的默认质保天数（从容器 settings.warranty_days 传入）。
   * 容器在初始 effect 中加载 settings，Tab 激活时通常已加载完成。
   */
  defaultWarrantyDays: number;
}

/** 商品模板 Tab：模板列表 + 新增/编辑模板 Modal + 从闲鱼导入 Modal。
 *
 * 状态自包含：templates / tplForm / xianyu 相关 state 全部下沉。
 * mount effect 加载 templates + xianyuAccounts（从容器初始 Promise.all 下沉）。
 *
 * 两个 Modal 的 state 与 Tab 紧耦合（工具栏按钮触发），内联在此文件中
 * 而非独立文件——拆成独立文件需传 15+ props，反而增加复杂度。
 */
export default function ProductTemplateTab({ defaultWarrantyDays }: ProductTemplateTabProps) {
  const [templates, setTemplates] = useState<ProductTemplate[]>([]);
  const [tplModalOpen, setTplModalOpen] = useState(false);
  const [editingTpl, setEditingTpl] = useState<ProductTemplate | null>(null);
  const [xianyuImportOpen, setXianyuImportOpen] = useState(false);
  const [xianyuAccounts, setXianyuAccounts] = useState<XianyuAccount[]>([]);
  const [templateSourceFilter, setTemplateSourceFilter] = useState<string | number>('all');
  const [xianyuImportAccountId, setXianyuImportAccountId] = useState<number | undefined>(undefined);
  const [xianyuItems, setXianyuItems] = useState<XianyuItem[]>([]);
  const [xianyuItemImportFilter, setXianyuItemImportFilter] = useState<XianyuItemTemplateProjectionFilter>('unimported');
  const [selectedXianyuItemIds, setSelectedXianyuItemIds] = useState<number[]>([]);
  const [xianyuItemsLoading, setXianyuItemsLoading] = useState(false);
  const [xianyuImporting, setXianyuImporting] = useState(false);
  const [xianyuImportDefaultCost, setXianyuImportDefaultCost] = useState(0);
  const [xianyuImportWarrantyDays, setXianyuImportWarrantyDays] = useState(defaultWarrantyDays);
  const [tplForm] = Form.useForm();

  const loadTemplates = async () => {
    setTemplates(await listTemplates());
  };

  const loadXianyuAccountOptions = async () => {
    try {
      setXianyuAccounts(await listXianyuAccounts());
    } catch {
      // 设置页仍可管理普通模板；账号信息只用于闲鱼来源展示和筛选。
    }
  };

  useEffect(() => {
    Promise.all([loadTemplates(), loadXianyuAccountOptions()]);
  }, []);

  const openXianyuImport = async () => {
    setXianyuImportOpen(true);
    setSelectedXianyuItemIds([]);
    setXianyuItemImportFilter('unimported');
    setXianyuImportDefaultCost(0);
    setXianyuImportWarrantyDays(defaultWarrantyDays);
    setXianyuItems([]);
    try {
      const accounts = await listXianyuAccounts();
      setXianyuAccounts(accounts);
      const firstId = accounts[0]?.id;
      setXianyuImportAccountId(firstId);
      if (firstId) {
        setXianyuItemsLoading(true);
        setXianyuItems(await listXianyuItems(firstId));
      }
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载闲鱼账号失败');
    } finally {
      setXianyuItemsLoading(false);
    }
  };

  const loadXianyuItems = async (accountId = xianyuImportAccountId) => {
    if (!accountId) return;
    setXianyuItemsLoading(true);
    setSelectedXianyuItemIds([]);
    try {
      setXianyuItems(await listXianyuItems(accountId));
    } catch (err) {
      message.error(err instanceof Error ? err.message : '加载闲鱼商品失败');
    } finally {
      setXianyuItemsLoading(false);
    }
  };

  const handleSyncXianyuItems = async () => {
    if (!xianyuImportAccountId) {
      message.warning('请先选择闲鱼账号');
      return;
    }
    setXianyuItemsLoading(true);
    setSelectedXianyuItemIds([]);
    try {
      const result = await syncXianyuItems(xianyuImportAccountId);
      if (result.success) {
        message.success(`拉取完成：拉取 ${result.fetched} 个商品，更新 ${result.upserted_count} 个镜像`);
      } else {
        message.warning(`拉取未完成：${result.error || '未知原因'}`);
      }
      setXianyuItems(await listXianyuItems(xianyuImportAccountId));
    } catch (err) {
      message.error(err instanceof Error ? err.message : '拉取闲鱼商品失败');
    } finally {
      setXianyuItemsLoading(false);
    }
  };

  const handleImportXianyuItems = async () => {
    if (!xianyuImportAccountId || selectedXianyuItemIds.length === 0) {
      message.warning('请先选择要导入的商品');
      return;
    }
    if (xianyuImportDefaultCost < 0 || xianyuImportWarrantyDays < 0) {
      message.warning('请填写有效的默认成本和质保天数');
      return;
    }
    setXianyuImporting(true);
    try {
      const result = await importXianyuItemsAsTemplates(
        xianyuImportAccountId,
        selectedXianyuItemIds,
        {
          default_cost: xianyuImportDefaultCost,
          warranty_days: xianyuImportWarrantyDays,
        },
      );
      message.success(`导入完成：新增 ${result.created_count} 个模板，跳过 ${result.skipped_count} 个`);
      setSelectedXianyuItemIds([]);
      await Promise.all([loadTemplates(), loadXianyuItems(xianyuImportAccountId)]);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '导入商品模板失败');
    } finally {
      setXianyuImporting(false);
    }
  };

  const handleSaveTpl = async () => {
    try {
      const values = await tplForm.validateFields();
      if (editingTpl) {
        await updateTemplate(editingTpl.id!, values);
        message.success('模板已更新');
      } else {
        await createTemplate(values);
        message.success('模板已创建');
      }
      setTplModalOpen(false);
      setEditingTpl(null);
      tplForm.resetFields();
      loadTemplates();
    } catch (err: unknown) {
      if (isValidationError(err)) return;
      console.error('保存模板失败:', err);
      message.error(getErrorMessage(err, '保存失败'));
    }
  };

  const handleDeleteTpl = async (id: number) => {
    try {
      await deleteTemplate(id);
      message.success('已删除');
      loadTemplates();
    } catch (err) {
      console.error('删除模板失败:', err);
      message.error(err instanceof Error ? err.message : '删除失败');
    }
  };

  const xianyuAccountNameById = new Map(
    xianyuAccounts.map((account) => [account.id, account.nickname || account.unb || `账号 ${account.id}`]),
  );

  const tplColumns = [
    {
      title: '图片',
      dataIndex: 'image_url',
      width: 70,
      render: (v?: string) => <ProductImage url={v} size={44} />,
    },
    { title: '商品名称', dataIndex: 'name', ellipsis: true },
    { title: '默认成本', dataIndex: 'default_cost', width: 100, render: (v: number) => `¥${v}` },
    { title: '建议售价', dataIndex: 'default_sale_price', width: 100, render: (v?: number) => (v ? `¥${v}` : '-') },
    { title: '分类', dataIndex: 'category', width: 100, render: (v?: string) => v || '-' },
    {
      title: '来源账号',
      dataIndex: 'source_xianyu_account_id',
      width: 130,
      filters: xianyuAccounts.map((account) => ({
        text: account.nickname || account.unb || `账号 ${account.id}`,
        value: account.id,
      })),
      onFilter: (value: any, record: ProductTemplate) => record.source_xianyu_account_id === Number(value),
      render: (v?: number) => {
        if (!v) return <Tag>手动</Tag>;
        return <Tag color="blue">{xianyuAccountNameById.get(v) || `账号 ${v}`}</Tag>;
      },
    },
    { title: '质保天数', dataIndex: 'warranty_days', width: 90, align: 'center' as const, render: (v: number) => getWarrantyDaysLabel(v) },
    {
      title: '启用',
      dataIndex: 'is_active',
      width: 70,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '是' : '否'}</Tag>,
    },
    {
      title: '操作',
      width: 120,
      render: (_: unknown, r: ProductTemplate) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => { setEditingTpl(r); tplForm.setFieldsValue(r); setTplModalOpen(true); }} />
          <Popconfirm title="确认删除？" onConfirm={() => handleDeleteTpl(r.id!)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const xianyuItemColumns = [
    {
      title: '商品',
      dataIndex: 'title',
      ellipsis: true,
      render: (v?: string, record?: XianyuItem) => (
        <Space>
          <ProductImage url={record?.image_url} size={32} />
          <span>{v || '-'}</span>
        </Space>
      ),
    },
    { title: '售价', dataIndex: 'price', width: 90, align: 'right' as const, render: (v: number) => `¥${Number(v || 0).toFixed(2)}` },
    { title: '状态', dataIndex: 'item_status', width: 100, render: (v?: string) => v ? <Tag>{v}</Tag> : '-' },
    {
      title: '导入',
      dataIndex: 'projected_template_id',
      width: 100,
      render: (v?: number) => v ? <Tag color="green">已导入</Tag> : <Tag>未导入</Tag>,
    },
    { title: '闲鱼商品ID', dataIndex: 'item_id', width: 150, render: (v: string) => <Text style={{ fontSize: 12 }}>{v}</Text> },
    {
      title: '最近拉取',
      dataIndex: 'last_seen_at',
      width: 150,
      render: (v: Date) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
  ];

  const emptyText = <Empty description="暂无模板" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  const filteredXianyuItems = filterXianyuItemsByTemplateProjection(xianyuItems, xianyuItemImportFilter);
  const filteredTemplates = templates.filter((tpl) => {
    if (templateSourceFilter === 'all') return true;
    if (templateSourceFilter === 'manual') return !tpl.source_xianyu_account_id;
    return tpl.source_xianyu_account_id === Number(templateSourceFilter);
  });
  const importedTemplateCount = templates.filter((tpl) => Boolean(tpl.source_xianyu_account_id)).length;

  return (
    <>
      <Space style={{ marginBottom: 16 }} wrap>
        <Button
          type="primary"
          icon={<PlusOutlined />}
          onClick={() => {
            setEditingTpl(null);
            tplForm.resetFields();
            tplForm.setFieldsValue({ is_active: true, warranty_days: defaultWarrantyDays });
            setTplModalOpen(true);
          }}
        >
          新增模板
        </Button>
        <Button icon={<CloudDownloadOutlined />} onClick={openXianyuImport}>
          从闲鱼导入
        </Button>
        <Select
          style={{ width: 220 }}
          value={templateSourceFilter}
          onChange={setTemplateSourceFilter}
          options={[
            { label: `全部模板（${templates.length}）`, value: 'all' },
            { label: `手动模板（${templates.length - importedTemplateCount}）`, value: 'manual' },
            ...xianyuAccounts.map((account) => ({
              label: `${account.nickname || account.unb || `账号 ${account.id}`}（${templates.filter((tpl) => tpl.source_xianyu_account_id === account.id).length}）`,
              value: account.id,
            })),
          ]}
        />
      </Space>
      <Table
        rowKey="id"
        dataSource={filteredTemplates}
        columns={tplColumns}
        size="middle"
        pagination={{ pageSize: 20 }}
        locale={{ emptyText }}
        scroll={{ x: 980 }}
      />

      {/* 从闲鱼导入商品 Modal */}
      <Modal
        title="从闲鱼导入商品"
        open={xianyuImportOpen}
        onCancel={() => setXianyuImportOpen(false)}
        footer={[
          <Button key="cancel" onClick={() => setXianyuImportOpen(false)}>关闭</Button>,
          <Button key="sync" icon={<ReloadOutlined />} loading={xianyuItemsLoading} onClick={handleSyncXianyuItems}>
            拉取闲鱼商品
          </Button>,
          <Button
            key="import"
            type="primary"
            icon={<CloudUploadOutlined />}
            loading={xianyuImporting}
            disabled={selectedXianyuItemIds.length === 0}
            onClick={handleImportXianyuItems}
          >
            导入选中（{selectedXianyuItemIds.length}）
          </Button>,
        ]}
        width={920}
      >
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 12 }}
          message="商品按闲鱼账号隔离"
          description="先选择账号并拉取商品镜像，再勾选要导入的商品模板。导入会保留来源账号和闲鱼商品 ID，不会跨账号去重或覆盖。"
        />
        <Space style={{ marginBottom: 12 }} wrap>
          <Select
            style={{ width: 240 }}
            placeholder="选择闲鱼账号"
            value={xianyuImportAccountId}
            onChange={(value) => {
              setXianyuImportAccountId(value);
              loadXianyuItems(value);
            }}
            options={xianyuAccounts.map((account) => ({
              value: account.id,
              label: `${account.nickname}${account.unb ? `（${account.unb}）` : ''}`,
            }))}
          />
          <Button icon={<ReloadOutlined />} onClick={() => loadXianyuItems()} disabled={!xianyuImportAccountId}>
            刷新镜像
          </Button>
          <InputNumber
            min={0}
            precision={2}
            prefix="¥"
            addonBefore="默认成本"
            value={xianyuImportDefaultCost}
            onChange={(value) => setXianyuImportDefaultCost(Number(value ?? 0))}
            style={{ width: 170 }}
          />
          <InputNumber
            min={0}
            max={3650}
            addonBefore="质保天数"
            title="填 0 表示导入模板默认不质保"
            value={xianyuImportWarrantyDays}
            onChange={(value) => setXianyuImportWarrantyDays(Number(value ?? 0))}
            style={{ width: 170 }}
          />
          <Segmented
            size="small"
            value={xianyuItemImportFilter}
            onChange={(value) => {
              setXianyuItemImportFilter(value as XianyuItemTemplateProjectionFilter);
              setSelectedXianyuItemIds([]);
            }}
            options={[
              { label: '未导入', value: 'unimported' },
              { label: '已导入', value: 'imported' },
              { label: '全部', value: 'all' },
            ]}
          />
        </Space>
        <Table
          rowKey="id"
          size="small"
          loading={xianyuItemsLoading}
          dataSource={filteredXianyuItems}
          columns={xianyuItemColumns}
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: <Empty description="暂无闲鱼商品镜像，请先点击「拉取闲鱼商品」" image={Empty.PRESENTED_IMAGE_SIMPLE} /> }}
          rowSelection={{
            selectedRowKeys: selectedXianyuItemIds,
            onChange: (keys) => setSelectedXianyuItemIds(keys.map((key) => Number(key))),
            getCheckboxProps: (record: XianyuItem) => ({
              disabled: Boolean(record.projected_template_id),
            }),
          }}
        />
      </Modal>

      {/* 新增/编辑模板 Modal */}
      <Modal
        title={editingTpl ? '编辑模板' : '新增模板'}
        open={tplModalOpen}
        onCancel={() => { setTplModalOpen(false); setEditingTpl(null); tplForm.resetFields(); }}
        onOk={handleSaveTpl}
        okText="保存"
      >
        <Form form={tplForm} layout="vertical">
          <Form.Item name="name" label="商品名称" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="如：软件激活码（年卡）" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="default_cost" label="默认成本价" rules={[{ required: true }]}>
                <InputNumber min={0} precision={2} prefix="¥" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="default_sale_price" label="建议售价（选填）">
                <InputNumber min={0} precision={2} prefix="¥" style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="category" label="分类（选填）">
                <Input placeholder="如：激活码" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="warranty_days" label="默认质保天数" tooltip="填 0 表示使用该模板创建订单时默认不质保" rules={[{ required: true }]}>
                <InputNumber min={0} max={3650} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
}
