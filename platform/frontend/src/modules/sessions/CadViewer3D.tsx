// 리포트에 붙인 StepForge glb 를 three.js 로 여는 형상 뷰어 — 고른 각도의 파트별 값으로 칠한다(지연 적재, 뷰어 1단계)
import { useEffect, useMemo, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader, type GLTF } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { getReportCase, sessionFileBytes } from '@/shared/api/endpoints'
import type { ReportCad, ReportCadPart } from '@/shared/api/types'
import { nodePart, partShade, shadeOf } from './cadView'
import { release } from './threeUtil'

interface Props {
  reportId: string
  sessionId: string
  cad: ReportCad
  caseKey: string
  caseName: string
  metric: string
  metricLabel: string
  highlightPid: number | null          // 맵에서 고른 파트 — 빨간 모서리선으로 두른다
  colorOf: (t: number) => string       // 0–1 → `rgb(r,g,b)` (맵과 같은 색 띠)
  fmt: (v: number) => string
  legendColors: string[]
  onClose: () => void
}

const GREY = 'rgb(205,205,205)'      // 그 각도에 값이 없는 파트
// 고른 파트는 칠을 바꾸지 않고 모서리선으로 두른다 — 비침(emissive)은 칠과 섞여 범례에 없는 색이 됐다(10-30 화면 확인)
const EDGE = 0xdc2626
const XRAY_OPACITY = 0.18            // 「속 보기」 — 고른 파트 말고는 비친다(휴대폰 꼴은 속 파트가 겉판에 가린다)

interface Stage {
  renderer: THREE.WebGLRenderer
  scene: THREE.Scene
  camera: THREE.PerspectiveCamera
  controls: OrbitControls
  model: THREE.Object3D | null
  axes: THREE.AxesHelper | null
  meshes: Map<number, THREE.Mesh[]>   // pid → 그 파트의 mesh 들
  edges: THREE.LineSegments[]        // 고른 파트의 모서리선(바꿀 때 걷어 낸다)
  render: () => void
}

