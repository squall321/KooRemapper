// three.js 그림들이 함께 쓰는 작은 도우미 — 물체의 GPU 자원 놓기(3D 구 · CAD 형상 뷰어)
import type * as THREE from 'three'

/** 물체 하나의 GPU 자원을 놓는다 — 글자 스프라이트의 텍스처까지(재질만 놓으면 텍스처가 남는다). */
export function release(o: THREE.Object3D): void {
  const m = o as THREE.Mesh
  m.geometry?.dispose?.()
  const mats = ([] as (THREE.Material | undefined)[]).concat(m.material as THREE.Material | THREE.Material[] | undefined)
  for (const mat of mats) {
    ;(mat as THREE.SpriteMaterial | undefined)?.map?.dispose()
    mat?.dispose()
  }
}
