// 邮件发送服务 - 调用本地 mail-server(:3001) 发送邮件，记录走后端 API
import { getSettings } from './settingsService';
import { addMailRecord } from './mailRecordService';
import { listMailRecords } from './mailRecordService';

// 本地邮件服务地址
const BUILD_MAIL_SERVER = import.meta.env.VITE_MAIL_SERVER_URL?.trim();
const MAIL_SERVER = (BUILD_MAIL_SERVER || 'http://localhost:13001').replace(/\/+$/, '');

// 连续失败告警阈值
const MAIL_ALERT_THRESHOLD = 3;

// 发货信息（GPT 账号商品）
export interface DeliveryInfo {
  email_account: string; // 邮箱账号（GPT 登录账号）
  gpt_password: string; // GPT 密码
  token_url: string; // 动态令牌网址
  email_password: string; // 邮箱密码
}

export interface SendMailParams {
  to: string; // 收件人邮箱
  customerName?: string; // 客户昵称
  delivery: DeliveryInfo; // 发货信息
}

export interface MailResult {
  success: boolean;
  messageId?: string;
  error?: string;
}

// 检查本地邮件服务是否在线
export async function checkMailServer(): Promise<boolean> {
  try {
    const res = await fetch(`${MAIL_SERVER}/api/health`, { method: 'GET' });
    return res.ok;
  } catch {
    return false;
  }
}

// 转义 HTML 特殊字符，防止注入
function escapeHtml(str: string): string {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// 解析粘贴的发货文本，自动提取发货信息字段
// 支持格式：
// 1. 分隔符单行：邮箱----GPT密码----URL----邮箱密码
// 2. 四行纯值：按顺序为 邮箱账号 / GPT密码 / 动态令牌网址 / 邮箱密码
// 3. 字段名格式：邮箱账号：xxx / GPT 密码：xxx / ...
export function parseDeliveryText(text: string): Partial<DeliveryInfo> {
  const result: Partial<DeliveryInfo> = {};
  const normalized = text.replace(/\r\n/g, '\n').trim();
  if (!normalized) return result;

  const emailRegex = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/;
  const urlRegex = /https?:\/\/[^\s，。、；）)]+/;

  // 1. 尝试分隔符格式（----、--、|、｜、制表符等）
  const separatorPattern = /[-]{2,}|[|｜\t]+/;
  const parts = normalized
    .split(separatorPattern)
    .map((p) => p.trim())
    .filter(Boolean);
  if (parts.length >= 4) {
    result.email_account = parts[0];
    result.gpt_password = parts[1];
    result.token_url = parts[2];
    result.email_password = parts[3];
    return result;
  }

  const lines = normalized.split('\n').map((l) => l.trim()).filter(Boolean);

  // 2. 尝试 "字段名：值" 或 "字段名:值" 格式
  for (const line of lines) {
    const m = line.match(/^(.+?)[：:]\s*(.+)$/);
    if (!m) continue;
    const key = m[1].trim().toLowerCase();
    const value = m[2].trim();
    if ((key.includes('邮箱账号') || key === '账号') && !result.email_account) {
      result.email_account = value;
    } else if ((key.includes('gpt') && key.includes('密码')) && !result.gpt_password) {
      result.gpt_password = value;
    } else if ((key.includes('令牌') || key.includes('2fa') || key.includes('网址') || key.includes('链接') || key.includes('url')) && !result.token_url) {
      result.token_url = value;
    } else if (key.includes('邮箱密码') && !result.email_password) {
      result.email_password = value;
    } else if (key.includes('密码') && !key.includes('邮箱') && !result.gpt_password) {
      // 兜底：单独的"密码"归为 GPT 密码
      result.gpt_password = value;
    }
  }

  // 3. 兜底：四行纯值按顺序识别
  const hasFieldName = lines.some((l) => /^(.+?)[：:]\s*(.+)$/.test(l));
  if (!hasFieldName && lines.length >= 2) {
    const order: (keyof DeliveryInfo)[] = ['email_account', 'gpt_password', 'token_url', 'email_password'];
    for (let i = 0; i < Math.min(lines.length, 4); i++) {
      const key = order[i];
      if (result[key]) continue;
      const line = lines[i];
      if (key === 'email_account') {
        const em = line.match(emailRegex);
        result.email_account = em ? em[0] : line;
      } else if (key === 'token_url') {
        const um = line.match(urlRegex);
        result.token_url = um ? um[0] : line;
      } else {
        result[key] = line;
      }
    }
  }

  return result;
}

