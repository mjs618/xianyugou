import Dexie from 'dexie';
import type {
  Customer,
  Transaction,
  CustomerLink,
  AfterSales,
  RebateRecord,
  ProductTemplate,
  WarrantyExtension,
  NotificationRecord,
  CustomerTag,
  CustomerTagRelation,
  Settings,
  Attachment,
  MailRecord,
  OperationLog,
} from '@/types';

// Dexie 数据库定义
export class XianyuDB extends Dexie {
  customers!: Dexie.Table<Customer, number>;
  transactions!: Dexie.Table<Transaction, number>;
  customerLinks!: Dexie.Table<CustomerLink, number>;
  afterSales!: Dexie.Table<AfterSales, number>;
  rebateRecords!: Dexie.Table<RebateRecord, number>;
  productTemplates!: Dexie.Table<ProductTemplate, number>;
  warrantyExtensions!: Dexie.Table<WarrantyExtension, number>;
  notificationRecords!: Dexie.Table<NotificationRecord, number>;
  customerTags!: Dexie.Table<CustomerTag, number>;
  customerTagRelations!: Dexie.Table<CustomerTagRelation, number>;
  attachments!: Dexie.Table<Attachment, number>;
  mailRecords!: Dexie.Table<MailRecord, number>;
  operationLogs!: Dexie.Table<OperationLog, number>;
  settings!: Dexie.Table<Settings, number>;

  constructor() {
    super('XianyuAccountingDB');
    this.version(1).stores({
      customers: '++id, xianyu_nickname, level, is_blacklist, total_spent, deleted_at',
      transactions:
        '++id, customer_id, trade_at, status, warranty_end, source_customer_id, xianyu_order_no, deleted_at, [status+warranty_end]',
      customerLinks: '++id, referrer_id, buyer_id, [referrer_id+buyer_id]',
      afterSales: '++id, transaction_id, status, created_at',
      rebateRecords: '++id, referrer_id, status',
      productTemplates: '++id, name, is_active, category',
      warrantyExtensions: '++id, transaction_id',
      notificationRecords: '++id, type, status, scheduled_at, ref_id',
      customerTags: '++id, &name',
      customerTagRelations: '++id, customer_id, tag_id, [customer_id+tag_id]',
      settings: '++id',
    });
    this.version(2).stores({
      rebateRecords: '++id, referrer_id, transaction_id, status, created_at',
      notificationRecords: '++id, type, status, scheduled_at, ref_id, created_at',
    });
    this.version(3).stores({
      attachments: '++id, created_at',
    });
    this.version(4).stores({
      mailRecords: '++id, to, status, sent_at',
    });
    this.version(5).stores({
      operationLogs: '++id, module, action, target_id, created_at',
    });
    // P1 索引补全：customerLinks 加 buyer_id 单字段索引（calcReferralLevel/wouldCreateCycle 用）
    // P0-4 级联策略：afterSales 加 deleted_at 索引（软删除工单过滤）
    this.version(6).stores({
      customerLinks: '++id, referrer_id, buyer_id, [referrer_id+buyer_id]',
      afterSales: '++id, transaction_id, status, created_at, deleted_at',
    });
  }
}

export const db = new XianyuDB();
