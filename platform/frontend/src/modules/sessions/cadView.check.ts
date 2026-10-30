// CAD 형상 뷰어 셈(cadView.ts)의 성질 시험 — 프런트에 시험 러너가 없어 tsc 로 옮겨 node 로 돌린다
//
// 돌리기: platform/frontend 에서
//   T=$(mktemp -d) && node_modules/.bin/tsc --outDir "$T" --module commonjs --target es2020 --strict \
//     --skipLibCheck src/modules/sessions/cadView.ts src/modules/sessions/cadView.check.ts && node "$T/cadView.check.js"
import { nodePart, partShade, shadeOf } from './cadView'

let failed = 0
function check(name: string, ok: boolean, detail = ''): void {
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${ok || !detail ? '' : ' — ' + detail}`)
  if (!ok) failed++
}

const parts = [{ pid: 20, glb: { node: 20 } }, { pid: 3, glb: { node: 7 } }, { pid: 9, glb: { node: 2 } }]
const np = nodePart(parts)
check('노드 번호로 파트를 찾는다', np.get(7)?.pid === 3 && np.get(20)?.pid === 20)
check('없는 노드는 파트가 없다', np.get(99) === undefined)
check('같은 노드가 둘이면 앞의 것', nodePart([{ pid: 1, glb: { node: 5 } }, { pid: 2, glb: { node: 5 } }]).get(5)?.pid === 1)

const metrics = { '20': { peak_stress: 400 }, '3': { peak_stress: 100, peak_g: 5 }, '9': { peak_g: 7 } }
const sh = partShade(parts, metrics, 'peak_stress')
check('값이 있는 파트만으로 범위', sh.lo === 100 && sh.hi === 400, `${sh.lo}–${sh.hi}`)
check('값이 없는 파트는 null(회색)', sh.value.get(9) === null)
check('문자열 열쇠의 pid 를 읽는다', sh.value.get(20) === 400)
const none = partShade(parts, null, 'peak_stress')
check('값이 하나도 없으면 범위 0–0', none.lo === 0 && none.hi === 0 && none.value.get(3) === null)
check('NaN · 무한대는 값이 아니다', partShade(parts, { '3': { peak_stress: NaN }, '20': { peak_stress: Infinity } }, 'peak_stress').value.get(3) === null)

check('범위 양 끝은 0 과 1', shadeOf(100, 100, 400) === 0 && shadeOf(400, 100, 400) === 1)
check('범위가 0 이면 가운데', shadeOf(5, 5, 5) === 0.5)
check('범위 밖은 0–1 로 자른다', shadeOf(500, 100, 400) === 1 && shadeOf(0, 100, 400) === 0)

console.log(failed ? `\n${failed} 개 실패` : '\n모두 통과')
// node 타입 없이 — 이 파일은 앱의 tsc -b 검사에도 들어간다(DOM 라이브러리).
if (failed) (globalThis as { process?: { exit(code: number): void } }).process?.exit(1)
