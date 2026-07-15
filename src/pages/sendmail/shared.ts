/** SendMail 子组件共享的类型与工具函数。 */

export interface MailFormValues {
  to: string;
  customerName?: string;
  email_account: string;
  gpt_password: string;
  token_url: string;
  email_password: string;
}

/** 从 contact_info 提取邮箱地址。 */
export function extractEmail(contactInfo?: string): string {
  if (!contactInfo) return '';
  const m = contactInfo.match(/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/);
  return m ? m[0] : '';
}