// 根据发货信息生成邮件正文（HTML）- 使用教程文档格式
export function buildDeliveryMail(delivery: DeliveryInfo, customerName?: string): {
  subject: string;
  html: string;
  text: string;
} {
  const e = escapeHtml;
  const name = customerName ? e(customerName) : '客户';
  const account = e(delivery.email_account);
  const gptPwd = e(delivery.gpt_password);
  const tokenUrl = e(delivery.token_url);
  const mailPwd = e(delivery.email_password);

  const subject = '您的商品发货信息及使用教程';

  const html = `
<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Microsoft YaHei',sans-serif;max-width:680px;margin:0 auto;color:#333;line-height:1.7;">
  <p>尊敬的 ${name}，您好：</p>
  <p>感谢您的购买！以下是您的商品信息及详细使用教程，请妥善保管。</p>

  <h3 style="color:#1971c2;border-left:4px solid #1971c2;padding-left:10px;margin-top:24px;">一、发货信息</h3>
  <table style="width:100%;border-collapse:collapse;font-size:14px;">
    <tr><td style="padding:8px 12px;border:1px solid #e9ecef;background:#f8f9fa;width:160px;font-weight:600;">邮箱账号</td><td style="padding:8px 12px;border:1px solid #e9ecef;">${account}</td></tr>
    <tr><td style="padding:8px 12px;border:1px solid #e9ecef;background:#f8f9fa;font-weight:600;">GPT 密码</td><td style="padding:8px 12px;border:1px solid #e9ecef;">${gptPwd}</td></tr>
    <tr><td style="padding:8px 12px;border:1px solid #e9ecef;background:#f8f9fa;font-weight:600;">动态令牌网址</td><td style="padding:8px 12px;border:1px solid #e9ecef;">${tokenUrl}</td></tr>
    <tr><td style="padding:8px 12px;border:1px solid #e9ecef;background:#f8f9fa;font-weight:600;">邮箱密码</td><td style="padding:8px 12px;border:1px solid #e9ecef;">${mailPwd}</td></tr>
  </table>
  <p style="font-size:12px;color:#868e96;margin-top:6px;">说明：邮箱账号即为 GPT 登录所使用的账号。</p>

  <h3 style="color:#1971c2;border-left:4px solid #1971c2;padding-left:10px;margin-top:24px;">二、登录前准备</h3>
  <ol style="padding-left:22px;">
    <li>准备稳定、可用的网络环境。</li>
    <li>打开 Outlook 中文登录页：<a href="https://www.microsoft.com/zh-cn/microsoft-365/outlook/log-in">https://www.microsoft.com/zh-cn/microsoft-365/outlook/log-in</a></li>
    <li>准备好收到的邮箱账号、邮箱密码、GPT 密码和动态令牌信息。</li>
  </ol>

  <h3 style="color:#1971c2;border-left:4px solid #1971c2;padding-left:10px;margin-top:24px;">三、登录邮箱并查看验证码</h3>
  <ol style="padding-left:22px;">
    <li>在 Outlook 登录页输入邮箱账号。</li>
    <li>按页面提示输入邮箱密码，完成邮箱登录。</li>
    <li>同时打开 GPT 登录页，输入同一个邮箱账号和 GPT 密码。</li>
    <li>第一次登录时，系统可能会向邮箱发送验证码。回到 Outlook 收件箱，找到验证码邮件。</li>
    <li>将邮箱验证码填入 GPT 登录页面。</li>
  </ol>

  <h3 style="color:#1971c2;border-left:4px solid #1971c2;padding-left:10px;margin-top:24px;">四、使用动态密码器</h3>
  <p>如果输入邮箱验证码后，页面继续提示输入验证器或动态验证码，请使用动态令牌获取验证码。</p>
  <ol style="padding-left:22px;">
    <li>完整动态令牌网址格式：https://2fa.run/&lt;动态令牌提取码&gt;</li>
    <li>也可以只复制最后一个 / 后面的提取码，在支持 TOTP 的软件或网页中生成动态验证码。</li>
    <li>请完整复制提取码，不要漏掉任何字符。复制不完整会导致无法打开网页或无法生成验证码。</li>
    <li>如果 2fa.run 访问过多或出现 404，可使用备用地址：https://2fa.cn/ ，然后粘贴提取码生成验证码。</li>
  </ol>

  <h3 style="color:#1971c2;border-left:4px solid #1971c2;padding-left:10px;margin-top:24px;">五、绑定辅助邮箱</h3>
  <p>如果页面提示绑定辅助邮箱，请输入您自己常用且可长期使用的邮箱作为辅助邮箱。绑定后请保存好该辅助邮箱信息，以便后续找回或验证。</p>

  <h3 style="color:#1971c2;border-left:4px solid #1971c2;padding-left:10px;margin-top:24px;">六、常见问题</h3>
  <ul style="padding-left:22px;">
    <li><b>提示无法登录：</b>通常与当前网络环境或 IP 质量有关。请更换稳定、干净的网络节点后重新登录。</li>
    <li><b>提示所在国家或地区不可用：</b>通常是网络节点不稳定、频繁变化或被识别为不可用区域。请更换稳定网络后重试。</li>
    <li><b>提示账号或密码不正确，或尝试次数过多：</b>不一定代表账号密码错误，也可能是当前 IP 被 Microsoft 风控。请更换 IP，重新打开浏览器后再试。</li>
    <li><b>动态令牌网页打不开或显示 404：</b>检查提取码是否复制完整；如仍无法打开，改用 https://2fa.cn/ 并粘贴提取码。</li>
  </ul>

  <div style="margin-top:24px;padding:12px 16px;background:#fff9db;border-radius:6px;font-size:13px;color:#866a04;">
    <b>安全提示：</b>请妥善保管邮箱账号、GPT 密码、邮箱密码和动态令牌。不要把密码、动态令牌提取码或验证码发送给无关人员。
  </div>

  <p style="margin-top:24px;color:#868e96;font-size:12px;border-top:1px solid #e9ecef;padding-top:12px;">如有疑问，请随时联系我们。祝您使用愉快！</p>
</div>`.trim();

  const text = `尊敬的 ${name}，您好：

感谢您的购买！以下是您的商品信息及详细使用教程，请妥善保管。

【发货信息】
邮箱账号：${delivery.email_account}
GPT 密码：${delivery.gpt_password}
动态令牌网址：${delivery.token_url}
邮箱密码：${delivery.email_password}
说明：邮箱账号即为 GPT 登录所使用的账号。

【一、登录前准备】
1. 准备稳定、可用的网络环境。
2. 打开 Outlook 中文登录页：https://www.microsoft.com/zh-cn/microsoft-365/outlook/log-in
3. 准备好收到的邮箱账号、邮箱密码、GPT 密码和动态令牌信息。

【二、登录邮箱并查看验证码】
1. 在 Outlook 登录页输入邮箱账号。
2. 按页面提示输入邮箱密码，完成邮箱登录。
3. 同时打开 GPT 登录页，输入同一个邮箱账号和 GPT 密码。
4. 第一次登录时，系统可能会向邮箱发送验证码。回到 Outlook 收件箱，找到验证码邮件。
5. 将邮箱验证码填入 GPT 登录页面。

【三、使用动态密码器】
如果输入邮箱验证码后，页面继续提示输入验证器或动态验证码，请使用动态令牌获取验证码。
1. 完整动态令牌网址格式：https://2fa.run/<动态令牌提取码>
2. 也可以只复制最后一个 / 后面的提取码，在支持 TOTP 的软件或网页中生成动态验证码。
3. 请完整复制提取码，不要漏掉任何字符。
4. 如果 2fa.run 访问过多或出现 404，可使用备用地址：https://2fa.cn/ ，然后粘贴提取码生成验证码。

【四、绑定辅助邮箱】
如果页面提示绑定辅助邮箱，请输入您自己常用且可长期使用的邮箱作为辅助邮箱。绑定后请保存好该辅助邮箱信息。

【五、常见问题】
- 提示无法登录：通常与网络环境或 IP 质量有关，请更换稳定、干净的网络节点后重新登录。
- 提示所在国家或地区不可用：请更换稳定网络后重试。
- 提示账号或密码不正确：可能是当前 IP 被 Microsoft 风控，请更换 IP 后重试。
- 动态令牌网页打不开或显示 404：检查提取码是否复制完整；如仍无法打开，改用 https://2fa.cn/ 并粘贴提取码。

【安全提示】请妥善保管邮箱账号、GPT 密码、邮箱密码和动态令牌。不要把密码、动态令牌提取码或验证码发送给无关人员。

如有疑问，请随时联系我们。祝您使用愉快！`.trim();

  return { subject, html, text };
}

