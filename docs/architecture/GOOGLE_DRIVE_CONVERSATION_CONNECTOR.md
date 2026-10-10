# Google Drive / Docs Conversation Connector
## Chengzhu v2 · opt-in read-only external document provider

**状态**：REAL ADAPTER CODE AVAILABLE / OPT-IN / REAL ACCOUNT EVIDENCE PENDING  
**Provider**：Google Drive API v3  
**Capability**：`docs.read`  
**OAuth scope contract**：`https://www.googleapis.com/auth/drive.readonly`

---

## 1. 产品目的

Google Drive provider 只解决一条链：

```text
explicit Drive folder
→ complete user-triggered read refresh
→ immutable DOCUMENT snapshots
→ user explicitly selects snapshots
→ frozen Session Pack
→ grounded Manual Ask / Recall / Contribution Opportunity
```

它不是：
- Drive mirror；
- background crawler；
- document editor；
- OAuth account manager；
- binary/PDF understanding engine。

---

## 2. 为什么使用 full target refresh

Drive 有 account-wide Changes API，但 Chengzhu 当前产品语义是：

> 用户明确把某个资料范围带入某个 Space。

因此 v1 provider 不做 account-wide background changes mirror，而是：

```text
folder id
→ prove folder target
→ files.list complete pagination
→ read/export supported content
→ only after complete collection return snapshots
```

每次 Sync 都由用户显式触发。

好处：
- target scope 可见；
- 不会因为 changes token 扫描用户整个 Drive；
- 不会把“移出 folder / 删除 / account-wide change feed”悄悄解释成 Space truth；
- immutable snapshot revision 仍由 Chengzhu generic integration boundary 保留。

---

## 3. Credential boundary

启动后端前显式启用：

```text
CHENGZHU_GOOGLE_DRIVE_CONNECTOR_ENABLE=1
```

真实 access token 放在进程环境，例如：

```text
GOOGLE_DRIVE_ACCESS_TOKEN=<secret>
```

product.db 只保存 opaque reference：

```text
provider:google-drive:env:GOOGLE_DRIVE_ACCESS_TOKEN
```

禁止：
- UI 粘贴 access token；
- product.db 保存 token；
- snapshot / export / audit 保存 Authorization；
- URL query 携带 bearer token；
- HTTP API base。

当前没有伪造 OAuth refresh-token / consent lifecycle。

---

## 4. Verify truth

Verify 只执行 Google Drive `about.get` read probe：

```text
opaque credential ref
→ resolve env access token
→ GET /drive/v3/about
→ explicit success
→ CONNECTED
```

CONNECTED 只证明 account token 当前可读。

它不证明：
- 某个 folder 存在；
- folder 可读；
- folder 内所有文件内容可导出。

这些只能由显式 Sync 的 target probe + provider response 证明。

---

## 5. Folder target

Sync target 必须是：

```text
root
or
explicit Drive folder id
```

Sync 先执行 folder metadata probe，要求：
- target 存在；
- MIME type = Google Drive folder；
- target 不在 trash。

显式 Shared Drive folder 也支持：folder probe / list / text-blob media read 带 Google Drive 的 all-drives compatibility 参数，但 query 仍严格限定到这个 parent folder，不会因此扩大成 shared drive 全盘扫描。

目标 folder 的 403/404 等失败属于 target failure，不应把已验证 account token 误标成认证失效。

---

## 6. Content truth

在读取任何正文前，provider 都先尊重 Drive 返回的 `capabilities.canDownload`。如果该文件禁止下载/导出，Chengzhu 只保留 metadata-only snapshot，并记录 `DOWNLOAD_RESTRICTED`；不会用失败 export 冒充“正文不可解析”。

### Google Docs

```text
application/vnd.google-apps.document
→ canDownload = true
→ files.export
→ text/plain
→ TEXT_EXPORT_EXCERPT_20K
```

### Google Slides

```text
application/vnd.google-apps.presentation
→ files.export
→ text/plain
→ TEXT_EXPORT_EXCERPT_20K
```

### Google Sheets

