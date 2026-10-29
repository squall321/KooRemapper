// 전각도 낙하 위험도를 3D 구에 그리는 three.js 그림 — 보간 면색 · 표본 점 · 임계 고리 · 고르기 · PNG(지연 적재)
import { useEffect, useRef } from 'react'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { dirOf, interpolate, type Field, type Level } from './sphereRisk'

export interface GlobePoint {
  key: string
  name: string
  lon: number
  lat: number
  shown: number          // 색을 정하는 값(허용값이 있으면 허용비, 없으면 값)
  level: Level | null
  label: string          // 마우스를 올렸을 때 · 고른 점 글자
}

interface Props {
  points: GlobePoint[]
  field: Field | null    // null 이면 면을 회색으로(채움 끔)
  fieldToShown: (v: number) => number
  colorOf: (shown: number) => string   // `rgb(r,g,b)`
  selectedKey: string | null
  onSelect: (key: string) => void
  caption: string
  legend: { lo: string; hi: string; unit: string; colors: string[] }
  fileBase: string
}

const MARKER_R = 0.026
const RING_R = 0.05

/** 글자 스프라이트 — 캔버스 폭을 글자에 맞춘다(고정 폭이면 긴 각도 이름이 잘린다). `boxed` 면 흰 바탕을 깐다. */
function textSprite(text: string, color = '#555', height = 0.1, boxed = false): THREE.Sprite {
  const font = '600 32px sans-serif'
  const g0 = document.createElement('canvas').getContext('2d')!
  g0.font = font
  const w = Math.ceil(g0.measureText(text).width) + 16
  const h = 44
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  const g = c.getContext('2d')!
  if (boxed) {
    g.fillStyle = 'rgba(255,255,255,0.88)'
    g.fillRect(0, 0, w, h)
  }
  g.font = font
  g.fillStyle = color
  g.textAlign = 'center'
  g.textBaseline = 'middle'
  g.fillText(text, w / 2, h / 2)
  const tex = new THREE.CanvasTexture(c)
  tex.colorSpace = THREE.SRGBColorSpace
  const sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }))
  sp.scale.set((height * w) / h, height, 1)
  return sp
}

/** 물체 하나의 GPU 자원을 놓는다 — 글자 스프라이트의 텍스처까지(재질만 놓으면 텍스처가 남는다). */
function release(o: THREE.Object3D): void {
  const m = o as THREE.Mesh
  m.geometry?.dispose?.()
  const mats = ([] as (THREE.Material | undefined)[]).concat(m.material as THREE.Material | THREE.Material[] | undefined)
  for (const mat of mats) {
    ;(mat as THREE.SpriteMaterial | undefined)?.map?.dispose()
    mat?.dispose()
  }
}

/** 점 v 에서 구에 닿는 평면 위의 원(고리). */
function ringAt(v: THREE.Vector3, r: number, material: THREE.LineBasicMaterial | THREE.LineDashedMaterial): THREE.LineLoop {
  const u = new THREE.Vector3().crossVectors(v, Math.abs(v.z) < 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(1, 0, 0)).normalize()
  const w = new THREE.Vector3().crossVectors(v, u).normalize()
  const pts: THREE.Vector3[] = []
  for (let i = 0; i < 48; i++) {
    const a = (i / 48) * Math.PI * 2
    pts.push(v.clone().multiplyScalar(1.012).addScaledVector(u, Math.cos(a) * r).addScaledVector(w, Math.sin(a) * r))
  }
  const loop = new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(pts), material)
  if (material instanceof THREE.LineDashedMaterial) loop.computeLineDistances()
  return loop
}

