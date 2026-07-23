import { describe, expect, it } from 'vitest';
import { normalizeXianyuImageUrl } from '@/utils/imageUrl';

describe('normalizeXianyuImageUrl', () => {
  it('returns undefined for empty or undefined input', () => {
    expect(normalizeXianyuImageUrl('')).toBeUndefined();
    expect(normalizeXianyuImageUrl(undefined)).toBeUndefined();
  });

  it('upgrades protocol-relative URLs to HTTPS', () => {
    expect(normalizeXianyuImageUrl('//img.alicdn.com/a.png')).toBe('https://img.alicdn.com/a.png');
  });

  it('upgrades http AliCDN URLs to HTTPS and converts heic to thumbnail', () => {
    expect(normalizeXianyuImageUrl('http://img.alicdn.com/bao/uploaded/i1/xxx/O1CN01.heic')).toBe(
      'https://img.alicdn.com/bao/uploaded/i1/xxx/O1CN01.heic_120x120.jpg',
    );
  });

  it('keeps https AliCDN non-heic URLs unchanged', () => {
    const url = 'https://img.alicdn.com/bao/uploaded/i1/xxx/O1CN01.jpg';
    expect(normalizeXianyuImageUrl(url)).toBe(url);
  });

  it('appends thumbnail suffix to AliCDN heic/heif URLs without an existing resize suffix', () => {
    expect(normalizeXianyuImageUrl('https://img.alicdn.com/foo.heic')).toBe(
      'https://img.alicdn.com/foo.heic_120x120.jpg',
    );
    expect(normalizeXianyuImageUrl('https://img.alicdn.com/foo.heif?x=1')).toBe(
      'https://img.alicdn.com/foo.heif_120x120.jpg',
    );
  });

  it('does not duplicate thumbnail suffix for heic URLs that already have one', () => {
    expect(normalizeXianyuImageUrl('https://img.alicdn.com/foo.heic_200x200.jpg')).toBe(
      'https://img.alicdn.com/foo.heic_200x200.jpg',
    );
  });

  it('does not modify non-AliCDN URLs', () => {
    expect(normalizeXianyuImageUrl('https://example.com/foo.heic')).toBe('https://example.com/foo.heic');
    expect(normalizeXianyuImageUrl('/local.png')).toBe('/local.png');
  });
});
