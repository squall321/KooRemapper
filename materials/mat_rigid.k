$$ ============================================================================
$$  MAT_RIGID (Type 020) - 2 rigid materials
$$  Unit: t / mm / s --> MPa
$$ ============================================================================
*KEYWORD
$
$$ --- MID 21: Rigid (Fully constrained) ---
*MAT_RIGID_TITLE
Rigid
$      MID       RHO         E        PR         N    COUPLE         M     ALIAS
        217.9300E-09  190000.0       0.3       0.0       0.0       0.0
$      CMO      CON1      CON2
       1.0         7         7
$       A1        A2        A3        V1        V2        V3
       0.0       0.0       0.0       0.0       0.0       0.0
$
$$ --- MID 46: Peek-RIGID (Rz free, partial constraint) ---
*MAT_RIGID_TITLE
Peek-RIGID
$      MID       RHO         E        PR         N    COUPLE         M     ALIAS
        467.9300E-09  190000.0       0.3       0.0       0.0       0.0
$      CMO      CON1      CON2
       1.0         4         7
$       A1        A2        A3        V1        V2        V3
       0.0       0.0       0.0       0.0       0.0       0.0
$
*END
