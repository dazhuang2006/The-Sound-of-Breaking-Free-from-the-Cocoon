/**
 * 网格 A* 寻路：点击地面后让小朋友「走过去」，而不是瞬移。
 *
 * - 0.5 世界单位一个格子（32 × 22），完全够用且每帧成本可忽略；
 * - 家具按占地矩形外扩「身体半径」，孩子不会穿模；
 * - 找到路径后做一次视线裁剪（string pulling），走起来是直的，不是一格一格拐。
 */

const CELL = 0.5
const RADIUS = 0.42
const SAMPLE = 0.14

export function createNav(scene) {
  const bounds = scene.bounds || { minX: 0.7, maxX: 15.3, minY: 0.7, maxY: 10.3 }
  const cols = Math.ceil(16 / CELL)
  const rows = Math.ceil(11 / CELL)
  const solids = (scene.props || [])
    .filter((prop) => prop.solid)
    .map((prop) => ({
      x0: prop.x - prop.w / 2 - RADIUS,
      x1: prop.x + prop.w / 2 + RADIUS,
      y0: prop.y - prop.h / 2 - RADIUS,
      y1: prop.y + prop.h / 2 + RADIUS
    }))

  function inBounds(x, y) {
    return x >= bounds.minX && x <= bounds.maxX && y >= bounds.minY && y <= bounds.maxY
  }

  function blocked(x, y) {
    for (const s of solids) {
      if (x > s.x0 && x < s.x1 && y > s.y0 && y < s.y1) return true
    }
    return false
  }

  function walkable(x, y) {
    return inBounds(x, y) && !blocked(x, y)
  }

  function cellOf(x, y) {
    const col = Math.max(0, Math.min(cols - 1, Math.floor(x / CELL)))
    const row = Math.max(0, Math.min(rows - 1, Math.floor(y / CELL)))
    return { col, row }
  }

  function centerOf(col, row) {
    return { x: (col + 0.5) * CELL, y: (row + 0.5) * CELL }
  }

  function cellWalkable(col, row) {
    if (col < 0 || row < 0 || col >= cols || row >= rows) return false
    const p = centerOf(col, row)
    return walkable(p.x, p.y)
  }

  /**
   * 目标落在柜子/桌子里时，找离它最近的可行走格子。
   *
   * 注意：不能只判断「这个点能不能站」，还要判断「这个点所在的格子能不能走」——
   * 站在桌子边缘的点虽然合法，但格子中心仍在桌子里，A* 永远到不了，人就会站着不动。
   */
  function nearestFree(x, y, maxRing = 14) {
    const exact = cellOf(x, y)
    if (cellWalkable(exact.col, exact.row)) {
      return walkable(x, y) ? { x, y } : centerOf(exact.col, exact.row)
    }
    const { col, row } = exact
    for (let ring = 1; ring <= maxRing; ring += 1) {
      let best = null
      let bestDist = Infinity
      for (let dc = -ring; dc <= ring; dc += 1) {
        for (let dr = -ring; dr <= ring; dr += 1) {
          if (Math.abs(dc) !== ring && Math.abs(dr) !== ring) continue
          if (!cellWalkable(col + dc, row + dr)) continue
          const p = centerOf(col + dc, row + dr)
          const dist = (p.x - x) ** 2 + (p.y - y) ** 2
          if (dist < bestDist) {
            best = p
            bestDist = dist
          }
        }
      }
      if (best) return best
    }
    return null
  }

  /** 两点之间能不能直着走（用于裁剪路径）。 */
  function lineFree(a, b) {
    const dist = Math.hypot(b.x - a.x, b.y - a.y)
    const steps = Math.max(1, Math.ceil(dist / SAMPLE))
    for (let i = 0; i <= steps; i += 1) {
      const t = i / steps
      if (!walkable(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)) return false
    }
    return true
  }

  function smooth(points) {
    if (points.length <= 2) return points
    const out = [points[0]]
    let index = 0
    while (index < points.length - 1) {
      let next = points.length - 1
      for (; next > index + 1; next -= 1) {
        if (lineFree(points[index], points[next])) break
      }
      out.push(points[next])
      index = next
    }
    return out
  }

  function findPath(from, to) {
    const start = nearestFree(from.x, from.y)
    if (!start) return []
    const startCell = cellOf(start.x, start.y)
    if (!cellWalkable(startCell.col, startCell.row)) return []

    const goal = nearestFree(to.x, to.y)
    if (!goal) return []
    const goalCell = cellOf(goal.x, goal.y)

    if (startCell.col === goalCell.col && startCell.row === goalCell.row) {
      return [start, goal]
    }

    const size = cols * rows
    const gScore = new Float64Array(size).fill(Infinity)
    const fScore = new Float64Array(size).fill(Infinity)
    const cameFrom = new Int32Array(size).fill(-1)
    const closed = new Uint8Array(size)
    const startIndex = startCell.row * cols + startCell.col
    const goalIndex = goalCell.row * cols + goalCell.col
    gScore[startIndex] = 0
    fScore[startIndex] = heuristic(startCell, goalCell)

    const open = [startIndex]
    const inOpen = new Uint8Array(size)
    inOpen[startIndex] = 1

    while (open.length) {
      let best = 0
      for (let i = 1; i < open.length; i += 1) {
        if (fScore[open[i]] < fScore[open[best]]) best = i
      }
      const current = open.splice(best, 1)[0]
      inOpen[current] = 0
      if (current === goalIndex) {
        const cells = []
        let node = current
        while (node !== -1) {
          cells.push(centerOf(node % cols, Math.floor(node / cols)))
          node = cameFrom[node]
        }
        cells.reverse()
        const points = [start, ...cells.slice(1)]
        points[points.length - 1] = goal
        return smooth(points)
      }
      closed[current] = 1
      const col = current % cols
      const row = Math.floor(current / cols)
      for (const [dc, dr] of NEIGHBOURS) {
        const nc = col + dc
        const nr = row + dr
        if (!cellWalkable(nc, nr)) continue
        const neighbour = nr * cols + nc
        if (closed[neighbour]) continue
        const step = dc && dr ? 1.4142 : 1
        const tentative = gScore[current] + step
        if (tentative >= gScore[neighbour]) continue
        cameFrom[neighbour] = current
        gScore[neighbour] = tentative
        fScore[neighbour] = tentative + heuristic({ col: nc, row: nr }, goalCell)
        if (!inOpen[neighbour]) {
          inOpen[neighbour] = 1
          open.push(neighbour)
        }
      }
    }
    return []
  }

  return { findPath, nearestFree, walkable, lineFree, bounds }
}

const NEIGHBOURS = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
  [1, 1],
  [1, -1],
  [-1, 1],
  [-1, -1]
]

function heuristic(a, b) {
  const dx = Math.abs(a.col - b.col)
  const dy = Math.abs(a.row - b.row)
  return (dx + dy) + (1.4142 - 2) * Math.min(dx, dy)
}