// 发送发货邮件
export async function sendDeliveryMail(params: SendMailParams): Promise<MailResult> {
  const settings = await getSettings();

  if (!settings.smtp_user || !settings.smtp_pass) {
    return { success: false, error: '未配置 SMTP 信息，请先在「设置 - 邮件配置」中填写 QQ 邮箱和授权码' };
  }

  const { subject, html, text } = buildDeliveryMail(params.delivery, params.customerName);

  let res: Response;
  try {
    res = await fetch(`${MAIL_SERVER}/api/send-mail`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        smtp: {
          host: String(settings.smtp_host || '').trim(),
          port: settings.smtp_port,
          user: String(settings.smtp_user || '').trim(),
          pass: settings.smtp_pass,
          from: settings.smtp_from || settings.smtp_user,
        },
        to: params.to,
        subject,
        html,
        text,
      }),
    });
  } catch {
    return {
      success: false,
      error: '无法连接本地邮件服务，请确认已运行 npm run mail-server（邮件容器是否在运行）',
    };
  }

  const data = await res.json().catch(() => ({ success: false, error: '邮件服务返回异常' }));

  // 记录发送历史
  try {
    await addMailRecord({
      to: params.to,
      customer_name: params.customerName,
      email_account: params.delivery.email_account,
      gpt_password: params.delivery.gpt_password,
      token_url: params.delivery.token_url,
      email_password: params.delivery.email_password,
      subject,
      status: data.success ? 'success' : 'failed',
      error: data.error,
      message_id: data.messageId,
      sent_at: new Date(),
    });
  } catch {
    // 记录历史失败不影响发送结果
  }

  // 发送失败时检查是否需要触发告警
  if (!data.success) {
    await checkMailFailureAlert().catch(() => {});
  }

  return data;
}

