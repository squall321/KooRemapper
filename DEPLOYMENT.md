# KooRemapper 배포 가이드

다른 컴퓨터에 KooRemapper를 설치하는 방법입니다.

---

## 🚀 빠른 배포 (권장)

KooRemapper는 **정적 링크**로 빌드되어 실행파일 하나만 복사하면 됩니다.

### Windows

```cmd
# 1. 실행파일 복사
KooRemapper.exe → C:\Tools\KooRemapper.exe

# 2. PATH 추가 (선택)
# 시스템 환경 변수에 C:\Tools 추가

# 3. 실행 테스트
KooRemapper.exe --help
```

### Linux / macOS

```bash
# 1. 실행파일 복사
sudo cp KooRemapper /usr/local/bin/

# 2. 실행 권한
sudo chmod +x /usr/local/bin/KooRemapper

# 3. 실행 테스트
KooRemapper --help
```

---

## 📦 전체 패키지 배포

### 배포 패키지 구성

```
KooRemapper_v1.0.0/
├── KooRemapper.exe          # 실행파일 (Windows)
├── KooRemapper              # 실행파일 (Linux/macOS)
├── README.md                # 사용 설명서
├── examples/                # 예제 파일
│   ├── curved.yaml
│   ├── vardens.yaml
│   └── simple_bent.k
└── docs/                    # 추가 문서
    └── DEPLOYMENT.md
```

### 배포 패키지 생성 (Windows)

```cmd
cd D:\KooRemapper

# 배포 폴더 생성
mkdir KooRemapper_Package
cd KooRemapper_Package

# 실행파일 복사
copy ..\build\bin\Release\KooRemapper.exe .

# 문서 복사
copy ..\README.md .
copy ..\DEPLOYMENT.md .

# 예제 복사
mkdir examples
copy ..\examples\arc30\arc30_bent.k examples\
copy ..\build\bin\Release\test_vardens.yaml examples\vardens.yaml

# ZIP 압축
powershell Compress-Archive -Path * -DestinationPath KooRemapper_v1.0.0_Windows.zip
```

### 배포 패키지 생성 (Linux/macOS)

```bash
cd KooRemapper

# 배포 폴더 생성
mkdir -p KooRemapper_Package
cd KooRemapper_Package

# 실행파일 복사
cp ../build/bin/Release/KooRemapper .
chmod +x KooRemapper

# 문서 복사
cp ../README.md .
cp ../DEPLOYMENT.md .

# 예제 복사
mkdir -p examples
cp ../examples/arc30/arc30_bent.k examples/
cp ../build/bin/Release/test_vardens.yaml examples/vardens.yaml

# TAR 압축
tar -czf KooRemapper_v1.0.0_Linux.tar.gz *
```

---

## 🔧 소스에서 빌드 (개발자용)

### 1. 저장소 클론

```bash
git clone https://github.com/squall321/KooRemapper.git
cd KooRemapper
```

### 2. 빌드

**Windows:**
```cmd
scripts\build_windows.bat
```

**Linux/macOS:**
```bash
./scripts/build_linux.sh
```

### 3. 빌드 결과

- 실행파일: `build/bin/Release/KooRemapper[.exe]`
- 테스트: `build/bin/Release/KooRemapper_tests[.exe]`
- 라이브러리: `build/lib/Release/kooremapper_lib.lib`

---

## ✅ 설치 확인

### 실행파일 테스트

```bash
# 버전 확인
KooRemapper version

# 도움말
KooRemapper help

# 간단한 예제 생성
KooRemapper generate arc test_arc
```

### 예상 출력

```
============================================================
  KooRemapper - Mesh Mapping Tool for LS-DYNA
  Version 1.0.0
============================================================

✓ Generated bent mesh: test_arc_bent.k
✓ Generated flat mesh: test_arc_flat.k
```

---

## 🌐 네트워크 배포

### 공유 폴더 사용

```cmd
# 공유 폴더에 복사
copy KooRemapper.exe \\server\shared\tools\

# 사용자는 PATH에 추가
set PATH=%PATH%;\\server\shared\tools
```

### Docker 이미지 (선택)

```dockerfile
FROM ubuntu:22.04

# 필요 라이브러리
RUN apt-get update && apt-get install -y libgomp1

# 실행파일 복사
COPY KooRemapper /usr/local/bin/
RUN chmod +x /usr/local/bin/KooRemapper

# 실행
ENTRYPOINT ["KooRemapper"]
```

---

## 📋 시스템 요구사항

### Windows
- Windows 10 이상 (64-bit)
- Visual C++ Redistributable 불필요 (정적 링크)

### Linux
- GLIBC 2.27+ (Ubuntu 18.04+, CentOS 8+)
- libgomp (OpenMP, 일반적으로 설치됨)

### macOS
- macOS 10.15 (Catalina) 이상
- Xcode Command Line Tools (선택)

---

## 🆘 문제 해결

### "실행할 수 없음" (Linux/macOS)

```bash
chmod +x KooRemapper
```

### "DLL을 찾을 수 없음" (Windows)

- KooRemapper는 정적 링크되어 외부 DLL이 필요 없습니다.
- 문제가 계속되면 `build_windows.bat`에서 `/MT` 플래그 확인

### "Permission denied"

```bash
sudo cp KooRemapper /usr/local/bin/
# 또는
chmod +x KooRemapper
./KooRemapper
```

---

## 📞 지원

- GitHub: https://github.com/squall321/KooRemapper
- Issues: https://github.com/squall321/KooRemapper/issues
- README: [README.md](README.md)
