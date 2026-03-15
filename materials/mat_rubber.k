$$ ============================================================================
$$  MAT_MOONEY-RIVLIN_RUBBER (Type 027) - 2 materials
$$  Unit: t / mm / s --> MPa
$$ ============================================================================
*KEYWORD
$
$$ --- MID 45: Rubber-Mooney (PCAP rubber cap) ---
$$     G = 2*(A+B) = 2*(60+0) = 120 MPa
*MAT_MOONEY-RIVLIN_RUBBER
$      MID       RHO        PR         A         B       REF
        451.2000E-09     0.499      60.0       0.0
$      SGL        SW        ST      LCID
$
$$ --- MID 47: PSA-31.7 (PSA adhesive layers: PSA0/PSA2/PSA4/PSA6) ---
$$     G = 2*(A+B) = 2*(31.7+0) = 63.4 MPa
*MAT_MOONEY-RIVLIN_RUBBER
$      MID       RHO        PR         A         B       REF
        471.2000E-09     0.499      31.7       0.0
$      SGL        SW        ST      LCID
$
*END
