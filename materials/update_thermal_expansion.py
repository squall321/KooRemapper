import json

with open('materials/material_db.json', 'r', encoding='utf-8') as f:
    db = json.load(f)

# 1) Remove card_thermal_expansion from part_material_map
for pid_str, pdata in db['part_material_map'].items():
    pdata.pop('card_thermal_expansion', None)

# 2) Add card_thermal_expansion to each material entry (keyed by MID)
#    *MAT_ADD_THERMAL_EXPANSION uses PID, but at DB level store with MID as reference
#    Actual PID substitution happens at output time
count = 0
for mid_str, mat in db['materials'].items():
    alpha = mat.get('thermal', {}).get('ALPHA', 0)
    if alpha and alpha > 0:
        mid_int = int(mid_str)
        mid_field = str(mid_int).rjust(10)
        lcid_field = '0'.rjust(10)
        alpha_field = f'{alpha:.4E}'.rjust(10)
        card = (
            '*MAT_ADD_THERMAL_EXPANSION\n'
            '$      PID      LCID      MULT\n'
            f'{mid_field}{lcid_field}{alpha_field}'
        )
        mat['card_thermal_expansion'] = card
        count += 1

# 3) Regenerate .k file keyed by MID
lines = []
lines.append('$$ ============================================================================')
lines.append('$$  *MAT_ADD_THERMAL_EXPANSION per material (MID)')
lines.append('$$  LCID=0 -> constant CTE (MULT = ALPHA in 1/K)')
lines.append('$$  NOTE: PID field = MID here. Replace with actual PID at use time.')
lines.append('$$  Unit: 1/K')
lines.append('$$ ============================================================================')
lines.append('*KEYWORD')
lines.append('$')

for mid_str in sorted(db['materials'].keys(), key=lambda x: int(x)):
    mat = db['materials'][mid_str]
    alpha = mat.get('thermal', {}).get('ALPHA', 0)
    if alpha and alpha > 0:
        mid_int = int(mid_str)
        tag = mat.get('tag', mat.get('name', ''))
        name = mat.get('name', '')
        mid_field = str(mid_int).rjust(10)
        lcid_field = '0'.rjust(10)
        alpha_field = f'{alpha:.4E}'.rjust(10)
        lines.append(f'$$ --- MID {mid_str}: {name} ({tag}, ALPHA={alpha:.1E} 1/K) ---')
        lines.append('*MAT_ADD_THERMAL_EXPANSION')
        lines.append('$      PID      LCID      MULT')
        lines.append(f'{mid_field}{lcid_field}{alpha_field}')
        lines.append('$')

lines.append('*END')

with open('materials/mat_thermal_expansion.k', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

with open('materials/material_db.json', 'w', encoding='utf-8') as f:
    json.dump(db, f, indent=2, ensure_ascii=False)

print(f'Done. Materials with card_thermal_expansion: {count}')
print('Removed card_thermal_expansion from part_material_map')
print('K-file rewritten: materials/mat_thermal_expansion.k')
