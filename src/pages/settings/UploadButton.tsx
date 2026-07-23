import { Button, Upload } from 'antd';
import { UploadOutlined } from '@ant-design/icons';

/** 私有小组件：JSON 文件上传按钮包装，beforeUpload 返回 false 中断 antd 自动上传。 */
export default function UploadButton({ beforeUpload }: { beforeUpload: (file: File) => boolean }) {
  return (
    <Upload
      accept=".json"
      showUploadList={false}
      beforeUpload={(file) => {
        beforeUpload(file);
        return false;
      }}
    >
      <Button icon={<UploadOutlined />}>选择 JSON 文件恢复</Button>
    </Upload>
  );
}
