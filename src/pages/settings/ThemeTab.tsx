import { Card, Row, Col, Alert, message } from 'antd';
import { CheckOutlined } from '@ant-design/icons';
import { themes } from '@/config/themes';
import { useThemeStore } from '@/store/useThemeStore';

/** 主题选择 Tab：切换应用配色方案，状态来自全局 useThemeStore。 */
export default function ThemeTab() {
  const { themeId, setTheme } = useThemeStore();

  return (
    <div>
      <p style={{ color: 'var(--color-text-secondary)', marginBottom: 24 }}>选择应用的主题色彩方案，切换后立即生效</p>
      <Row gutter={[16, 16]}>
        {themes.map((t) => (
          <Col key={t.id} xs={12} sm={8} md={6}>
            <Card
              hoverable
              size="small"
              onClick={() => {
                setTheme(t.id);
                message.success(`已切换到「${t.name}」主题`);
              }}
              style={{
                cursor: 'pointer',
                border: themeId === t.id ? `1px solid ${t.swatch}` : '1px solid var(--color-border)',
                transition: 'border-color 0.2s ease',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div
                  style={{
                    width: 36,
                    height: 36,
                    borderRadius: 6,
                    background: t.swatch,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#fff',
                  }}
                >
                  {themeId === t.id && <CheckOutlined style={{ fontSize: 16 }} />}
                </div>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--color-dark)', fontSize: 13 }}>{t.name}</div>
                  <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                    <div style={{ width: 14, height: 14, borderRadius: 3, background: t.colors.primary }} />
                    <div style={{ width: 14, height: 14, borderRadius: 3, background: t.colors.primaryLight }} />
                    <div style={{ width: 14, height: 14, borderRadius: 3, background: t.colors.primaryBorder }} />
                  </div>
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
      <Alert
        type="info"
        message="主题偏好已自动保存到本地，下次打开应用时自动恢复"
        style={{ marginTop: 24 }}
        showIcon
      />
    </div>
  );
}
