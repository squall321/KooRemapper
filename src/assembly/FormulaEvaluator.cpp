#include "assembly/FormulaEvaluator.h"
#include <cmath>
#include <stdexcept>
#include <cctype>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace KooRemapper {

FormulaEvaluator::FormulaEvaluator() : pos_(nullptr), end_(nullptr) {
    variables_["pi"] = M_PI;
}

void FormulaEvaluator::setVariable(const std::string& name, double value) {
    variables_[name] = value;
}

double FormulaEvaluator::evaluate(const std::string& expression) {
    pos_ = expression.c_str();
    end_ = pos_ + expression.size();
    errorMessage_.clear();

    double result = parseExpression();

    skipWhitespace();
    if (pos_ < end_) {
        throw std::runtime_error("Unexpected character at position " +
            std::to_string(pos_ - expression.c_str()) + ": '" + std::string(1, *pos_) + "'");
    }

    return result;
}

// Expression: Term (('+' | '-') Term)*
double FormulaEvaluator::parseExpression() {
    double result = parseTerm();
    while (true) {
        skipWhitespace();
        if (match('+')) {
            result += parseTerm();
        } else if (match('-')) {
            result -= parseTerm();
        } else {
            break;
        }
    }
    return result;
}

// Term: Power (('*' | '/') Power)*
double FormulaEvaluator::parseTerm() {
    double result = parsePower();
    while (true) {
        skipWhitespace();
        if (match('*')) {
            result *= parsePower();
        } else if (match('/')) {
            double divisor = parsePower();
            if (divisor == 0.0) {
                throw std::runtime_error("Division by zero");
            }
            result /= divisor;
        } else {
            break;
        }
    }
    return result;
}

// Power: Unary ('^' Unary)*  (right-associative)
double FormulaEvaluator::parsePower() {
    double base = parseUnary();
    skipWhitespace();
    if (match('^')) {
        double exponent = parsePower(); // Right-associative recursion
        return std::pow(base, exponent);
    }
    return base;
}

// Unary: ('+' | '-')? Primary
double FormulaEvaluator::parseUnary() {
    skipWhitespace();
    if (match('-')) {
        return -parseUnary();
    }
    if (match('+')) {
        return parseUnary();
    }
    return parsePrimary();
}

// Primary: Number | Identifier (variable or function call) | '(' Expression ')'
double FormulaEvaluator::parsePrimary() {
    skipWhitespace();

    // Parenthesized expression
    if (match('(')) {
        double result = parseExpression();
        skipWhitespace();
        if (!match(')')) {
            throw std::runtime_error("Expected closing parenthesis");
        }
        return result;
    }

    // Number
    if (std::isdigit(peek()) || peek() == '.') {
        return parseNumber();
    }

    // Identifier (variable or function)
    if (std::isalpha(peek()) || peek() == '_') {
        std::string name = parseIdentifier();

        skipWhitespace();
        if (match('(')) {
            // Function call
            double arg1 = parseExpression();
            skipWhitespace();
            if (match(',')) {
                // Two-argument function
                double arg2 = parseExpression();
                skipWhitespace();
                if (!match(')')) {
                    throw std::runtime_error("Expected ')' after function arguments");
                }
                return callFunction2(name, arg1, arg2);
            }
            if (!match(')')) {
                throw std::runtime_error("Expected ')' after function argument");
            }
            return callFunction(name, arg1);
        }

        // Variable lookup
        auto it = variables_.find(name);
        if (it != variables_.end()) {
            return it->second;
        }
        throw std::runtime_error("Unknown variable: " + name);
    }

    if (pos_ >= end_) {
        throw std::runtime_error("Unexpected end of expression");
    }
    throw std::runtime_error("Unexpected character: '" + std::string(1, *pos_) + "'");
}

void FormulaEvaluator::skipWhitespace() {
    while (pos_ < end_ && std::isspace(*pos_)) {
        ++pos_;
    }
}

char FormulaEvaluator::peek() const {
    if (pos_ >= end_) return '\0';
    return *pos_;
}

char FormulaEvaluator::advance() {
    if (pos_ >= end_) return '\0';
    return *pos_++;
}

bool FormulaEvaluator::match(char c) {
    skipWhitespace();
    if (pos_ < end_ && *pos_ == c) {
        ++pos_;
        return true;
    }
    return false;
}

double FormulaEvaluator::parseNumber() {
    const char* start = pos_;

    // Integer part
    while (pos_ < end_ && std::isdigit(*pos_)) ++pos_;

    // Decimal part
    if (pos_ < end_ && *pos_ == '.') {
        ++pos_;
        while (pos_ < end_ && std::isdigit(*pos_)) ++pos_;
    }

    // Exponent part (e.g., 1.5e-3)
    if (pos_ < end_ && (*pos_ == 'e' || *pos_ == 'E')) {
        ++pos_;
        if (pos_ < end_ && (*pos_ == '+' || *pos_ == '-')) ++pos_;
        while (pos_ < end_ && std::isdigit(*pos_)) ++pos_;
    }

    std::string numStr(start, pos_);
    try {
        return std::stod(numStr);
    } catch (...) {
        throw std::runtime_error("Invalid number: " + numStr);
    }
}

std::string FormulaEvaluator::parseIdentifier() {
    const char* start = pos_;
    while (pos_ < end_ && (std::isalnum(*pos_) || *pos_ == '_')) {
        ++pos_;
    }
    return std::string(start, pos_);
}

double FormulaEvaluator::callFunction(const std::string& name, double arg) {
    if (name == "sin")  return std::sin(arg);
    if (name == "cos")  return std::cos(arg);
    if (name == "tan")  return std::tan(arg);
    if (name == "exp")  return std::exp(arg);
    if (name == "log")  return std::log(arg);
    if (name == "sqrt") return std::sqrt(arg);
    if (name == "abs")  return std::abs(arg);
    if (name == "asin") return std::asin(arg);
    if (name == "acos") return std::acos(arg);
    if (name == "atan") return std::atan(arg);
    throw std::runtime_error("Unknown function: " + name);
}

double FormulaEvaluator::callFunction2(const std::string& name, double arg1, double arg2) {
    if (name == "pow")  return std::pow(arg1, arg2);
    if (name == "atan2") return std::atan2(arg1, arg2);
    if (name == "min")  return std::min(arg1, arg2);
    if (name == "max")  return std::max(arg1, arg2);
    throw std::runtime_error("Unknown function: " + name + " (with 2 arguments)");
}

} // namespace KooRemapper
