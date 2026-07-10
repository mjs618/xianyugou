import { describe, expect, it } from 'vitest';
import {
  decryptWithPassword,
  encryptWithPassword,
  isEncryptedBackup,
} from '@/utils/backupCrypto';

describe('backupCrypto', () => {
  it('使用随机 salt 和 iv 加密并可正确解密', async () => {
    const first = await encryptWithPassword(
      '{"version":1}',
      'correct-password',
    );
    const second = await encryptWithPassword(
      '{"version":1}',
      'correct-password',
    );

    expect(first).not.toBe(second);
    expect(isEncryptedBackup(first)).toBe(true);
    await expect(
      decryptWithPassword(first, 'correct-password'),
    ).resolves.toBe('{"version":1}');
  });

  it('拒绝空密码、错误密码和损坏格式', async () => {
    await expect(encryptWithPassword('data', '')).rejects.toThrow(
      '备份密码不能为空',
    );
    const encrypted = await encryptWithPassword('data', 'correct');

    await expect(decryptWithPassword(encrypted, 'wrong')).rejects.toThrow(
      '备份密码错误或文件已损坏',
    );
    await expect(
      decryptWithPassword('backup:v1:broken', 'correct'),
    ).rejects.toThrow('加密备份格式损坏');
  });
});
