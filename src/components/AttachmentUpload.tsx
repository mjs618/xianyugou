import { useState, useEffect, useCallback, useMemo } from 'react';
import { Upload, Button, message, Space, Modal, Empty } from 'antd';
import { PlusOutlined, DeleteOutlined, PaperClipOutlined } from '@ant-design/icons';
import { addAttachment, deleteAttachment, getAttachmentContentUrl, getAttachments, MAX_ATTACHMENT_SIZE, ACCEPTED_IMAGE_TYPES } from '@/services/attachmentService';
import { getErrorMessage } from '@/utils/error';
import type { Attachment } from '@/types';

interface AttachmentUploadProps {
  value?: string[];
  onChange?: (ids: string[]) => void;
  disabled?: boolean;
  maxCount?: number;
}

export default function AttachmentUpload({ value = [], onChange, disabled, maxCount = 9 }: AttachmentUploadProps) {
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewSrc, setPreviewSrc] = useState<string>('');
  const [uploading, setUploading] = useState(false);

  // 根据 value（id 数组）加载附件详情
  const loadAttachments = useCallback(async () => {
    if (!value || value.length === 0) {
      setAttachments([]);
      return;
    }
    const list = await getAttachments(value);
    setAttachments(list);
  }, [value]);

  useEffect(() => {
    loadAttachments();
  }, [loadAttachments]);

  const previewUrls = useMemo(() => {
    const map = new Map<number, string>();
    for (const att of attachments) {
      map.set(att.id, getAttachmentContentUrl(att.id));
    }
    return map;
  }, [attachments]);

  // 处理文件选择（antd Upload beforeUpload 返回 false 阻止自动上传）
  const handleBeforeUpload = async (file: File): Promise<boolean> => {
    if (file.size > MAX_ATTACHMENT_SIZE) {
      message.error(`「${file.name}」超过 ${MAX_ATTACHMENT_SIZE / 1024 / 1024}MB 限制`);
      return false;
    }
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      message.error(`「${file.name}」格式不支持，仅支持 JPG/PNG/WebP/GIF`);
      return false;
    }
    if (attachments.length >= maxCount) {
      message.error(`最多上传 ${maxCount} 个附件`);
      return false;
    }

    setUploading(true);
    try {
      const att = await addAttachment(file);
      const nextIds = [...value, String(att.id)];
      onChange?.(nextIds);
      message.success(`「${file.name}」已上传`);
    } catch (err: unknown) {
      message.error(getErrorMessage(err, '上传失败'));
    } finally {
      setUploading(false);
    }
    return false;
  };

  // 删除附件
  const handleDelete = async (id: number) => {
    Modal.confirm({
      title: '确认删除该附件？',
      content: '删除后不可恢复',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        await deleteAttachment(id);
        const nextIds = value.filter((v) => v !== String(id));
        onChange?.(nextIds);
        message.success('已删除');
      },
    });
  };

  // 预览大图
  const handlePreview = (att: Attachment) => {
      const url = previewUrls.get(att.id);
    if (url) {
      setPreviewSrc(url);
      setPreviewOpen(true);
    }
  };

  const onClosePreview = () => {
    setPreviewOpen(false);
    setPreviewSrc('');
  };

  if (disabled && attachments.length === 0) {
    return <Empty description="无附件" image={Empty.PRESENTED_IMAGE_SIMPLE} />;
  }

  return (
    <div>
      <Space wrap size={8}>
        {attachments.map((att) => (
          <div
            key={att.id}
            style={{
              position: 'relative',
              width: 96,
              height: 96,
              borderRadius: 6,
              overflow: 'hidden',
              border: '1px solid var(--color-border)',
              background: 'var(--color-bg)',
            }}
          >
            <img
              src={previewUrls.get(att.id!)}
              alt={att.name}
              style={{ width: '100%', height: '100%', objectFit: 'cover', cursor: 'pointer' }}
              onClick={() => handlePreview(att)}
            />
            {!disabled && (
              <Button
                type="primary"
                danger
                size="small"
                icon={<DeleteOutlined />}
                onClick={(e) => { e.stopPropagation(); handleDelete(att.id); }}
                style={{ position: 'absolute', top: 2, right: 2, minWidth: 24, padding: 0 }}
              />
            )}
            <div
              style={{
                position: 'absolute',
                bottom: 0,
                left: 0,
                right: 0,
                background: 'rgba(0,0,0,0.5)',
                color: '#fff',
                fontSize: 11,
                padding: '2px 4px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={att.name}
            >
              {att.name}
            </div>
          </div>
        ))}

        {!disabled && attachments.length < maxCount && (
          <Upload
            accept={ACCEPTED_IMAGE_TYPES.join(',')}
            showUploadList={false}
            beforeUpload={handleBeforeUpload}
            multiple
            disabled={uploading || disabled}
          >
            <div
              style={{
                width: 96,
                height: 96,
                border: '1px dashed var(--color-border)',
                borderRadius: 6,
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                color: 'var(--color-text-secondary)',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--theme-primary)')}
              onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--color-border)')}
            >
              <PlusOutlined style={{ fontSize: 20 }} />
              <span style={{ fontSize: 12, marginTop: 4 }}>上传图片</span>
            </div>
          </Upload>
        )}
      </Space>

      {!disabled && (
        <div style={{ marginTop: 4, fontSize: 12, color: 'var(--color-text-tertiary)' }}>
          <PaperClipOutlined /> 支持 JPG/PNG/WebP/GIF，单张 ≤ {MAX_ATTACHMENT_SIZE / 1024 / 1024}MB
          {attachments.length > 0 && `，已上传 ${attachments.length}/${maxCount}`}
        </div>
      )}

      {/* 大图预览 */}
      <Modal open={previewOpen} onCancel={onClosePreview} footer={null} width={800} destroyOnClose>
        {previewSrc && <img src={previewSrc} alt="预览" style={{ width: '100%' }} />}
      </Modal>
    </div>
  );
}
