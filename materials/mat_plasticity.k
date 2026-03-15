$$ ============================================================================
$$  MAT_PIECEWISE_LINEAR_PLASTICITY (Type 024) - 1 material
$$  Unit: t / mm / s --> MPa
$$ ============================================================================
*KEYWORD
$
$$ --- MID 38: M-Film (Titanium alloy, elasto-plastic) ---
$$     Ti grade, E=105GPa, SIGY=411.88 MPa, UTS~1200 MPa
*MAT_PIECEWISE_LINEAR_PLASTICITY
$      MID       RHO         E        PR      SIGY      ETAN      FAIL      TDEL
        384.5000E-09  105000.0       0.3    411.88       0.0       0.0       0.0
$        C         P      LCSS      LCSR        VP       LCF
       0.0       0.0         0         0       0.0
$     EPS1      EPS2      EPS3      EPS4      EPS5      EPS6      EPS7      EPS8
       0.0   0.00782  0.010774       0.0       0.0       0.0       0.0       0.0
$      ES1       ES2       ES3       ES4       ES5       ES6       ES7       ES8
    411.88   1029.64    1200.0       0.0       0.0       0.0       0.0       0.0
$
$$ Stress-Strain curve:
$$   Point 1: eps=0.0       sig=411.88 MPa  (yield)
$$   Point 2: eps=0.00782   sig=1029.64 MPa (hardening)
$$   Point 3: eps=0.01077   sig=1200.00 MPa (near UTS)
$
*END
