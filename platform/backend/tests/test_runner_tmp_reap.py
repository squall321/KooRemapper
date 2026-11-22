# 잡이 끝날 때 작업 폴더에서 주인 없는 오래된 바이너리 임시 파일(`*.kr_tmp_*`)만 치우는지 보는 시험(3차 4판 L-13)
"""주인 없는 임시 파일 치우기 (2026-11-22 · 미룬 결함 3차 4판 L-13).

취소 · 시간 초과(SIGKILL)된 잡이 남긴 `*.kr_tmp_*` 는 바이너리의 다음 실행이 같은 산출 · 같은 호스트 · pid 이름공간일 때만 치웠다 —
실행기로 계산 노드에서 돈 잡 · 다른 산출 이름이면 영영 남았다. 이제 잡이 끝날 때마다 작업 폴더에서 10 분 넘게 건드리지 않은 것을 지운다.
지금 쓰는 중(올리기 검사 modelmeta 가 같은 폴더에서 돈다)인 새 임시 파일 · 표지 없는 파일은 그대로다.
"""
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.worker.runner_loop import _TMP_ORPHAN_AGE_SEC, reap_orphan_tmp  # noqa: E402


def _touch(p: Path, age: float, now: float) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("x")
    os.utime(p, (now - age, now - age))
    return p


def test_old_tmp_files_go_and_fresh_or_unmarked_stay(tmp_path):
    now = 2_000_000_000.0
    old = _TMP_ORPHAN_AGE_SEC + 5
    gone = [
        _touch(tmp_path / ".kr_tmp_0a1b2c3d_4242_1f_1_9e8d7c6b.k", old, now),         # staged_write 의 반쯤 쓴 산출
        _touch(tmp_path / ".kr_tmp_lock_9e8d7c6b", old, now),                         # 그 잠금
        _touch(tmp_path / "sub" / ".m.kr_tmp_flat_20261122_1.k", old, now),           # 하위 폴더의 펼친 덱
        _touch(tmp_path / "box.kr_tmp_pol1_2.msh", old, now),                         # meshfix polish 왕복
    ]
    stay = [
        _touch(tmp_path / ".kr_tmp_fresh_1.k", 30, now),                             # 지금 쓰는 중일 수 있다
        _touch(tmp_path / "box_out.k", old, now),                                      # 산출(표지 없음)
        _touch(tmp_path / "box__mf.log", old, now),                                    # meshfix 가 일부러 남긴 로그
    ]
    got = reap_orphan_tmp(tmp_path, now=now)
    assert sorted(got) == sorted(p.relative_to(tmp_path).as_posix() for p in gone)
    assert not any(p.exists() for p in gone)
    assert all(p.exists() for p in stay)


def test_missing_dir_is_quiet(tmp_path):
    assert reap_orphan_tmp(tmp_path / "nope") == []
