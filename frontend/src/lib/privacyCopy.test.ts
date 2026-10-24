import { describe, expect, it } from 'vitest'

import { COACH_LAN_COPY, LOCAL_DATA_COPY, SHARE_PRIVACY_COPY } from './privacyCopy'

// These strings are promises, not decoration. If someone shortens one for layout
// reasons, the guarantee it carried has to be re-earned somewhere else.
describe('privacy copy keeps its promises', () => {
  it('share privacy never promises undetectability', () => {
    expect(SHARE_PRIVACY_COPY).toContain('不是安全')
    expect(SHARE_PRIVACY_COPY).toContain('不可检测')
  })

  it('local data is described as plaintext, with disk encryption asked for', () => {
    expect(LOCAL_DATA_COPY).toContain('明文')
    expect(LOCAL_DATA_COPY).toMatch(/BitLocker|FileVault/)
  })

  it('the coach listener is disclosed as a LAN port', () => {
    expect(COACH_LAN_COPY).toContain('18180')
    expect(COACH_LAN_COPY).toContain('局域网')
    expect(COACH_LAN_COPY).toContain('token')
  })
})
