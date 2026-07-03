// 本地邮件发送服务（配合闲鱼记账系统前端使用）
// 使用 nodemailer 通过 QQ 邮箱 SMTP 发送邮件
// 启动：npm run mail-server
import http from 'node:http';
import dns from 'node:dns';
import nodemailer from 'nodemailer';

const PORT = process.env.MAIL_PORT || 3001;

// 全局强制 IPv4 优先解析，避免 Docker 容器内 IPv6 导致 ENOTFOUND
dns.setDefaultResultOrder('ipv4first');

// 统一响应
function json(res, status, data) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
  res.end(JSON.stringify(data));
}

// 将 SMTP/网络错误翻译为可操作的中文提示
// 覆盖 QQ 邮箱最常见的几类失败，引导用户自行修复配置而非面对一长串英文
function explainSmtpError(err) {
  const msg = String(err.message || '');
  const code = err.responseCode;
  const resp = String(err.response || '');

  // 认证失败：授权码错误/失效/未开启服务/被风控（QQ 535）
  if (code === 535 || /535|login fail|invalid login/i.test(msg + resp)) {
    return 'SMTP 认证失败：授权码错误或已失效。请到邮箱网页端「设置 → 账户」确认已开启 IMAP/SMTP 服务，并重新生成「授权码」（不是邮箱登录密码），填入系统设置后重试。';
  }
  // 用户名/密码被拒（Gmail/网易等 535 Authentication required 也归此类）
  if (/authentication required|auth.*fail|username and password not accepted/i.test(msg + resp)) {
    return 'SMTP 认证失败：邮箱账号或授权码不正确，请检查发件邮箱地址与授权码是否匹配。';
  }
  // 收件人地址无效（550）
  if (code === 550 || /550|user not found|mailbox unavailable|does ?not exist/i.test(msg + resp)) {
    return '收件人邮箱无效或不存在，请核对收件人地址是否正确。';
  }
  // 发送频率/数量超限
  if (/frequency|rate limit|too many|quota|exceed/i.test(msg + resp)) {
    return '发送过于频繁或超出邮箱每日发送限额，请稍候片刻再试，或减少批量发送数量。';
  }
  // 网络层：连不上服务器
  if (/ENOTFOUND|EAI_AGAIN|getaddrinfo/i.test(msg)) {
    return `无法解析 SMTP 服务器地址「${String(err.message).match(/(\S+)/)?.[0] || ''}」，请检查「SMTP 服务器」填写是否正确，或当前网络/DNS 是否可用。`;
  }
  if (/ECONNREFUSED|ECONNRESET|ETIMEDOUT|connect ETIMEDOUT/i.test(msg)) {
    return `无法连接 SMTP 服务器，请检查端口（465/587）是否正确、服务器是否可达，或网络/防火墙是否放行。`;
  }
  // SSL/TLS 相关
  if (/SSL|TLS|certificate|self[- ]signed|UNABLE_TO_VERIFY/i.test(msg)) {
    return 'SMTP 加密连接（SSL/TLS）握手失败，请确认端口与加密方式匹配（465 用 SSL，587 用 STARTTLS）。';
  }
  // 兜底：保留原始信息
  return err.message || '邮件发送失败';
}

// 读取请求体
async function readBody(req) {
  let body = '';
  for await (const chunk of req) body += chunk;
  return body ? JSON.parse(body) : {};
}

const server = http.createServer(async (req, res) => {
  // CORS（前端运行在 5173 端口）
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  // 健康检查
  if (req.method === 'GET' && req.url === '/api/health') {
    json(res, 200, { ok: true, service: 'mail-server', time: new Date().toISOString() });
    return;
  }

  // 发送邮件
  if (req.method === 'POST' && req.url === '/api/send-mail') {
    try {
      const { smtp, to, subject, html, text } = await readBody(req);

      if (!smtp || !smtp.host || !smtp.user || !smtp.pass) {
        json(res, 400, { success: false, error: 'SMTP 配置不完整（需要 host/user/pass）' });
        return;
      }
      if (!to) {
        json(res, 400, { success: false, error: '收件人邮箱不能为空' });
        return;
      }

      // 去除前后空白，避免 ENOTFOUND / 参数校验失败
      const host = String(smtp.host).trim();
      const port = Number(smtp.port) || 465;
      const user = String(smtp.user).trim();
      const rcpt = String(to).trim();

      // QQ SMTP 要求 MAIL FROM 必须是认证账号本身的邮箱地址
      // smtp_from 仅用于显示名称（如"闲鱼助手 <xxx@qq.com>"），提取其中的邮箱部分
      const fromRaw = String(smtp.from || user).trim();
      const emailMatch = fromRaw.match(/<[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}>/);
      const fromEmail = emailMatch
        ? emailMatch[0].slice(1, -1)
        : (fromRaw.includes('@') ? fromRaw : user);
      // 如果 smtp_from 含显示名称，保留格式；否则直接用邮箱
      const displayName = fromRaw.includes('<') ? fromRaw.split('<')[0].trim() : '';
      const from = displayName ? `${displayName} <${fromEmail}>` : fromEmail;

      // 直接使用域名连接，由 dns.setDefaultResultOrder 保证 IPv4 优先
      const transporter = nodemailer.createTransport({
        host,
        port,
        secure: port === 465,
        auth: { user, pass: smtp.pass },
        name: host,
      });

      console.log(`[${new Date().toISOString()}] 发送请求: from=${from} to=${rcpt} host=${host}:${port}`);
      const info = await transporter.sendMail({
        from,
        to: rcpt,
        subject: subject || '发货信息',
        html,
        text,
      });

      console.log(`[${new Date().toISOString()}] 邮件已发送 -> ${rcpt} | messageId: ${info.messageId}`);
      json(res, 200, { success: true, messageId: info.messageId });
    } catch (err) {
      console.error(`[${new Date().toISOString()}] 发送失败:`, err.message);
      if (err.response) console.error('  SMTP 响应:', err.response);
      if (err.responseCode) console.error('  响应码:', err.responseCode);
      if (err.command) console.error('  命令:', err.command);
      // 将 SMTP 原始错误翻译为可操作的中文提示，附带原错误便于排障
      json(res, 500, { success: false, error: explainSmtpError(err), rawError: err.message });
    }
    return;
  }

  json(res, 404, { error: 'Not Found' });
});

server.listen(PORT, () => {
  console.log('========================================');
  console.log('  闲鱼记账 - 邮件发送服务已启动');
  console.log(`  地址: http://localhost:${PORT}`);
  console.log('  接口: POST /api/send-mail');
  console.log('  健康检查: GET /api/health');
  console.log('========================================');
});
