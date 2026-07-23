// JSON 备份密码加密：PBKDF2-SHA256 派生密钥，AES-256-GCM 加密。
// 格式：backup:v1:<base64(salt)>:<base64(iv)>:<base64(ciphertext)>

const BACKUP_PREFIX = 'backup:v1:';
const PBKDF2_ITERATIONS = 100000;

function bufToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let index = 0; index < bytes.length; index += 1) {
    binary += String.fromCharCode(bytes[index]);
  }
  return btoa(binary);
}

function base64ToBuf(value: string): ArrayBuffer {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes.buffer;
}

async function deriveKeyFromPassword(
  password: string,
  salt: Uint8Array,
): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    { name: 'PBKDF2' },
    false,
    ['deriveKey'],
  );
  return crypto.subtle.deriveKey(
    {
      name: 'PBKDF2',
      salt,
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt'],
  );
}

export async function encryptWithPassword(
  plaintext: string,
  password: string,
): Promise<string> {
  if (!password) throw new Error('备份密码不能为空');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const key = await deriveKeyFromPassword(password, salt);
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv },
    key,
    new TextEncoder().encode(plaintext),
  );
  return `${BACKUP_PREFIX}${bufToBase64(salt.buffer)}:${bufToBase64(iv.buffer)}:${bufToBase64(ciphertext)}`;
}

export async function decryptWithPassword(
  encrypted: string,
  password: string,
): Promise<string> {
  if (!encrypted.startsWith(BACKUP_PREFIX)) {
    throw new Error('无效的加密备份格式');
  }
  const parts = encrypted.slice(BACKUP_PREFIX.length).split(':');
  if (parts.length !== 3) throw new Error('加密备份格式损坏');
  const salt = new Uint8Array(base64ToBuf(parts[0]));
  const iv = new Uint8Array(base64ToBuf(parts[1]));
  const ciphertext = base64ToBuf(parts[2]);
  const key = await deriveKeyFromPassword(password, salt);
  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv },
      key,
      ciphertext,
    );
    return new TextDecoder().decode(plaintext);
  } catch {
    throw new Error('备份密码错误或文件已损坏');
  }
}

export function isEncryptedBackup(value: string): boolean {
  return value.startsWith(BACKUP_PREFIX);
}
