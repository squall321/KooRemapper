import json

with open('materials/material_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

def fmt_field(val, width=10):
    """Format a value into a fixed-width LS-DYNA field"""
    if isinstance(val, int):
        return str(val).rjust(width)
    elif isinstance(val, float):
        if val == 0.0:
            return '0.0'.rjust(width)
        elif abs(val) >= 1e6 or abs(val) < 0.01:
            s = f'{val:.4E}'
            return s.rjust(width)
        elif val == int(val):
            s = f'{val:.1f}'
            return s.rjust(width)
        else:
            # Try to fit in 10 chars
            for dec in range(4, 0, -1):
                s = f'{val:.{dec}f}'
                if len(s) <= width:
                    return s.rjust(width)
            return f'{val:.4E}'.rjust(width)
    else:
        return str(val).rjust(width)

def fmt_rho(rho):
    """Format density in LS-DYNA notation"""
    return f'{rho:.4E}'.rjust(10)

def make_elastic_card(mid, name, rho, E, PR):
    """Generate MAT_ELASTIC card"""
    lines = [
        '*MAT_ELASTIC_TITLE',
        name,
        '$      MID       RHO         E        PR        DA        DB         K',
        f'{fmt_field(mid)}{fmt_rho(rho)}{fmt_field(E)}{fmt_field(PR)}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}'
    ]
    return '\n'.join(lines)

def make_rigid_card(mid, name, rho, E, PR, cmo=1.0, con1=7, con2=7):
    """Generate MAT_RIGID card (full lock by default)"""
    lines = [
        '*MAT_RIGID_TITLE',
        name,
        '$      MID       RHO         E        PR         N    COUPLE         M     ALIAS',
        f'{fmt_field(mid)}{fmt_rho(rho)}{fmt_field(E)}{fmt_field(PR)}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}          ',
        '$      CMO      CON1      CON2',
        f'{fmt_field(cmo)}{fmt_field(con1)}{fmt_field(con2)}',
        '$       A1        A2        A3        V1        V2        V3',
        f'{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}'
    ]
    return '\n'.join(lines)

def make_024_card(mid, name, rho, E, PR, sigy, etan=0.0):
    """Generate MAT_PIECEWISE_LINEAR_PLASTICITY card"""
    lines = [
        '*MAT_PIECEWISE_LINEAR_PLASTICITY_TITLE',
        name,
        '$      MID       RHO         E        PR      SIGY      ETAN      FAIL      TDEL',
        f'{fmt_field(mid)}{fmt_rho(rho)}{fmt_field(E)}{fmt_field(PR)}{fmt_field(sigy)}{fmt_field(etan)}{fmt_field(0.0)}{fmt_field(0.0)}',
        '$        C         P      LCSS      LCSR        VP       LCF',
        f'{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0)}{fmt_field(0)}{fmt_field(0.0)}          '
    ]
    return '\n'.join(lines)

def make_elastic_from_mooney(mid, name, rho, A, B, PR):
    """Generate MAT_ELASTIC from Mooney-Rivlin parameters. E = 6*(A+B) for small strain"""
    E_approx = 6.0 * (A + B)
    lines = [
        '*MAT_ELASTIC_TITLE',
        f'{name} (linearized from Mooney-Rivlin)',
        '$      MID       RHO         E        PR        DA        DB         K',
        f'{fmt_field(mid)}{fmt_rho(rho)}{fmt_field(E_approx)}{fmt_field(PR)}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}'
    ]
    return '\n'.join(lines)

def make_elastic_from_visco(mid, name, rho, G0, GI, BULK):
    """Generate MAT_ELASTIC from viscoelastic. Use instantaneous G0 and long-term GI"""
    # E = 9KG / (3K+G)
    E_inst = 9.0 * BULK * G0 / (3.0 * BULK + G0)
    PR_inst = (3.0 * BULK - 2.0 * G0) / (6.0 * BULK + 2.0 * G0)
    E_long = 9.0 * BULK * GI / (3.0 * BULK + GI)
    PR_long = (3.0 * BULK - 2.0 * GI) / (6.0 * BULK + 2.0 * GI)
    cards = {}
    # Instantaneous
    lines = [
        '*MAT_ELASTIC_TITLE',
        f'{name} (instantaneous, G0={G0})',
        '$      MID       RHO         E        PR        DA        DB         K',
        f'{fmt_field(mid)}{fmt_rho(rho)}{fmt_field(round(E_inst,2))}{fmt_field(round(PR_inst,4))}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}'
    ]
    cards['MAT_ELASTIC_instantaneous'] = '\n'.join(lines)
    # Long-term
    lines = [
        '*MAT_ELASTIC_TITLE',
        f'{name} (long-term, GI={GI})',
        '$      MID       RHO         E        PR        DA        DB         K',
        f'{fmt_field(mid)}{fmt_rho(rho)}{fmt_field(round(E_long,4))}{fmt_field(round(PR_long,4))}{fmt_field(0.0)}{fmt_field(0.0)}{fmt_field(0.0)}'
    ]
    cards['MAT_ELASTIC_longterm'] = '\n'.join(lines)
    return cards

# Typical yield stress estimates for metals (MPa)
metal_sigy = {
    '2': 215.0,    # STS304: ~215 MPa
    '3': 490.0,    # S45C: ~490 MPa
    '4': 245.0,    # AL7003-H: ~245 MPa
    '6': 490.0,    # Ground (carbon steel): ~490 MPa
    '11': 260.0,   # Cu (FPCB): ~260 MPa
    '13': 700.0,   # SUS spring: ~700 MPa
    '18': 200.0,   # AL frame: ~200 MPa
    '19': 240.0,   # Ti CP: ~240 MPa
}

for mid_str, mat in db['materials'].items():
    mid = int(mid_str)
    name = mat['name']
    mech = mat['mechanical']
    orig_type = mat['mat_type']

    # Preserve original card as-is
    orig_card = mat.pop('card_structural')

    cards = {}

    # --- Original card (always first) ---
    cards[orig_type] = orig_card

    if orig_type == 'MAT_ELASTIC':
        rho = mech['RHO']
        E = mech['E']
        PR = mech['PR']

        # Add MAT_RIGID variant
        cards['MAT_RIGID'] = make_rigid_card(mid, name, rho, E, PR)

        # Add MAT_024 for metals with known yield
        if mid_str in metal_sigy:
            sigy = metal_sigy[mid_str]
            cards['MAT_PIECEWISE_LINEAR_PLASTICITY'] = make_024_card(mid, name, rho, E, PR, sigy)

    elif orig_type == 'MAT_RIGID':
        rho = mech['RHO']
        E = mech['E']
        PR = mech['PR']

        # Add MAT_ELASTIC variant
        cards['MAT_ELASTIC'] = make_elastic_card(mid, name, rho, E, PR)

    elif orig_type == 'MAT_PIECEWISE_LINEAR_PLASTICITY':
        rho = mech['RHO']
        E = mech['E']
        PR = mech['PR']

        # Add MAT_ELASTIC variant
        cards['MAT_ELASTIC'] = make_elastic_card(mid, name, rho, E, PR)
        # Add MAT_RIGID variant
        cards['MAT_RIGID'] = make_rigid_card(mid, name, rho, E, PR)

    elif orig_type == 'MAT_MOONEY-RIVLIN_RUBBER':
        rho = mech['RHO']
        A = mech['A']
        B = mech['B']
        PR = mech['PR']

        # Add linearized MAT_ELASTIC variant
        cards['MAT_ELASTIC'] = make_elastic_from_mooney(mid, name, rho, A, B, PR)
        # Add MAT_RIGID variant
        E_approx = 6.0 * (A + B)
        cards['MAT_RIGID'] = make_rigid_card(mid, name, rho, E_approx, PR)

    elif orig_type == 'MAT_VISCOELASTIC':
        rho = mech['RHO']
        G0 = mech['G0']
        GI = mech['GI']
        BULK = mech['BULK']

        # Add MAT_ELASTIC variants (instantaneous + long-term)
        visco_cards = make_elastic_from_visco(mid, name, rho, G0, GI, BULK)
        cards.update(visco_cards)

        # Add MAT_RIGID variant
        E_inst = 9.0 * BULK * G0 / (3.0 * BULK + G0)
        PR_inst = (3.0 * BULK - 2.0 * G0) / (6.0 * BULK + 2.0 * G0)
        cards['MAT_RIGID'] = make_rigid_card(mid, name, rho, round(E_inst, 2), round(PR_inst, 4))

    mat['cards_structural'] = cards

# Remove old field name (now using cards_structural)
# mat_type stays to indicate the "primary" type

with open('materials/material_db.json', 'w', encoding='utf-8') as f:
    json.dump(db, f, indent=2, ensure_ascii=False)

# Print summary
for mid_str in sorted(db['materials'].keys(), key=lambda x: int(x)):
    mat = db['materials'][mid_str]
    variants = list(mat['cards_structural'].keys())
    print(f'  MID {mid_str:>3}: {mat["name"]:<25} -> {variants}')

print(f'\nTotal: {len(db["materials"])} materials updated')
