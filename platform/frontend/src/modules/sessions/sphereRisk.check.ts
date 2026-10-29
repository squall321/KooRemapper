// 구면 위험도 맵 셈(sphereRisk.ts)의 성질 시험 — 프런트에 시험 러너가 없어 tsc 로 옮겨 node 로 돌린다
//
// 돌리기: platform/frontend 에서
//   T=$(mktemp -d) && node_modules/.bin/tsc --outDir "$T" --module commonjs --target es2020 --strict \
//     --skipLibCheck src/modules/sessions/sphereRisk.ts src/modules/sessions/sphereRisk.check.ts && node "$T/sphereRisk.check.js"
import { dirOf, interpolate, levelOf, lonLatGrid, makeField, ratioOf, topN, type Sample, type Vec3 } from './sphereRisk'

let failed = 0
function check(name: string, ok: boolean, detail = ''): void {
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${ok || !detail ? '' : ' — ' + detail}`)
  if (!ok) failed++
}
const near = (a: number, b: number, eps = 1e-9) => Math.abs(a - b) <= eps
const nearV = (a: Vec3, b: Vec3, eps = 1e-9) => a.every((c, i) => near(c, b[i], eps))

// 방향 — 백엔드 `_angle_vec` 과 같은 축
check('위도 90° = +Z', nearV(dirOf(0, 90), [0, 0, 1]))
check('경도 90° = +Y', nearV(dirOf(90, 0), [0, 1, 0]))
check('경도 0° · 위도 0° = +X', nearV(dirOf(0, 0), [1, 0, 0]))
check('경도 ±180° 는 같은 방향', nearV(dirOf(180, 0), dirOf(-180, 0)))
check('위도는 ±90° 로 잘린다', nearV(dirOf(0, 120), [0, 0, 1]))

// 보간
const s = (key: string, lon: number, lat: number, value: number): Sample => ({ key, name: key, lon, lat, value })
const samples = [s('a', 0, 0, 10), s('b', 90, 0, 20), s('c', 180, 0, 30), s('d', -90, 0, 40), s('e', 0, 90, 50), s('f', 0, -90, 60)]
const field = makeField(samples)
check('표본 자리 = 표본 값', samples.every((x) => near(interpolate(field, dirOf(x.lon, x.lat)), x.value)))
const grid = lonLatGrid(field, 10)
const vals = [...grid.values]
check('보간은 표본 범위를 넘지 않는다', vals.every((v) => v >= 10 - 1e-9 && v <= 60 + 1e-9),
      `min ${Math.min(...vals)} max ${Math.max(...vals)}`)
check('격자 크기(10° → 36 × 18)', grid.w === 36 && grid.h === 18)
const mid = interpolate(field, dirOf(45, 0))
check('가운데 값은 이웃 사이', mid > 10 && mid < 60, String(mid))
check('표본이 없으면 NaN', Number.isNaN(interpolate(makeField([]), [1, 0, 0])))

// 같은 방향 표본 — 큰 값
const dup = makeField([s('x1', 30, 10, 3), s('x2', 30, 10, 5), s('y', 120, -20, 1)])
check('같은 방향은 하나로(큰 값)', dup.dirs.length === 2 && near(interpolate(dup, dirOf(30, 10)), 5))
const pole = makeField([s('p1', 0, 90, 2), s('p2', 77, 90, 9)])
check('극점은 경도와 무관하게 한 방향', pole.dirs.length === 1 && near(pole.values[0], 9))

// 허용비 · 판정
check('허용비 = 값 ÷ 허용값', near(ratioOf(10, 20) ?? NaN, 0.5))
check('허용값 0 · 음수 · 빈 값 · NaN 은 비율 없음',
      [0, -1, null, undefined, NaN].every((a) => ratioOf(10, a as number | null | undefined) === null))
check('1.0 은 초과', levelOf(1.0, 0.8) === 'exceed')
check('경고 비율과 같으면 경고', levelOf(0.8, 0.8) === 'warn')
check('경고 비율 아래면 정상', levelOf(0.79, 0.8) === 'ok')
check('비율이 없으면 판정 없음', levelOf(null, 0.8) === null)

// 상위 N — 표본 값 순서, 이름으로 동률을 가른다
const t = topN([s('m', 0, 0, 5), s('k', 0, 0, 9), s('j', 0, 0, 9), s('z', 0, 0, NaN)], 2)
check('상위 N 순서(값 내림 · 이름)', t.map((x) => x.key).join(',') === 'j,k', t.map((x) => x.key).join(','))
check('N 은 표본 수를 넘지 않는다', topN(samples, 50).length === samples.length)

console.log(failed ? `\n${failed} 개 실패` : '\n모두 통과')
// node 타입 없이 — 이 파일은 앱의 tsc -b 검사에도 들어간다(DOM 라이브러리).
if (failed) (globalThis as { process?: { exit(code: number): void } }).process?.exit(1)
