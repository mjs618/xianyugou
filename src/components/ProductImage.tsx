import { useEffect, useState, type CSSProperties } from 'react';
import { normalizeXianyuImageUrl } from '@/utils/imageUrl';

interface ProductImageProps {
  url?: string;
  size?: number;
  alt?: string;
  style?: CSSProperties;
  showFallback?: boolean;
}

/**
 * 统一商品图片组件。
 *
 * - 自动把闲鱼/AliCDN 的 http、//、.heic 等 URL 规范化为可显示地址。
 * - 加载失败时显示占位，避免裂图。
 */
export default function ProductImage({
  url,
  size = 44,
  alt = '',
  style,
  showFallback = true,
}: ProductImageProps) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [url]);

  const src = normalizeXianyuImageUrl(url);

  if (!src || failed) {
    if (!showFallback) return null;
    return (
      <span
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: size,
          height: size,
          borderRadius: 4,
          background: '#f5f5f5',
          color: '#999',
          fontSize: 12,
          ...style,
        }}
      >
        无图
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      onError={() => setFailed(true)}
      style={{
        width: size,
        height: size,
        objectFit: 'cover',
        borderRadius: 4,
        display: 'block',
        ...style,
      }}
    />
  );
}
