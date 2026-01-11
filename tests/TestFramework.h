#pragma once

#include <string>
#include <vector>
#include <functional>
#include <iostream>
#include <cmath>
#include <chrono>

namespace KooRemapper {
namespace Test {

/**
 * Simple test framework - no external dependencies
 */
class TestFramework {
public:
    struct TestResult {
        std::string name;
        bool passed;
        std::string message;
        double durationMs;
    };

    using TestFunc = std::function<void()>;

    static TestFramework& instance() {
        static TestFramework inst;
        return inst;
    }

    void registerTest(const std::string& name, TestFunc func) {
        tests_.push_back({name, func});
    }

    int runAll() {
        std::cout << "\n========================================\n";
        std::cout << "  KooRemapper Test Suite\n";
        std::cout << "========================================\n\n";

        int passed = 0;
        int failed = 0;

        for (const auto& test : tests_) {
            currentTest_ = test.name;
            currentPassed_ = true;
            currentMessage_.clear();

            auto start = std::chrono::high_resolution_clock::now();

            try {
                test.func();
            } catch (const std::exception& e) {
                currentPassed_ = false;
                currentMessage_ = std::string("Exception: ") + e.what();
            } catch (...) {
                currentPassed_ = false;
                currentMessage_ = "Unknown exception";
            }

            auto end = std::chrono::high_resolution_clock::now();
            double durationMs = std::chrono::duration<double, std::milli>(end - start).count();

            if (currentPassed_) {
                std::cout << "[PASS] " << test.name << " (" << durationMs << " ms)\n";
                passed++;
            } else {
                std::cout << "[FAIL] " << test.name << "\n";
                std::cout << "       " << currentMessage_ << "\n";
                failed++;
            }

            results_.push_back({test.name, currentPassed_, currentMessage_, durationMs});
        }

        std::cout << "\n----------------------------------------\n";
        std::cout << "Results: " << passed << " passed, " << failed << " failed\n";
        std::cout << "----------------------------------------\n\n";

        return failed > 0 ? 1 : 0;
    }

    void fail(const std::string& message) {
        currentPassed_ = false;
        currentMessage_ = message;
    }

    bool isCurrentPassed() const { return currentPassed_; }

private:
    TestFramework() = default;

    struct TestEntry {
        std::string name;
        TestFunc func;
    };

    std::vector<TestEntry> tests_;
    std::vector<TestResult> results_;
    std::string currentTest_;
    bool currentPassed_ = true;
    std::string currentMessage_;
};

// Macros for easy test definition
#define TEST(name) \
    void test_##name(); \
    struct TestRegistrar_##name { \
        TestRegistrar_##name() { \
            KooRemapper::Test::TestFramework::instance().registerTest(#name, test_##name); \
        } \
    } testRegistrar_##name; \
    void test_##name()

#define ASSERT_TRUE(expr) \
    if (!(expr)) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_TRUE failed: ") + #expr + " at line " + std::to_string(__LINE__)); \
        return; \
    }

#define ASSERT_FALSE(expr) \
    if (expr) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_FALSE failed: ") + #expr + " at line " + std::to_string(__LINE__)); \
        return; \
    }

#define ASSERT_EQ(a, b) \
    if ((a) != (b)) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_EQ failed: ") + #a + " != " + #b + " at line " + std::to_string(__LINE__)); \
        return; \
    }

#define ASSERT_NE(a, b) \
    if ((a) == (b)) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_NE failed: ") + #a + " == " + #b + " at line " + std::to_string(__LINE__)); \
        return; \
    }

#define ASSERT_NEAR(a, b, tol) \
    if (std::abs((a) - (b)) > (tol)) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_NEAR failed: |") + std::to_string(a) + " - " + std::to_string(b) + \
            "| > " + std::to_string(tol) + " at line " + std::to_string(__LINE__)); \
        return; \
    }

#define ASSERT_LT(a, b) \
    if (!((a) < (b))) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_LT failed: ") + #a + " >= " + #b + " at line " + std::to_string(__LINE__)); \
        return; \
    }

#define ASSERT_GT(a, b) \
    if (!((a) > (b))) { \
        KooRemapper::Test::TestFramework::instance().fail( \
            std::string("ASSERT_GT failed: ") + #a + " <= " + #b + " at line " + std::to_string(__LINE__)); \
        return; \
    }

} // namespace Test
} // namespace KooRemapper
