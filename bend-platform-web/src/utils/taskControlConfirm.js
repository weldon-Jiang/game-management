import { ElMessageBox } from 'element-plus'

const CONFIRM_OPTIONS = {
  confirmButtonText: '确定',
  cancelButtonText: '取消',
  type: 'warning',
  distinguishCancelAndClose: true
}

/**
 * 运行中串流任务终止二次确认（与 Agent 关窗语义一致）。
 */
export async function confirmTerminateStreamingTask() {
  await ElMessageBox.confirm(
    '终止将结束串流任务与自动化，并关闭 Agent 端串流窗口，是否继续？',
    '终止任务',
    CONFIRM_OPTIONS
  )
}

/**
 * 待执行（pending）任务取消二次确认。
 */
export async function confirmCancelPendingTask() {
  await ElMessageBox.confirm(
    '取消后该任务将不再执行，是否继续？',
    '取消任务',
    CONFIRM_OPTIONS
  )
}

/** ElMessageBox 用户点取消/关闭时抛出的标记。 */
export function isConfirmDismissed(error) {
  return error === 'cancel' || error === 'close'
}
