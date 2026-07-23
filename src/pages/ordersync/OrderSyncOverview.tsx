import { Button, Collapse, Typography } from 'antd';
import {
  CheckCircleOutlined,
  CloudSyncOutlined,
  LinkOutlined,
  ReloadOutlined,
  SafetyCertificateOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import type { CookieCloudConfigStatus, XianyuAccount } from '@/types';
import { getOrderSyncOverview } from './orderSyncViewModel';

const { Text } = Typography;

interface OrderSyncOverviewProps {
  accounts: XianyuAccount[];
  cookieCloudStatus: CookieCloudConfigStatus | null;
  onReloadCookieCloud: () => void;
}

interface SummaryItemProps {
  label: string;
  value: string | number;
  detail: string;
  tone?: 'default' | 'success' | 'warning' | 'danger';
}

function SummaryItem({ label, value, detail, tone = 'default' }: SummaryItemProps) {
  return (
    <div className={`order-sync-summary-item order-sync-summary-item--${tone}`}>
      <span className="order-sync-summary-label">{label}</span>
      <strong className="order-sync-summary-value">{value}</strong>
      <span className="order-sync-summary-detail">{detail}</span>
    </div>
  );
}

function SyncHelp() {
  return (
    <div className="order-sync-help">
      <p>
        添加闲鱼账号后，点击「同步订单」即可拉取成交订单并写入交易记录；点击「同步商品」会生成商品镜像。
        同步按订单号去重，可安全重复执行。
      </p>
      <p>
        <SafetyCertificateOutlined /> 自动同步最短 60 分钟一次。遇到登录失效或风控响应会立即熔断暂停，
        需更新 Cookie、通过校验后手动恢复。
      </p>
      <p>
        <LinkOutlined /> 获取 Cookie：在浏览器登录闲鱼（goofish.com）后，打开开发者工具 → Network → 任意请求 →
        复制完整 Cookie。
      </p>
      <Text type="secondary">
        需要把商品镜像导入为模板时，请前往「设置 / 商品模板 / 从闲鱼导入商品」。
      </Text>
    </div>
  );
}

export default function OrderSyncOverview({
  accounts,
  cookieCloudStatus,
  onReloadCookieCloud,
}: OrderSyncOverviewProps) {
  const summary = getOrderSyncOverview(accounts);
  const cookieCloudValue = cookieCloudStatus === null
    ? '状态未知'
    : cookieCloudStatus.enabled ? '已启用' : '未启用';

  return (
    <section aria-label="同步状态总览" className="order-sync-overview">
      <div className="order-sync-summary-grid">
        <SummaryItem label="全部账号" value={summary.total} detail="已接入闲鱼账号" />
        <SummaryItem
          label="待处理"
          value={summary.needsAttention}
          detail={summary.needsAttention > 0 ? '需要人工处理' : '账号状态正常'}
          tone={summary.needsAttention > 0 ? 'danger' : 'success'}
        />
        <SummaryItem label="自动同步" value={summary.autoSyncActive} detail="当前有效运行" />
        <SummaryItem
          label="CookieCloud"
          value={cookieCloudValue}
          detail="Cookie 自动续期"
          tone={cookieCloudStatus === null ? 'default' : cookieCloudStatus.enabled ? 'success' : 'warning'}
        />
      </div>

      {summary.pausedNames.length > 0 && (
        <div className="order-sync-task order-sync-task--danger">
          <div className="order-sync-task-icon"><WarningOutlined /></div>
          <div className="order-sync-task-content">
            <strong>{summary.pausedNames.length} 个账号需要处理</strong>
            <span className="order-sync-task-accounts">{summary.pausedNames.join('、')}</span>
            <div className="order-sync-recovery-steps" aria-label="账号恢复步骤">
              <span><b>1</b> 更新 Cookie</span>
              <i aria-hidden="true">→</i>
              <span><b>2</b> 校验</span>
              <i aria-hidden="true">→</i>
              <span><b>3</b> 恢复</span>
            </div>
          </div>
        </div>
      )}

      {cookieCloudStatus && !cookieCloudStatus.enabled && (
        <div className="order-sync-task order-sync-task--warning">
          <div className="order-sync-task-icon"><CloudSyncOutlined /></div>
          <div className="order-sync-task-content">
            <strong>CookieCloud 未启用</strong>
            <span>{cookieCloudStatus.message}</span>
            <Text type="secondary" className="order-sync-task-detail">
              {cookieCloudStatus.next_step}
              {cookieCloudStatus.missing_keys.length > 0
                ? ` 缺少：${cookieCloudStatus.missing_keys.join('、')}`
                : ''}
            </Text>
          </div>
          <Button
            aria-label="重新检测 CookieCloud"
            size="small"
            icon={<ReloadOutlined />}
            onClick={onReloadCookieCloud}
          >
            重新检测
          </Button>
        </div>
      )}

      {cookieCloudStatus?.enabled && (
        <div className="order-sync-service-ok">
          <CheckCircleOutlined /> Cookie 过期后将尝试通过 CookieCloud 自动续期
        </div>
      )}

      <Collapse
        className="order-sync-help-collapse"
        ghost
        items={[{
          key: 'help',
          label: '同步说明与 Cookie 获取方法',
          children: <SyncHelp />,
        }]}
      />
    </section>
  );
}
