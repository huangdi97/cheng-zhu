// User-facing privacy copy, kept in one place so the promises can be asserted in a
// test instead of drifting per screen.

export const SHARE_PRIVACY_COPY =
  '用于减少成竹中的私人资料意外出现在受支持的屏幕共享或录制路径中。不同系统和捕获方式行为不同，这不是安全或“不可检测”保证。'

export const LOCAL_DATA_COPY =
  '上传的原始简历文件由当前 Windows 账户加密保护（DPAPI）；简历文本、目标与对话记录仍以明文 SQLite 保存在本机数据目录，不做云端同步。建议开启系统磁盘加密（BitLocker / FileVault）。'

export const COACH_LAN_COPY =
  '真人教练模式开启时，本机会在 18180 端口向局域网提供受限的教练页（需一次性 token），会话结束后关闭；其余服务只监听本机回环地址。'
