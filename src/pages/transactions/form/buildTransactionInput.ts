import dayjs from 'dayjs';
import type { FormInstance } from 'antd';
import { createCustomer, findByNickname } from '@/services/customerService';
import type { ChannelType, SourceType, TransactionInput, TransactionStatus } from '@/types';

interface BuildInputParams {
  form: FormInstance;
  customerId: number;
  fallbackTradeAt: dayjs.Dayjs;
  fallbackShippedAt: dayjs.Dayjs;
  fallbackStatus: TransactionStatus;
  fallbackSourceType: SourceType;
  fallbackChannel: ChannelType;
  fallbackWarrantyDays: number;
}

/** 从 Form 实例 + fallback state 构造 TransactionInput。
 *
 * handleSubmit 与 handleSaveAndContinue 共用此逻辑，避免重复。
 */
export function buildTransactionInput({
  form,
  customerId,
  fallbackTradeAt,
  fallbackShippedAt,
  fallbackStatus,
  fallbackSourceType,
  fallbackChannel,
  fallbackWarrantyDays,
}: BuildInputParams): TransactionInput {
  const values = form.getFieldsValue();
  const status: TransactionStatus = values.status || fallbackStatus;
  const tradeAt = values.trade_at || fallbackTradeAt;
  const shippedAt = values.shipped_at || fallbackShippedAt || values.trade_at || fallbackTradeAt;

  return {
    customer_id: customerId,
    xianyu_order_no: values.xianyu_order_no,
    product_name: values.product_name,
    product_template_id: values.product_template_id,
    sale_price: Number(values.sale_price),
    cost_price: Number(values.cost_price),
    trade_at: tradeAt.toDate(),
    shipped_at: status === 'completed' ? shippedAt.toDate() : undefined,
    status,
    warranty_days: values.has_warranty === false ? 0 : Number(values.warranty_days ?? fallbackWarrantyDays),
    source_type: values.source_type || fallbackSourceType,
    channel: values.channel || fallbackChannel,
    source_customer_id: values.source_customer_id,
    notes: values.notes,
    attachments: values.attachments || [],
  };
}

interface ResolveCustomerIdResult {
  customerId: number | null;
  message?: 'info' | 'error' | 'warning';
  messageText?: string;
}

/** 处理 isNewCustomer 分支：检查昵称非空，已存在则复用，否则新建。
 *
 * 返回 customerId；若校验失败返回 null。
 */
export async function resolveCustomerId(
  values: { contact_info?: string },
  isNewCustomer: boolean,
  newNickname: string,
  existingCustomerId?: number,
): Promise<ResolveCustomerIdResult> {
  if (!isNewCustomer) {
    if (!existingCustomerId) {
      return { customerId: null, message: 'error', messageText: '请选择客户' };
    }
    return { customerId: existingCustomerId };
  }

  if (!newNickname.trim()) {
    return { customerId: null, message: 'error', messageText: '请输入客户昵称' };
  }
  const existing = await findByNickname(newNickname);
  if (existing) {
    return {
      customerId: existing.id!,
      message: 'info',
      messageText: `客户「${existing.xianyu_nickname}」已存在，已自动关联`,
    };
  }
  const created = await createCustomer({ xianyu_nickname: newNickname, contact_info: values.contact_info });
  return { customerId: created.id! };
}
