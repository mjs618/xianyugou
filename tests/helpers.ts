import { db } from '@/db';

// 每个测试前清空所有表
export async function resetDB(): Promise<void> {
  await db.transaction(
    'rw',
    [
      db.customers,
      db.transactions,
      db.customerLinks,
      db.afterSales,
      db.rebateRecords,
      db.productTemplates,
      db.warrantyExtensions,
      db.notificationRecords,
      db.customerTags,
      db.customerTagRelations,
      db.settings,
      db.mailRecords,
      db.operationLogs,
    ],
    async () => {
      await Promise.all([
        db.customers.clear(),
        db.transactions.clear(),
        db.customerLinks.clear(),
        db.afterSales.clear(),
        db.rebateRecords.clear(),
        db.productTemplates.clear(),
        db.warrantyExtensions.clear(),
        db.notificationRecords.clear(),
        db.customerTags.clear(),
        db.customerTagRelations.clear(),
        db.settings.clear(),
        db.mailRecords.clear(),
        db.operationLogs.clear(),
      ]);
    }
  );
}
