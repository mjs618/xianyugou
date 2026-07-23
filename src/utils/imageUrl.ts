/**
 * Normalize a Xianyu/AliCDN image URL so that it can be displayed in the browser.
 *
 * - Upgrades protocol-relative URLs to HTTPS.
 * - Upgrades plain HTTP AliCDN URLs to HTTPS (avoids mixed-content when the
 *   app is served over HTTPS).
 * - Appends a JPEG thumbnail suffix for .heic/.heif originals, since browsers
 *   often fail to decode HEIC and AliCDN returns a JPEG/WebP when a resize
 *   suffix is requested.
 */
export function normalizeXianyuImageUrl(url?: string): string | undefined {
  if (!url) return undefined;

  let normalized = url.startsWith('//') ? `https:${url}` : url;
  normalized = normalized.replace(/^http:\/\/img\.alicdn\.com\//, 'https://img.alicdn.com/');

  const isAliCdn = /^https:\/\/img\.alicdn\.com\//i.test(normalized);
  if (
    isAliCdn &&
    /\.(heic|heif)(?:$|\?)/i.test(normalized) &&
    !/_\d+x\d+\.jpg(?:$|\?)/i.test(normalized)
  ) {
    normalized = normalized.split('?')[0] + '_120x120.jpg';
  }

  return normalized;
}
