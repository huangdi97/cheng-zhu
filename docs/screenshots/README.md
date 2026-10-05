# README / Public Demo 素材维护

README 使用的截图、GIF、封面图必须代表**当前 Goal-centered 产品**，不能继续用旧模块式 Assist / Knowledge Map / Resume Optimizer 当主产品故事。

## 当前公开故事

README 的主展示顺序应当是：

```text
Action Home
→ Goal Room
→ Practice
→ Preflight
→ Live Fast Cue
→ Reflection
→ Next Focus
```

这才是当前 v1.4 产品，而不是“打开应用直接进入实时辅助”。

## 推荐素材

建议公开素材至少覆盖：

| 文件 | 内容 |
|---|---|
| `product-demo.webm` | Goal-centered 完整主循环 |
| `product-demo-poster.png` | 主循环封面 |
| `product-demo.gif` | GitHub README 兼容预览 |
| `action-home.png` | Action Home |
| `goal-room.png` | Goal Overview / Next Focus |
| `practice.png` | Practice 3.0 |
| `preflight.png` | Preflight 3.0 |
| `live-fast-cue.png` | Question → Fast Cue → Source/Warning |
| `reflection.png` | Reflection → Next Focus |

辅助素材可以继续保留：

- Fact Inbox；
- Quick Notes；
- Question Banks；
- Panel Practice；
- Command Palette；
- Overlay；
- 390px；
- Light / Dark；
- Diagnostics A–F。

## Runtime evidence 优先

发布证据优先来自：

```text
GitHub Actions
→ Windows packaged app
→ runtime UI evidence artifact
```

README 演示可以使用 deterministic demo data，但必须来自当前前端组件和当前 IA。

禁止：

- 用设计稿冒充 runtime；
- 用旧 v1.2 模块截图冒充 v1.4；
- 在演示中把 synthetic 数据说成真实用户结果。

## 自动生成

当前脚本应维护为 Goal-centered：

```bash
cd frontend
npx playwright install chromium
npm run screenshots:readme
npm run demo:readme
```

如果脚本仍以旧 Assist route 为中心，应先更新脚本，再更新二进制素材。

## Demo 内容约定

公开 demo 优先在 45–75 秒内表达：

1. 首页告诉用户下一步；
2. 进入一个具体 Goal；
3. 看 Next Focus；
4. 启动针对性 Practice；
5. Go Live → Preflight；
6. Question → Fast Cue；
7. 结束后 Reflection；
8. Reflection 改变下一步。

实时技术细节（ASR / KB / Deep / Overlay）可以出现，但不应重新成为整个产品故事。

## 隐私

所有公开素材必须使用 synthetic/demo data。

不要把：

- API Key；
- 真实简历；
- 真实面试录音；
- 真实用户 transcript；
- 用户私人材料

提交到仓库。
