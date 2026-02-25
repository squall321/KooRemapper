#pragma once

#include <vector>
#include <string>
#include <unordered_map>

namespace KooRemapper {

class WarpageGrid {
public:
    // 파일 읽기
    bool loadFromFile(const std::string& filepath, double maskValue, double noiseThreshold);

    // 마스킹 영역 보간
    void interpolateMaskedRegions();

    // 양방향 선형 보간
    double interpolate(double u, double v) const;  // u,v ∈ [0, 1]

    // 곡률 및 기울기 계산 (유한 차분)
    void computeCurvatures();
    double getCurvatureXX(int i, int j) const;
    double getCurvatureYY(int i, int j) const;
    double getCurvatureXY(int i, int j) const;
    double getGradientX(int i, int j) const;   // ∂w/∂x (for finite strain)
    double getGradientY(int i, int j) const;   // ∂w/∂y (for finite strain)

    // Getter
    int rows() const { return nRows_; }
    int cols() const { return nCols_; }
    double get(int i, int j) const;

    // 통계
    std::pair<double, double> getDataRange() const;
    std::pair<double, double> getCurvatureRange() const;
    double getAverageCurvature() const;

    // 디버깅
    void exportDebugData(const std::string& prefix) const;

private:
    int nRows_ = 0;
    int nCols_ = 0;
    std::vector<std::vector<double>> data_;      // 원본 데이터
    std::vector<std::vector<double>> kappa_xx_;  // 곡률 XX
    std::vector<std::vector<double>> kappa_yy_;  // 곡률 YY
    std::vector<std::vector<double>> kappa_xy_;  // 곡률 XY
    std::vector<std::vector<double>> grad_x_;    // 기울기 ∂w/∂x (for finite strain)
    std::vector<std::vector<double>> grad_y_;    // 기울기 ∂w/∂y (for finite strain)

    // 보간 캐싱
    mutable std::unordered_map<int, double> interpCache_;

    // 내부 헬퍼
    void parseTabDelimitedFile(const std::string& filepath);
    void applyMaskInterpolation(double maskValue);
    void removeNoise(double threshold);
    int countMaskedCells(double maskValue) const;
    bool detectIsolatedMaskedRegions(double maskValue);

    // 경계 곡률
    double forwardDifferenceX(int i, int j) const;
    double backwardDifferenceX(int i, int j) const;
    double forwardDifferenceY(int i, int j) const;
    double backwardDifferenceY(int i, int j) const;
    double forwardDifferenceXY(int i, int j) const;

    // 보간 구현
    double interpolateImpl(double u, double v) const;
};

} // namespace KooRemapper
