// 덱을 쓸 때 원본 개행을 되붙이는 공용 출력 계층 — 모든 덱 쓰기의 단일 진입점
#pragma once

#include <fstream>
#include <ostream>
#include <streambuf>
#include <string>

#include "parser/DeckNewline.h"

namespace KooRemapper {

// `\n` 을 그 덱의 개행으로 바꿔 흘려보내는 streambuf.
//
// ⚠ 왜 문자열로 모아 한 번에 치환하지 않나 — 덱이 700MB~1GB 다. 출력 전문을 문자열로 들고
// 치환본을 또 만들면 복사가 곱으로 는다. 스트리밍이면 상수 메모리다.
//
// 본문에 CR 이 없다는 전제를 쓰지 않는다 — 이미 `\r\n` 인 자리는 그대로 두고 **홀로 선 `\n`**
// 앞에만 CR 을 넣는다. 그래서 CR 을 떼는 리더(ModelAssembler·KFileReader)와 안 떼는 리더
// (strip·relax)가 같은 계층을 써도 `\r\r\n` 이 생기지 않는다.
class NewlineStreambuf : public std::streambuf {
public:
    NewlineStreambuf(std::streambuf* dst, DeckNewline nl)
        : dst_(dst), crlf_(nl == DeckNewline::CRLF) {}

protected:
    int_type overflow(int_type c) override {
        if (traits_type::eq_int_type(c, traits_type::eof())) return traits_type::not_eof(c);
        const char ch = traits_type::to_char_type(c);
        if (crlf_ && ch == '\n' && !prevWasCR_) {
            if (traits_type::eq_int_type(dst_->sputc('\r'), traits_type::eof()))
                return traits_type::eof();
        }
        prevWasCR_ = (ch == '\r');
        return dst_->sputc(ch);
    }

    std::streamsize xsputn(const char* s, std::streamsize n) override {
        if (!crlf_) {
            if (n > 0) prevWasCR_ = (s[n - 1] == '\r');
            return dst_->sputn(s, n);
        }
        std::streamsize done = 0;
        std::streamsize runStart = 0;
        for (std::streamsize i = 0; i < n; ++i) {
            const char ch = s[i];
            const bool prevCR = (i == 0) ? prevWasCR_ : (s[i - 1] == '\r');
            if (ch == '\n' && !prevCR) {
                // 여기까지를 통째로 흘리고 CR 을 끼운다 — 한 글자씩 쓰면 700MB 에서 느리다
                if (i > runStart) dst_->sputn(s + runStart, i - runStart);
                dst_->sputc('\r');
                runStart = i;
            }
            ++done;
        }
        if (n > runStart) dst_->sputn(s + runStart, n - runStart);
        if (n > 0) prevWasCR_ = (s[n - 1] == '\r');
        return done;
    }

    int sync() override { return dst_->pubsync(); }

private:
    std::streambuf* dst_;
    bool crlf_;
    bool prevWasCR_ = false;
};

// 덱 파일 하나를 연다. **반드시 바이너리 모드**다 — MSVC 의 텍스트 모드는 `\n` 을 `\r\n` 으로
// 바꾸므로, CR 을 살려 넘기는 경로에서 `\r\r\n` 이 나온다(리눅스 CRLF 소실과는 별개의 결함).
//
// 쓰는 쪽은 지금처럼 `\n` 으로 쓰면 된다. 개행 되붙임은 이 계층이 한다.
class DeckWriter {
public:
    DeckWriter(const std::string& path, DeckNewline nl)
        : file_(path, std::ios::binary), buf_(file_.rdbuf(), nl), out_(&buf_) {}

    bool ok() const { return file_.is_open(); }
    std::ostream& stream() { return out_; }
    void close() { out_.flush(); file_.close(); }

private:
    std::ofstream file_;
    NewlineStreambuf buf_;
    std::ostream out_;
};

}  // namespace KooRemapper
