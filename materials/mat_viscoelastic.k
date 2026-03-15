$$ ============================================================================
$$  MAT_VISCOELASTIC (Type 006) - 1 material
$$  Unit: t / mm / s --> MPa
$$ ============================================================================
*KEYWORD
$
$$ --- MID 43: visco (Viscoelastic polymer) ---
$$     G(t) = GI + (G0 - GI) * exp(-BETA * t)
$$     Instantaneous: G0 = 5.0 MPa
$$     Long-term:     GI = 0.1 MPa
$$     Decay rate:    BETA = 5.0 /s
$$     Bulk modulus:  K = 5000 MPa
*MAT_VISCOELASTIC
$      MID       RHO      BULK        G0        GI      BETA
        431.1000E-09    5000.0       5.0       0.1       5.0
$
*END
