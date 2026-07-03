// 敏感字段加密工具 - 基于 Web Crypto API（AES-GCM）
// 主密钥为 non-extractable CryptoKey，存储于 IndexedDB，无法被 JS 读取原始密钥材料
// 加密后的值带前缀 "enc:v1:"，便于识别和存量数据迁移

const ENC_PREFIX = 'enc:v1:';
const KEY_STORE_KEY = 'master-key';

// IndexedDB 用于存储主密钥的独立库（与业务库分离，避免备份/恢复时丢失）
const KEY_DB_NAME = 'XianyuKeyStore';
const KEY_DB_VERSION = 1;
const KEY_STORE = 'keys';

// 获取或创建主密钥（non-extractable，JS 无法读取密钥原材料）
async function getOrCreateMasterKey(): Promise<CryptoKey> {
  const key = await getKeyFromStore();
  if (key) return key;

  // 生成新的 AES-GCM 主密钥，extractable=false 保证密钥不可导出
  const newKey = await crypto.subtle.generateKey(
    { name: 'AES-GCM', length: 256 },
    false, // non-extractable
    ['encrypt', 'decrypt']
  );
  await saveKeyToStore(newKey);
  return newKey;
}

// 从 IndexedDB 读取主密钥
async function getKeyFromStore(): Promise<CryptoKey | null> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(KEY_DB_NAME, KEY_DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(KEY_STORE)) {
        db.createObjectStore(KEY_STORE);
      }
    };
    req.onsuccess = () => {
      const db = req.result;
      try {
        const tx = db.transaction(KEY_STORE, 'readonly');
        const store = tx.objectStore(KEY_STORE);
        const getReq = store.get(KEY_STORE_KEY);
        getReq.onsuccess = () => resolve(getReq.result || null);
        getReq.onerror = () => reject(getReq.error);
      } catch {
        resolve(null);
      }
    };
    req.onerror = () => reject(req.error);
  });
}

// 保存主密钥到 IndexedDB
async function saveKeyToStore(key: CryptoKey): Promise<void> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(KEY_DB_NAME, KEY_DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(KEY_STORE)) {
        db.createObjectStore(KEY_STORE);
      }
    };
    req.onsuccess = () => {
      const db = req.result;
      const tx = db.transaction(KEY_STORE, 'readwrite');
      const store = tx.objectStore(KEY_STORE);
      store.put(key, KEY_STORE_KEY);
      tx.oncomplete = () => resolve();
      tx.onerror = () => reject(tx.error);
    };
    req.onerror = () => reject(req.error);
  });
}

// Base64 编解码（处理 Uint8Array）
function bufToBase64(buf: ArrayBuffer): string {
  const bytes = new Uint8Array(buf);
  let binary = '';
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToBuf(b64: string): ArrayBuffer {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes.buffer;
}

// 判断值是否已加密
export function isEncrypted(value: string | undefined | null): boolean {
  return !!value && value.startsWith(ENC_PREFIX);
}

// 加密字符串，返回带前缀的密文
// P1 安全加固：加密失败抛错而非静默回退明文，避免敏感数据以明文存储
export async function encryptField(plaintext: string): Promise<string> {
  if (!plaintext) return plaintext;
  // 已加密的值不重复加密（避免双重加密）
  if (isEncrypted(plaintext)) return plaintext;

  try {
    const key = await getOrCreateMasterKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const encoded = new TextEncoder().encode(plaintext);
    const ciphertext = await crypto.subtle.encrypt(
      { name: 'AES-GCM', iv },
      key,
      encoded
    );
    return ENC_PREFIX + bufToBase64(iv.buffer) + ':' + bufToBase64(ciphertext);
  } catch (err) {
    // 加密失败应抛错，由调用方决定回退策略；不应静默回退明文导致敏感数据暴露
    console.error('加密失败:', err);
    throw new Error('敏感字段加密失败，请检查浏览器是否支持 Web Crypto API');
  }
}

// 解密字符串
export async function decryptField(value: string | undefined | null): Promise<string> {
  if (!value || !isEncrypted(value)) return value || '';

  try {
    const key = await getOrCreateMasterKey();
    const payload = value.slice(ENC_PREFIX.length);
    const parts = payload.split(':');
    if (parts.length !== 2) return value; // 格式异常，返回原值

    const iv = new Uint8Array(base64ToBuf(parts[0]));
    const ciphertext = base64ToBuf(parts[1]);
    const decrypted = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext
    );
    return new TextDecoder().decode(decrypted);
  } catch (err) {
    // 主密钥丢失或数据损坏，返回占位符避免暴露密文
    console.error('解密失败:', err);
    return '******';
  }
}

// 批量解密对象中的指定字段（原地修改）
export async function decryptFields<T extends Record<string, any>>(
  obj: T,
  fields: (keyof T)[]
): Promise<T> {
  for (const field of fields) {
    if (obj[field] && typeof obj[field] === 'string') {
      obj[field] = await decryptField(obj[field] as string) as T[keyof T];
    }
  }
  return obj;
}

// ==================== 备份加密（P0-2）====================
// 基于用户密码的加密，用于 JSON 备份文件加密
// 流程：用户密码 → PBKDF2 派生密钥（salt 随机）→ AES-GCM 加密
// 密文格式：backup:v1:<base64(salt)>:<base64(iv)>:<base64(ciphertext)>

const BACKUP_PREFIX = 'backup:v1:';
const PBKDF2_ITERATIONS = 100000;

// 从用户密码派生 AES-GCM 密钥
async function deriveKeyFromPassword(password: string, salt: Uint8Array): Promise<CryptoKey> {
  const enc = new TextEncoder();
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    enc.encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: PBKDF2_ITERATIONS, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

// 用密码加密任意文本（用于备份加密）
export async function encryptWithPassword(plaintext: string, password: string): Promise<string> {
  if (!password) throw new Error('备份密码不能为空');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKeyFromPassword(password, salt);
  const encoded = new TextEncoder().encode(plaintext);
  const ciphertext = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, encoded);
  return BACKUP_PREFIX + bufToBase64(salt.buffer) + ':' + bufToBase64(iv.buffer) + ':' + bufToBase64(ciphertext);
}

// 用密码解密文本（用于备份恢复）
export async function decryptWithPassword(encrypted: string, password: string): Promise<string> {
  if (!encrypted.startsWith(BACKUP_PREFIX)) {
    throw new Error('无效的加密备份格式');
  }
  const payload = encrypted.slice(BACKUP_PREFIX.length);
  const parts = payload.split(':');
  if (parts.length !== 3) throw new Error('加密备份格式损坏');
  const salt = new Uint8Array(base64ToBuf(parts[0]));
  const iv = new Uint8Array(base64ToBuf(parts[1]));
  const ciphertext = base64ToBuf(parts[2]);
  const key = await deriveKeyFromPassword(password, salt);
  try {
    const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, ciphertext);
    return new TextDecoder().decode(decrypted);
  } catch {
    throw new Error('备份密码错误或文件已损坏');
  }
}

// 判断是否为加密备份
export function isEncryptedBackup(value: string): boolean {
  return value.startsWith(BACKUP_PREFIX);
}