export default function CadViewer3D(props: Props) {
  const { reportId, sessionId, cad, caseKey, caseName, metric, metricLabel, highlightPid, colorOf, fmt,
          legendColors, onClose } = props
  const hostRef = useRef<HTMLDivElement>(null)
  const stRef = useRef<Stage | null>(null)
  const [loaded, setLoaded] = useState(false)
  const [loadErr, setLoadErr] = useState<string | null>(null)
  const [picked, setPicked] = useState<ReportCadPart | null>(null)
  const [xray, setXray] = useState(false)
  const byNode = useMemo(() => nodePart(cad.parts), [cad.parts])
  const byPid = useMemo(() => new Map(cad.parts.map((p) => [p.pid, p])), [cad.parts])
  const byNodeRef = useRef(byNode)
  byNodeRef.current = byNode
  const byPidRef = useRef(byPid)
  byPidRef.current = byPid
  const kase = useQuery({ queryKey: ['report-case', reportId, caseKey], queryFn: () => getReportCase(reportId, caseKey) })
  const shade = useMemo(() => partShade(cad.parts, kase.data?.parts_metrics, metric), [cad.parts, kase.data, metric])
  const glbId = cad.view.glb[0]?.file_id

  // 한 번 — 렌더러 · 장면 · 빛 · 카메라 · 조작 · 고르기
  useEffect(() => {
    const host = hostRef.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    renderer.setClearColor(0xffffff, 1)
    host.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    // 빛은 칠이 범례 색에 가깝게. three r155+ 는 빛 세기를 물리 단위로 받아 Lambert 밝기가 「색 × 세기 ÷ π」 다 —
    // 세기 0.8 이면 범례 색의 ⅓ 밝기로 칠해져 208 MPa 가 범례에 없는 올리브가 됐다(10-30 화면 확인). 바탕빛 ≈ 0.76π 로
    // 범례 색의 76–100% 에 들게 하고, 방향빛은 모양만 읽히게 둔다.
    scene.add(new THREE.AmbientLight(0xffffff, 2.4))
    const sun = new THREE.DirectionalLight(0xffffff, 1.0)
    scene.add(sun)
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 1e5)
    camera.up.set(0, 0, 1)                       // 리포트 · 맵과 같이 Z 가 위
    const controls = new OrbitControls(camera, renderer.domElement)
    const render = () => {
      sun.position.copy(camera.position)         // 빛은 늘 보는 쪽에서 — 돌려도 그늘 면이 생기지 않는다
      renderer.render(scene, camera)
    }
    controls.addEventListener('change', render)
    const st: Stage = { renderer, scene, camera, controls, model: null, axes: null, meshes: new Map(), edges: [], render }
    stRef.current = st

    const resize = () => {
      const w = host.clientWidth || 560
      const h = Math.round(w * 0.62)
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      render()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(host)
    resize()

    // 누르기(끌기가 아니라) → 맞은 파트
    let down: { x: number; y: number } | null = null
    const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY } }
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) { down = null; return }
      down = null
      if (!st.model) return
      const rect = renderer.domElement.getBoundingClientRect()
      const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1)
      const ray = new THREE.Raycaster()
      ray.setFromCamera(ndc, camera)
      // mesh 만 — 고른 파트의 모서리선(자식 LineSegments)이 먼저 맞으면 파트 번호가 없어 「안 고름」 이 됐다(10-30 화면 확인).
      // 「속 보기」 면 비친 파트를 지나 처음 맞은 안 비친 파트를 고른다
      const hits = ray.intersectObject(st.model, true).filter((h) => (h.object as THREE.Mesh).isMesh)
      const hit = hits.find((h) => ((h.object as THREE.Mesh).material as THREE.Material).opacity >= 1) ?? hits[0]
      const pid = hit?.object.userData.pid as number | null | undefined
      setPicked(pid != null ? byPidRef.current.get(pid) ?? null : null)
    }
    renderer.domElement.addEventListener('pointerdown', onDown)
    renderer.domElement.addEventListener('pointerup', onUp)

    return () => {
      ro.disconnect()
      renderer.domElement.removeEventListener('pointerdown', onDown)
      renderer.domElement.removeEventListener('pointerup', onUp)
      controls.dispose()
      scene.traverse(release)
      renderer.dispose()
      host.removeChild(renderer.domElement)
      stRef.current = null
    }
  }, [])

  // glb 받기 → 노드를 파트에 잇고 m → mm 로 놓는다
  useEffect(() => {
    const st = stRef.current
    if (!st || glbId == null) return
    let alive = true
    setLoaded(false)
    setLoadErr(null)
    sessionFileBytes(sessionId, glbId)
      .then((buf) => new Promise<GLTF>((res, rej) => new GLTFLoader().parse(buf, '', res, rej)))
      .then((gltf) => {
        if (!alive || stRef.current !== st) {
          gltf.scene.traverse(release)
          return
        }
        for (const old of [st.model, st.axes]) {
          if (old) {
            st.scene.remove(old)
            old.traverse(release)
          }
        }
        st.edges = []
        const model = gltf.scene
        model.scale.setScalar(1000)              // glb 는 m, FE 덱 · 리포트는 mm
        const meshes = new Map<number, THREE.Mesh[]>()
        model.traverse((o) => {
          const mesh = o as THREE.Mesh
          if (!mesh.isMesh) return
          let node: number | undefined
          for (let x: THREE.Object3D | null = mesh; x && node === undefined; x = x.parent) {
            node = gltf.parser.associations.get(x)?.nodes
          }
          const part = node !== undefined ? byNodeRef.current.get(node) : undefined
          mesh.userData.pid = part?.pid ?? null
          if (part) meshes.set(part.pid, [...(meshes.get(part.pid) ?? []), mesh])
          // glb 재질 대신 칠할 재질 — 놓지 않으면 GPU 에 남는다
          const old = ([] as THREE.Material[]).concat(mesh.material as THREE.Material | THREE.Material[])
          mesh.material = new THREE.MeshLambertMaterial({ color: GREY, side: THREE.DoubleSide, transparent: true })
          old.forEach((m) => m.dispose())
        })
        st.scene.add(model)
        st.model = model
        st.meshes = meshes
        const box = new THREE.Box3().setFromObject(model)
        const size = box.getSize(new THREE.Vector3()).length() || 1
        const center = box.getCenter(new THREE.Vector3())
        const axes = new THREE.AxesHelper(size * 0.15)
        axes.position.copy(box.min)
        st.scene.add(axes)
        st.axes = axes
        st.camera.near = size / 1000
        st.camera.far = size * 100
        st.camera.updateProjectionMatrix()
        st.controls.target.copy(center)
        st.camera.position.copy(center.clone().add(new THREE.Vector3(1, -1, 0.7).normalize().multiplyScalar(size * 1.6)))
        st.controls.update()
        setLoaded(true)
      })
      .catch((e: unknown) => { if (alive) setLoadErr(e instanceof Error ? e.message : String(e)) })
    return () => { alive = false }
  }, [sessionId, glbId])

  // 칠 — 그 각도의 파트별 값 · 맵에서 고른 파트(모서리선) · 속 보기(비침)
  useEffect(() => {
    const st = stRef.current
    if (!st || !loaded) return
    for (const e of st.edges) {
      e.parent?.remove(e)
      release(e)
    }
    st.edges = []
    for (const [pid, meshes] of st.meshes) {
      const v = shade.value.get(pid)
      const color = v == null ? GREY : colorOf(shadeOf(v, shade.lo, shade.hi))
      const see = !xray || pid === highlightPid
      for (const m of meshes) {
        const mat = m.material as THREE.MeshLambertMaterial
        mat.color.setStyle(color, THREE.SRGBColorSpace)
        mat.opacity = see ? 1 : XRAY_OPACITY
        mat.depthWrite = see
        if (pid === highlightPid) {
          const line = new THREE.LineSegments(new THREE.EdgesGeometry(m.geometry, 25), new THREE.LineBasicMaterial({ color: EDGE }))
          m.add(line)                              // mesh 의 자식이라 m → mm 배율을 함께 받는다
          st.edges.push(line)
        }
      }
    }
    st.render()
  }, [shade, loaded, highlightPid, colorOf, xray])

  const pickedValue = picked ? shade.value.get(picked.pid) : undefined
  const nPainted = [...shade.value.values()].filter((v) => v != null).length
  const deck = cad.deck?.file ? `${cad.deck.file}${cad.deck.sha256 ? ` (${cad.deck.sha256.slice(0, 12)})` : ''}` : '–'

  return (
    <div className="space-y-1 border border-border rounded p-2">
      <div className="flex items-center gap-2 text-[11px]">
        <b>형상 — {caseName}</b>
        <span className="text-muted">{metricLabel} · 이 각도의 파트별 최대값으로 칠함</span>
        <button type="button" className="ml-auto underline text-muted" onClick={onClose}>닫기</button>
      </div>
      <div ref={hostRef} className="w-full border border-border rounded overflow-hidden" style={{ maxWidth: 720, cursor: 'grab' }} />
      {loadErr && <div className="text-[11px] text-red-600">glb 를 열지 못했다 — {loadErr}</div>}
      {!loaded && !loadErr && <div className="text-[11px] text-muted">glb 받는 중…</div>}
      {kase.isError && <div className="text-[11px] text-red-600">이 각도의 파트 값을 받지 못했다 — 형상만 회색으로 보인다</div>}
      <div className="flex items-center gap-2 text-[10px] text-muted">
        <span>{fmt(shade.lo)}</span>
        <div className="flex h-2 w-40">
          {legendColors.map((c, i) => <div key={i} className="flex-1" style={{ background: c }} />)}
        </div>
        <span>{fmt(shade.hi)}</span>
        <span>· 회색 = 이 각도 값 없음 · 빨간 모서리 = 맵에서 고른 파트 · 칠한 파트 {nPainted}/{cad.parts.length}</span>
        <label className="ml-auto flex items-center gap-1 text-fg">
          <input type="checkbox" checked={xray} onChange={(e) => setXray(e.target.checked)} /> 속 보기(고른 파트만 남기고 비침)
        </label>
      </div>
      <div className="text-[11px]">
        {picked
          ? <>파트 <b>{picked.name ?? `PID ${picked.pid}`}</b> (PID {picked.pid}) — {metricLabel} {pickedValue != null ? <b>{fmt(pickedValue)}</b> : '값 없음'}</>
          : <span className="text-muted">끌어서 돌리기 · 휠로 확대 · 파트를 누르면 이름과 값이 나온다</span>}
      </div>
      <div className="text-[10px] text-muted">
        묶음 {cad.key.slice(0, 12)} · 덱 {deck} · 과제 {cad.cad_project?.name ?? '–'} · 파트 {cad.n_parts}(리포트와 겹침 {cad.pids_matched})
        · 가중치 행 {cad.rows.toLocaleString()} · nnz {cad.nnz.toLocaleString()} — 받는 쪽 검사 통과
      </div>
      {cad.warnings.length > 0 && <div className="text-[10px] text-amber-600">{cad.warnings.join(' · ')}</div>}
      <div className="text-[10px] text-amber-600">
        덱 좌표 그대로의 형상이다 — 각도별 자세(바닥 · 낙하 방향)와 변형 프레임은 S1(C-3)이 운영에 들어오면 붙는다.
      </div>
    </div>
  )
}