```text
application/vnd.google-apps.spreadsheet
→ files.export
→ text/csv
→ FIRST_SHEET_CSV_EXCERPT_20K
→ partial_content = true
```

不能把第一张 sheet CSV 说成完整 spreadsheet。

### Retrieval 与 revision 必须分开

Provider 会完整读取/导出不超过 2MB 的可文本化内容，用完整内容计算本地 `full_content_digest_sha256`；该 digest 进入 snapshot metadata，因此即使文档前 20k 字完全相同、只有尾部变化，也会产生新的 immutable revision。

但 generic connector snapshot 当前只持久化/检索前 20,000 字符：

```text
retrieval_scope = FIRST_20000_CHARS
```

所以：
- `full_content_digest_sha256` 证明 revision identity 覆盖完整读取内容；
- `excerpt` 只代表当前可检索窗口；
- 不得把 Drive v1 provider 描述成“全文长期存储 / 全文检索”；
- 超过 20k 的正文尾部可以改变 revision，但不会自动进入当前 Manual Ask 的检索窗口。

### Common text blobs

```text
text/*
application/json/xml/yaml/sql/javascript
→ files.get?alt=media
→ TEXT_BLOB_EXCERPT_20K
```

### PDF / image / office binary / unsupported

只形成 metadata-only DOCUMENT snapshot：

```text
content_available = false
content_scope = METADATA_ONLY
content_unavailable_reason = UNSUPPORTED_OR_BINARY
```

不会因为“Drive 能访问这个文件”就声称 Chengzhu 已读懂正文。

---

## 7. Completeness gate

每次 folder refresh：
- files.list 必须完整分页；
- 任一页返回 `incompleteSearch=true` 时整次 Sync fail-closed，不保存可能缺项的 folder snapshot；
- 最大 500 个 direct children；
- 超过上限整次失败；
- 不保存“前 500 个”再假装完整；
- 单个文本正文上限 2MB；
- Google Workspace export 或 text blob 超过 2MB 时，该文件降为 `METADATA_ONLY / TEXT_TOO_LARGE`；
- 超大文本不做静默截断后冒充全文，也不会因为一个大文件把同 folder 内其他可读文件整批丢弃。

snapshot excerpt 仍由 integration boundary 做长度与 secret redaction。

---

## 8. Immutable revision truth

同一 Drive file 的不同读取结果按：

```text
connection
+ capability
+ external_kind
+ external_id
+ canonical content hash
```

形成 immutable revisions。

UI 可以看到：
- latest revision；
- historical revision；
- content available；
- partial content；
- metadata only。

Session 只冻结用户显式选择的 snapshot id/content hash。后续再次 Sync 不会静默改写已开始 Session Pack。

---

## 9. Privacy / least privilege truth

当前 scope：

```text
https://www.googleapis.com/auth/drive.readonly
```

这是为了读取用户显式指定 folder 内的既有文件内容。

当前 adapter：
- read-only；
- 无 create/update/delete；
- 无 background polling；
- 无 account-wide mirror；
- 无 Drive write；
- 无自动把所有 snapshot 选入 Space。

真实 Google OAuth verification/consent 与真实账号 replay 是独立 external evidence gate。

官方 API 参考：
- Files list: https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list
- Download/export: https://developers.google.com/workspace/drive/api/guides/manage-downloads
- Export MIME types: https://developers.google.com/workspace/drive/api/guides/ref-export-formats
- OAuth scopes: https://developers.google.com/workspace/drive/api/guides/api-specific-auth

---

## 10. 不允许声明

代码/测试完成后允许：

```text
GOOGLE_DRIVE_ADAPTER_CODE_AVAILABLE = TRUE
GOOGLE_DRIVE_OPT_IN_RUNTIME_AVAILABLE = TRUE
```

没有真实账号 evidence 前禁止：

```text
GOOGLE_DRIVE_ACCOUNT_CONNECTED = TRUE
REAL_DRIVE_DOCUMENT_SYNC_PROVEN = TRUE
REAL_GOOGLE_OAUTH_LIFECYCLE_COMPLETE = TRUE
```
