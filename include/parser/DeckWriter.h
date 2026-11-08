// 덱을 쓸 때 원본 개행을 되붙이는 공용 출력 계층 — 모든 덱 쓰기의 단일 진입점
#pragma once

#include <cerrno>
#include <cstring>
#include <fstream>
#include <ostream>
#include <streambuf>
#include <string>
#include <vector>

#include "parser/DeckNewline.h"

namespace KooRemapper {

// 이 프로세스에서 실패한 덱 쓰기(「경로: 까닭」) — DeckWriter · ModelAssembler::writeOutput · DynainWriter 가 적는다. main 은 op 이
// rc 0 을 돌려도 여기 적힌 것이 있으면 찍고 rc 1 로 끝낸다(여섯째 검토 S2 — 디스크가 차거나 파일 크기 상한에 걸려 잘린 덱이 rc 0 ·
// ok 보고로 나갔다). 스스로 실패를 다룬 op(바꿔 넣지 않고 rc 1 · 보고)은 그대로 rc 1 이다
namespace deck_write {
inline std::vector<std::string>& failures() {
    static std::vector<std::string> f;
    return f;
}
inline void note(const std::string& what) { failures().push_back(what); }
inline std::string describe(const std::string& path, int err) {
    return path + " (" + (err ? std::string(std::strerror(err)) : std::string("쓰기 실패")) + ")";
}
}  // namespace deck_write

// `\n` 을 그 덱의 개행으로 바꿔 흘려보내는 streambuf.
//
// ⚠ 왜 문자열로 모아 한 번에 치환하지 않나 — 덱이 700MB~1GB 다. 출력 전문을 문자열로 들고
// 치환본을 또 만들면 복사가 곱으로 는다. 스트리밍이면 상수 메모리다.
//
// 본문에 CR 이 없다는 전제를 쓰지 않는다 — 이미 `\r\n` 인 자리는 그대로 두고 **홀로 선 `\n`**
// 앞에만 CR 을 넣는다. 그래서 CR 을 떼는 리더(ModelAssembler·KFileReader)와 안 떼는 리더
// (strip·relax)가 같은 계층을 써도 `\r\r\n` 이 생기지 않는다.
//
// ★아래 파일 버퍼의 짧은 쓰기 · 실패(디스크 참 · EFBIG · EIO)는 받은 글자 수를 줄여 돌려줘 스트림이 badbit 을 서게 하고
//   첫 실패의 errno 를 남긴다 — 예전엔 CRLF 갈래가 `sputn` · `sputc` 결과를 버려 잘린 덱이 멀쩡한 스트림으로 끝났다(S2)
class NewlineStreambuf : public std::streambuf {
public:
    NewlineStreambuf(std::streambuf* dst, DeckNewline nl)
        : dst_(dst), crlf_(nl == DeckNewline::CRLF) {}

    bool failed() const { return failed_; }
    int error() const { return err_; }

protected:
    int_type overflow(int_type c) override {
        if (traits_type::eq_int_type(c, traits_type::eof())) return traits_type::not_eof(c);
        const char ch = traits_type::to_char_type(c);
        if (crlf_ && ch == '\n' && !prevWasCR_) {
            if (traits_type::eq_int_type(dst_->sputc('\r'), traits_type::eof())) return fail();
        }
        prevWasCR_ = (ch == '\r');
        if (traits_type::eq_int_type(dst_->sputc(ch), traits_type::eof())) return fail();
        return c;
    }

    std::streamsize xsputn(const char* s, std::streamsize n) override {
        if (!crlf_) {
            const std::streamsize w = dst_->sputn(s, n);
            if (w < n) fail();
            if (w > 0) prevWasCR_ = (s[w - 1] == '\r');
            return w;
        }
        std::streamsize runStart = 0;
        for (std::streamsize i = 0; i < n; ++i) {
            const bool prevCR = (i == 0) ? prevWasCR_ : (s[i - 1] == '\r');
            if (s[i] == '\n' && !prevCR) {
                // 여기까지를 통째로 흘리고 CR 을 끼운다 — 한 글자씩 쓰면 700MB 에서 느리다. 짧게 쓰였으면 거기서 멈춘다
                if (i > runStart && dst_->sputn(s + runStart, i - runStart) != i - runStart) { fail(); return runStart; }
                if (traits_type::eq_int_type(dst_->sputc('\r'), traits_type::eof())) { fail(); return i; }
                runStart = i;
            }
        }
        if (n > runStart && dst_->sputn(s + runStart, n - runStart) != n - runStart) { fail(); return runStart; }
        if (n > 0) prevWasCR_ = (s[n - 1] == '\r');
        return n;
    }

    int sync() override {
        const int r = dst_->pubsync();
        if (r != 0) fail();
        return r;
    }

private:
    int_type fail() {
        if (!failed_) {
            failed_ = true;
            err_ = errno;
        }
        return traits_type::eof();
    }

    std::streambuf* dst_;
    bool crlf_;
    bool prevWasCR_ = false;
    bool failed_ = false;
    int err_ = 0;
};

// 덱 파일 하나를 연다. **반드시 바이너리 모드**다 — MSVC 의 텍스트 모드는 `\n` 을 `\r\n` 으로
// 바꾸므로, CR 을 살려 넘기는 경로에서 `\r\r\n` 이 나온다(리눅스 CRLF 소실과는 별개의 결함).
//
// 쓰는 쪽은 지금처럼 `\n` 으로 쓰면 된다. 개행 되붙임은 이 계층이 한다.
// ★`close()` 는 쓰기가 어디서든 실패했으면(짧은 쓰기 · 스트림 상태 · 비우기 · 닫기) false 다 — 까닭은 `error()`(「경로 (strerror)」).
//   실패는 공용 기록(`deck_write::failures`)에도 남아 부르는 쪽이 결과를 보지 않아도 main 이 rc 1 로 끝낸다. 소멸자도 닫는다
class DeckWriter {
public:
    DeckWriter(const std::string& path, DeckNewline nl)
        : path_(path), file_(path, std::ios::binary), buf_(file_.rdbuf(), nl), out_(&buf_) {}
    ~DeckWriter() { close(); }
    DeckWriter(const DeckWriter&) = delete;
    DeckWriter& operator=(const DeckWriter&) = delete;

    bool ok() const { return file_.is_open(); }
    std::ostream& stream() { return out_; }
    bool close() {
        if (closed_) return !failed_;
        closed_ = true;
        if (!file_.is_open()) return true;   // 열지 못한 덱 — 부르는 쪽이 ok() 로 이미 말했다
        out_.flush();
        bool bad = buf_.failed() || out_.fail();
        int err = buf_.error();
        errno = 0;
        file_.close();
        if (file_.fail()) {
            bad = true;
            if (!err) err = errno;
        }
        if (bad) {
            failed_ = true;
            error_ = deck_write::describe(path_, err);
            deck_write::note(error_);
        }
        return !bad;
    }
    bool failed() const { return failed_; }
    const std::string& error() const { return error_; }

private:
    std::string path_;
    std::ofstream file_;
    NewlineStreambuf buf_;
    std::ostream out_;
    bool closed_ = false;
    bool failed_ = false;
    std::string error_;
};

}  // namespace KooRemapper
