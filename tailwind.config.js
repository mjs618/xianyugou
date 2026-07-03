/** @type {import('tailwindcss').Config} */
// 主题色与语义色统一由 src/styles/global.css 的 CSS 变量管理（唯一真源），
// 此处不再重复定义颜色，避免出现多套不一致的色值。
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"PingFang SC"', '"Microsoft YaHei"', 'system-ui', 'sans-serif'],
        mono: ['"SF Mono"', 'Menlo', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
};
