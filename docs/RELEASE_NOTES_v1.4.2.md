# 成竹 Chengzhu v1.4.2

## 这是什么版本

v1.4.2 是 v1.4.1 之后的产品工艺与公开产品面收口补丁。

它不增加新的一级功能，也不改变 v1.2/v1.3 Verified Interview Core。它把已经合入 main 的最终用户语言、公开截图、产品文档和 release-facing surface 真正打进可下载安装包，使：

```text
仓库中的最终产品事实
=
GitHub Release 中用户下载到的产品事实
```

## Release provenance closure

在最终发布审计中发现，v1.4.1 的 Release workflow 从：

```text
2355a1cdb71d60ae7f5d497150bdcd94499e9a3e
```

检出并构建 Windows 产物；但长时间构建期间 `main` 又前进到了：

```text
df286e768a874eab12365259c50e7742c77c33d9
```

旧 workflow 的 `gh release create` 没有显式 `--target`，因此 GitHub 在创建 `v1.4.1` tag 时使用了当时较新的默认分支 HEAD。两者之间包含 `backend/services/product/live.py`、`next_focus.py` 等产品代码变化，所以不能把它当成纯文档偏差。

v1.4.2 将发布不变量升级为：

```text
CI-proven SHA
==
Release checkout SHA
==
binary source SHA
==
public tag SHA
```

自动发布器现在从刚刚通过 main CI 的 `workflow_run.head_sha` 检出源码，并把该 SHA 作为 `source_sha` 传入 Release workflow。Release 创建 tag 时显式使用 `--target <source_sha>`，并在：

- tag 创建后；
- GitHub Release download-back 前；
- 最终从 draft 发布前；

三次验证 tag SHA 与 binary source SHA 一致。任何不一致都会直接使发布失败。

download-back evidence 同时记录 `source_sha` 与 `tag_sha`，因此后续可以从发布证据直接证明“这个安装包来自哪一个源码快照”。

## 主要变化

### Preflight 产品语言收口

Preflight 不再暴露工程值，例如：

```text
回答模型 0
AUTO
whisper
Skill Cards
Stories
```

而是展示：

- 实际配置的模型名称；
- 用户可理解的语音识别/语言标签；
- 中文产品术语；
- 当前 Goal / Person / Session override 的来源关系。

### Next Focus 产品语言收口

Next Focus 仍然可以在内部使用 rubric / priority / weight 做排序，但用户不再看到调试/评估器文案，例如：

```text
第 1.0 级（满级 4）
岗位权重 18
```

用户看到的是：

- 为什么这是当前最值得做的事；
- 它来自哪条真实 Gap / Reflection / Goal 要求；
- 下一步可以做什么。

### 公开产品文档与 Runtime 截图统一

README / DEVELOPMENT / RELEASE / LIVE_UX / PREP_MOCK_REVIEW 已全部对齐当前 Goal-centered Interview OS。

公开截图来自真实 v1.4 Windows packaged runtime evidence，包括：

- Action Home；
- Goal Room；
- Practice；
- Preflight；
- Live Fast Cue；
- Reflection；
- Command Palette；
- 390px Goal Prepare。

旧 module-first Assist/Knowledge/Resume 截图生成器不再允许覆盖 README 产品媒体。

### 最终设计收敛矩阵

新增：

```text
reports/CHENGZHU_V1_3_R2_TO_V1_4_FINAL_DESIGN_CONVERGENCE.md
```

逐项映射：

- v1.3-R2 Appendix E 产品验收项；
- v1.4 Engineering Definition of Done；
- 真实实现文件；
- 测试/Runtime/Release 证据；
- 仍然必须保持为外部或真实用户验证的项目。

## 保持不变的核心边界

v1.4.2 不改变：

- Frozen InterviewPack；
- Context Compiler authority；
- Provenance / User Assertion / Session Statement；
- Fast Cue before Deep；
- Stream Truth Guard；
- Human Assistance Policy；
- Share Privacy default OFF；
- Goal-centered IA；
- Personal Conversation Intelligence Future Profile boundary。

## 验证与发布门禁

v1.4.2 继续要求：

- backend / frontend / desktop 全量测试；
- functional Playwright；
- visual regression；
- accessibility/e2e gates；
- packaged smoke；
- Windows installer + portable；
- clean installer replay；
- SHA256；
- GitHub Release download-back；
- 安装后 packaged smoke。

只有这些门禁全部通过后才允许发布。

此外 v1.4.2 新增 release-provenance gate：公开 tag 必须与本次 installer / portable 的构建源码 SHA 完全相同。

## 真实用户边界

仍然保留：

```text
REAL_USER_EVIDENCE_PENDING
```

v1.4.2 不声称：

```text
PMF_PROVEN
REAL_INTERVIEW_TRANSFER_PROVEN
V1_4_REAL_VALIDATION_COMPLETE
```

真实长期用户、真实 provider 质量/成本、交互式多显示器 Overlay、代码签名、macOS notarization、公共 Human Coach relay 仍属于外部证据。

## License

MIT。第三方组件继续保留各自许可证，详见 `THIRD_PARTY_NOTICES.md`。