// 批量发送结果
export interface BatchResult {
  index: number;
  to: string;
  customerName?: string;
  success: boolean;
  error?: string;
}

// 批量发送发货邮件（逐封发送，返回每封结果）
export async function sendBatchDeliveryMail(items: SendMailParams[]): Promise<BatchResult[]> {
  const results: BatchResult[] = [];
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const r = await sendDeliveryMail(item);
    results.push({
      index: i,
      to: item.to,
      customerName: item.customerName,
      success: r.success,
      error: r.error,
    });
  }
  return results;
}

// 检查邮件连续失败告警：最近 N 条记录全部失败时触发告警
// 读后端 mailRecords，触发浏览器桌面通知
export async function checkMailFailureAlert(): Promise<void> {
  const allRecords = await listMailRecords();
  // 按时间倒序取最近 N 条（listMailRecords 已倒序）
  const records = allRecords.slice(0, MAIL_ALERT_THRESHOLD);
  if (records.length < MAIL_ALERT_THRESHOLD) return;

  // 全部失败才算连续失败
  const allFailed = records.every((r) => r.status === 'failed');
  if (!allFailed) return;

  const errors = records.map((r) => r.error || '未知错误').filter((v, i, a) => a.indexOf(v) === i);
  const content = `最近 ${MAIL_ALERT_THRESHOLD} 次邮件发送全部失败，错误：${errors.join('；')}。请检查邮件服务状态和 SMTP 配置。`;

  // 浏览器桌面通知（通知记录持久化待后端补 mail_alert 端点）
  if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {
    try {
      new Notification('邮件发送连续失败告警', { body: content });
    } catch {
      // 忽略通知异常
    }
  }
}
