---
timestamp: 2026-08-15T03-26-17Z
slug: frontend-src-app-tsx
---
# Critique — frontend/src/App.tsx（成竹 Cheng Zhu 主界面）

2026-08-15 · 双路独立评审（A 设计评审 + B 机械检测/a11y）· slug: frontend-src-app-tsx

## 评分（A）
- 设计具体性 4/5 · 视觉层级/IA 4/5 · 一致性 3/5 · 颜色与主题 3/5 · 排版 3/5 · 动效 4/5 · 可访问性 3/5 · 响应式 4/5

## 结论
方向正确、主链优秀：assist 双栏、角色化转录、玻璃浮层、低音量动效、6 主题令牌在核心工作区执行干净。短板是「外围塌陷」：求职看板/复盘/设置/悬浮窗退回通用后台色板（419 处默认色 + 18 处 hex），组件原语（按钮/开关/焦点环/状态徽标）多套并存，overlay 不参与主题。

## 必须修（B 实证）
1. ControlBar.tsx:645-646 关闭粘贴图 X 按钮缺 aria-label
2. ControlBar.tsx:772-776 结束面试按钮 <sm 断点纯图标无名称
3. ControlBar.tsx:896-961 aria-modal dialog 缺 Esc/背景点击关闭
4. index.css ov-focus 覆盖层 11-12px 文本对比度 2.3-3.3:1（< AA 4.5）
5. App.tsx:295-324 模块菜单缺 Esc 关闭

## 高优先结构性（A）
1. 语义令牌不变量被破坏：419 处默认调色板 + 18 处 hex（次级模块 + overlay）
2. 状态色语义错位：评分/状态用 raw 色相；overlay FAIL=琥珀 vs 主界面错误=红；isLight 分支硬编码
3. 主按钮三套实现 + 主行动随状态变色（未就绪=琥珀）
4. 焦点环三套并存（outline/全强度/ring-inset）
5. Toggle 三套实现（checkbox/胶囊/44x24 switch）vs design.json 36x20
6. emoji 当图标（logo/模式/视觉标记/toast），无无障碍名称
7. assist 次级 tab 与移动 tab 缺 aria-pressed/role=tab 语义
8. 悬停位移/内容平面投影违反 DESIGN.md Elevation 规则
9. 字号体系漂移（text-[9px]x18 / 13px / 15px 越界）
10. 圆角命名错位（design.json md=8 vs Tailwind md=6）+ 分隔条 aria/钳制不一致

## 推荐执行顺序
P0（快、安全）：B 的 5 条 a11y 修复（aria-label/Esc/对比度）
P1（中）：组件原语收敛 PrimaryButton/Switch/FocusRing/StatusBadge + emoji→lucide
P2（大）：语义令牌全仓审计替换 + overlay 令牌化 + 状态色语义统一
P3（小）：字号体系归一 + 圆角表同步 + hover 位移清理
