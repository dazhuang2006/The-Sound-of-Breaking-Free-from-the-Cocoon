/**
 * 等距（2.5D 斜俯视）投影。
 *
 * 世界坐标：16 × 11 的网格，(x, y) 是物体占地的中心。
 * 屏幕坐标：x = (gx - gy) * TILE_W / 2，y = (gx + gy) * TILE_H / 2。
 *
 * 舞台 viewBox 固定，CSS 只做等比缩放，因此「屏幕百分比」与「世界坐标」可以互相换算，
 * HTML 对话气泡才能稳稳地贴在角色头顶。
 */

export const TILE_W = 58
export const TILE_H = 29
export const GRID_W = 16
export const GRID_H = 11

/** 后墙高度（像素），房间是一个斜放的「立体盒子 / 立体岛」。 */
export const WALL_H = 212

/** 舞台视口：覆盖整块地板 + 后墙 + 留白。 */
export const VIEW = { x: -346, y: -246, w: 842, h: 668 }
export const VIEW_BOX = `${VIEW.x} ${VIEW.y} ${VIEW.w} ${VIEW.h}`
export const VIEW_RATIO = VIEW.w / VIEW.h

/** 墙面局部坐标（x 沿墙向右、y 向上为负）→ 屏幕坐标 的变换矩阵。 */
export const WALL_RIGHT_MATRIX = 'matrix(0.894 0.447 0 1 0 0)'
export const WALL_LEFT_MATRIX = 'matrix(-0.894 0.447 0 1 0 0)'

export function isoX(gx, gy) {
  return (gx - gy) * (TILE_W / 2)
}

export function isoY(gx, gy) {
  return (gx + gy) * (TILE_H / 2)
}

export function fromIso(sx, sy) {
  const a = sx / (TILE_W / 2) // gx - gy
  const b = sy / (TILE_H / 2) // gx + gy
  return { x: (a + b) / 2, y: (b - a) / 2 }
}

/** 深度键：越大越靠前，用于画序（远 → 近）。 */
export function depthKey(gx, gy) {
  return gx + gy
}

/** 世界点 → 舞台百分比（给 HTML 气泡定位）。 */
export function worldToPercent(gx, gy, lift = 0) {
  const left = ((isoX(gx, gy) - VIEW.x) / VIEW.w) * 100
  const top = ((isoY(gx, gy) - lift - VIEW.y) / VIEW.h) * 100
  return { left, top }
}

/** 屏幕像素（相对舞台左上角）→ 世界坐标，舞台宽高比与 viewBox 一致所以直接线性换算。 */
export function stagePointToWorld(px, py, width, height) {
  const sx = VIEW.x + (px / width) * VIEW.w
  const sy = VIEW.y + (py / height) * VIEW.h
  return fromIso(sx, sy)
}

export function clampToBounds(x, y, bounds, margin = 0.35) {
  const minX = (bounds?.minX ?? 0.7) + margin
  const maxX = (bounds?.maxX ?? GRID_W - 0.7) - margin
  const minY = (bounds?.minY ?? 0.7) + margin
  const maxY = (bounds?.maxY ?? GRID_H - 0.7) - margin
  return {
    x: Math.max(minX, Math.min(maxX, x)),
    y: Math.max(minY, Math.min(maxY, y))
  }
}