export default function SphereGlobe3D(props: Props) {
  const { points, field, fieldToShown, colorOf, selectedKey, onSelect, caption, legend, fileBase } = props
  const hostRef = useRef<HTMLDivElement>(null)
  const stateRef = useRef<{
    renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera
    controls: OrbitControls; dynamic: THREE.Group; markers: THREE.InstancedMesh | null; keys: string[]; render: () => void
  } | null>(null)
  const selectRef = useRef(onSelect)
  selectRef.current = onSelect

  // 한 번 — 렌더러 · 장면 · 카메라 · 조작 · 축 글자
  useEffect(() => {
    const host = hostRef.current!
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true })
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1))
    renderer.setClearColor(0xffffff, 1)
    host.appendChild(renderer.domElement)
    const scene = new THREE.Scene()
    const camera = new THREE.PerspectiveCamera(35, 1, 0.1, 50)
    camera.up.set(0, 0, 1)                       // 리포트 틀은 Z 가 위(위도 90° = +Z)
    // 거리 ≈ 5 — 구가 화면 높이의 6할쯤이라 ±Z 글자(반지름 1.25)까지 들어온다(4 남짓이면 +Z 가 화면 밖이었다)
    camera.position.set(3.2, -3.2, 2.2)
    const controls = new OrbitControls(camera, renderer.domElement)
    controls.enablePan = false
    controls.minDistance = 2.5
    controls.maxDistance = 10
    const render = () => renderer.render(scene, camera)
    controls.addEventListener('change', render)

    const axes: [string, THREE.Vector3][] = [
      ['+X', new THREE.Vector3(1, 0, 0)], ['-X', new THREE.Vector3(-1, 0, 0)],
      ['+Y', new THREE.Vector3(0, 1, 0)], ['-Y', new THREE.Vector3(0, -1, 0)],
      ['+Z', new THREE.Vector3(0, 0, 1)], ['-Z', new THREE.Vector3(0, 0, -1)],
    ]
    for (const [t, v] of axes) {
      const sp = textSprite(t)
      sp.position.copy(v.clone().multiplyScalar(1.25))
      scene.add(sp)
    }
    // 경위선(30°) — 방향을 읽는 눈금
    const grat: THREE.Vector3[] = []
    for (let lat = -60; lat <= 60; lat += 30) {
      for (let lon = -180; lon < 180; lon += 4) {
        const a = dirOf(lon, lat), b = dirOf(lon + 4, lat)
        grat.push(new THREE.Vector3(...a).multiplyScalar(1.003), new THREE.Vector3(...b).multiplyScalar(1.003))
      }
    }
    for (let lon = -180; lon < 180; lon += 30) {
      for (let lat = -90; lat < 90; lat += 4) {
        const a = dirOf(lon, lat), b = dirOf(lon, lat + 4)
        grat.push(new THREE.Vector3(...a).multiplyScalar(1.003), new THREE.Vector3(...b).multiplyScalar(1.003))
      }
    }
    scene.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(grat),
      new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.55 })))

    const dynamic = new THREE.Group()
    scene.add(dynamic)
    const st = { renderer, scene, camera, controls, dynamic, markers: null as THREE.InstancedMesh | null,
                 keys: [] as string[], render }
    stateRef.current = st

    const resize = () => {
      const w = host.clientWidth || 480
      const h = Math.round(w * 0.75)
      renderer.setSize(w, h)
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      render()
    }
    const ro = new ResizeObserver(resize)
    ro.observe(host)
    resize()

    // 누르기(끌기가 아니라) → 가장 가까운 표본 점
    let down: { x: number; y: number } | null = null
    const onDown = (e: PointerEvent) => { down = { x: e.clientX, y: e.clientY } }
    const onUp = (e: PointerEvent) => {
      if (!down || Math.hypot(e.clientX - down.x, e.clientY - down.y) > 4) { down = null; return }
      down = null
      const rect = renderer.domElement.getBoundingClientRect()
      const ndc = new THREE.Vector2(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1)
      const ray = new THREE.Raycaster()
      ray.setFromCamera(ndc, camera)
      const hit = st.markers ? ray.intersectObject(st.markers, false)[0] : undefined
      const key = hit?.instanceId != null ? st.keys[hit.instanceId] : undefined
      if (key) selectRef.current(key)
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
      stateRef.current = null
    }
  }, [])

  // 데이터가 바뀔 때 — 면색 · 점 · 고리를 다시 짓는다
  useEffect(() => {
    const st = stateRef.current
    if (!st) return
    for (const o of [...st.dynamic.children]) {
      st.dynamic.remove(o)
      release(o)
    }
    st.markers = null
    st.keys = []

    const geo = new THREE.SphereGeometry(1, 120, 60)
    const pos = geo.getAttribute('position')
    const colors = new Float32Array(pos.count * 3)
    const tmp = new THREE.Color()
    for (let i = 0; i < pos.count; i++) {
      // SphereGeometry 는 Y 가 극이다 — 리포트 틀(Z 가 극)로 돌려 놓는다
      const x = pos.getX(i), y = pos.getY(i), z = pos.getZ(i)
      pos.setXYZ(i, x, -z, y)
      if (field) {
        const v = interpolate(field, [x, -z, y])
        tmp.setStyle(colorOf(fieldToShown(v)), THREE.SRGBColorSpace)
      } else {
        tmp.setRGB(0.93, 0.93, 0.93, THREE.SRGBColorSpace)
      }
      colors[i * 3] = tmp.r
      colors[i * 3 + 1] = tmp.g
      colors[i * 3 + 2] = tmp.b
    }
    pos.needsUpdate = true
    geo.computeVertexNormals()
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3))
    st.dynamic.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ vertexColors: true })))

    const exceedMat = new THREE.LineBasicMaterial({ color: 0x111111 })
    const warnMat = new THREE.LineDashedMaterial({ color: 0x333333, dashSize: 0.012, gapSize: 0.01 })
    const selMat = new THREE.LineBasicMaterial({ color: 0xe11d48 })
    // 표본 점은 인스턴스 하나로 — 각도가 수천이어도 그리기 호출이 둘(점 · 테두리)이다
    const n = points.length
    const ball = new THREE.SphereGeometry(MARKER_R, 12, 8)
    const dots = new THREE.InstancedMesh(ball, new THREE.MeshBasicMaterial(), n)
    // 흰 테두리 — 2D 와 같다. 표본 자리의 면 색은 표본 색과 같아(보간이 표본에서 정확하다) 테두리 없이는 점이 묻힌다
    const halo = new THREE.InstancedMesh(new THREE.SphereGeometry(MARKER_R * 1.35, 12, 8),
                                         new THREE.MeshBasicMaterial({ color: 0xffffff }), n)
    const mtx = new THREE.Matrix4()
    points.forEach((p, i) => {
      const v = new THREE.Vector3(...dirOf(p.lon, p.lat))
      dots.setMatrixAt(i, mtx.makeTranslation(v.x * 1.024, v.y * 1.024, v.z * 1.024))
      halo.setMatrixAt(i, mtx.makeTranslation(v.x * 1.012, v.y * 1.012, v.z * 1.012))
      dots.setColorAt(i, new THREE.Color().setStyle(colorOf(p.shown), THREE.SRGBColorSpace))
    })
    dots.instanceMatrix.needsUpdate = true
    halo.instanceMatrix.needsUpdate = true
    if (dots.instanceColor) dots.instanceColor.needsUpdate = true
    st.dynamic.add(halo, dots)
    st.markers = dots
    st.keys = points.map((p) => p.key)
    for (const p of points) {
      const v = new THREE.Vector3(...dirOf(p.lon, p.lat))
      if (p.level === 'exceed') st.dynamic.add(ringAt(v, RING_R, exceedMat))
      else if (p.level === 'warn') st.dynamic.add(ringAt(v, RING_R, warnMat))
      if (p.key === selectedKey) {
        st.dynamic.add(ringAt(v, RING_R * 1.6, selMat))
        const sp = textSprite(p.label, '#e11d48', 0.09, true)
        sp.position.copy(v.clone().multiplyScalar(1.18))
        st.dynamic.add(sp)
      }
    }
    st.render()
  }, [points, field, fieldToShown, colorOf, selectedKey])

  // 고른 각도로 카메라를 돌린다(거리는 그대로)
  useEffect(() => {
    const st = stateRef.current
    const p = points.find((x) => x.key === selectedKey)
    if (!st || !p) return
    const dist = st.camera.position.length()
    st.camera.position.copy(new THREE.Vector3(...dirOf(p.lon, p.lat)).multiplyScalar(dist))
    st.controls.update()
    st.render()
  }, [selectedKey, points])

  const exportPng = () => {
    const st = stateRef.current
    if (!st) return
    st.render()
    const src = st.renderer.domElement
    const capH = 34, legH = 46
    const out = document.createElement('canvas')
    out.width = src.width
    out.height = src.height + capH + legH
    const g = out.getContext('2d')!
    g.fillStyle = '#fff'
    g.fillRect(0, 0, out.width, out.height)
    g.fillStyle = '#333'
    g.font = '600 18px sans-serif'
    g.textAlign = 'center'
    g.fillText(caption, out.width / 2, 23)
    g.drawImage(src, 0, capH)
    const lw = Math.min(360, out.width - 40), lx = (out.width - lw) / 2, ly = capH + src.height + 8
    legend.colors.forEach((c, i) => {
      g.fillStyle = c
      g.fillRect(lx + (i * lw) / legend.colors.length, ly, lw / legend.colors.length + 1, 12)
    })
    g.fillStyle = '#666'
    g.font = '13px sans-serif'
    g.textAlign = 'left'
    g.fillText(legend.lo, lx, ly + 30)
    g.textAlign = 'center'
    g.fillText(legend.unit, lx + lw / 2, ly + 30)
    g.textAlign = 'right'
    g.fillText(legend.hi, lx + lw, ly + 30)
    out.toBlob((b) => {
      if (!b) return
      const a = document.createElement('a')
      a.href = URL.createObjectURL(b)
      a.download = `${fileBase}_3d.png`
      a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 2000)
    }, 'image/png')
  }

  return (
    <div className="space-y-1">
      <div className="text-center text-[11px] font-semibold text-fg">{caption}</div>
      <div ref={hostRef} className="w-full border border-border rounded overflow-hidden" style={{ maxWidth: 560, cursor: 'grab' }} />
      <div className="flex items-center gap-2 text-[10px] text-muted">
        <span>끌어서 돌리기 · 휠로 확대 · 점을 누르면 고른다</span>
        <button type="button" className="underline" onClick={exportPng}>PNG</button>
      </div>
    </div>
  )
}
