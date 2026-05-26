#pragma once

#include <string>
#include <map>
#include <functional>

// Knowledge graph (lat.md):
//   @lat: [[modules/assembly]]

namespace KooRemapper {

/**
 * Mathematical expression evaluator (recursive descent parser)
 *
 * Supports:
 *   Operators: +, -, *, /, ^ (power), unary -
 *   Functions: sin, cos, tan, exp, log, sqrt, abs, pow
 *   Variables: user-defined (x1, x2, L1, L2, pi, etc.)
 *   Constants: pi (built-in)
 *   Parentheses: ()
 *
 * Example: "0.5*sin(2*pi*x1/L1)*sin(pi*x2/L2) + 0.1*cos(3*pi*x1/L1)"
 */
class FormulaEvaluator {
public:
    FormulaEvaluator();

    /**
     * Set a variable value for evaluation
     */
    void setVariable(const std::string& name, double value);

    /**
     * Evaluate the expression with current variable bindings
     * @return evaluated result
     * @throws std::runtime_error on parse error
     */
    double evaluate(const std::string& expression);

    const std::string& getErrorMessage() const { return errorMessage_; }

private:
    std::map<std::string, double> variables_;
    std::string errorMessage_;

    // Parser state
    const char* pos_;
    const char* end_;

    // Recursive descent parser
    double parseExpression();    // + -
    double parseTerm();          // * /
    double parsePower();         // ^
    double parseUnary();         // unary + -
    double parsePrimary();       // numbers, variables, functions, parentheses

    // Helpers
    void skipWhitespace();
    char peek() const;
    char advance();
    bool match(char c);
    double parseNumber();
    std::string parseIdentifier();
    double callFunction(const std::string& name, double arg);
    double callFunction2(const std::string& name, double arg1, double arg2);
};

} // namespace KooRemapper
