# Glossary

Domain vocabulary used throughout KooRemapper and this knowledge graph.

| Term | Meaning |
|------|---------|
| **K-file** | LS-DYNA keyword input file (`.k`, `.key`, `.dyn`). ASCII, 80-col. |
| **dynain** | LS-DYNA "dynamic initialization" file containing `*INITIAL_STRESS_*` cards. |
| **PID** | Part ID (LS-DYNA `*PART`). |
| **MID** | Material ID. |
| **SECID** | Section ID. |
| **EID** | Element ID. |
| **NID** | Node ID. |
| **HGID** | Hourglass-control ID. |
| **LCID** | Load curve ID. |
| **TMID** | Thermal material ID. |
| **ELFORM** | Element formulation number (LS-DYNA `*SECTION_*`). |
| **DR** | Dynamic Relaxation. |
| **CZM** | Cohesive-Zone Model. |
| **MEFEM** | Mesh-Free Enrichment FEM. |
| **HEX8 / TET4 / QUAD4 / TRIA3** | Linear element topologies (8/4/4/3 nodes). |
| **HEX20 / TET10 / QUAD8 / TRIA6** | Quadratic counterparts (mid-edge nodes). |
| **Isoparametric** | Same shape functions for geometry and field (see [[theory/shape-functions#Shape functions]]). |
| **Arc-length parameterization** | Map mesh node positions to normalized arc coordinate u ∈ [0,1]. |
| **Winding number** | Closed-curve point-in-polygon test (see [ClosedLoop.cpp](src/assembly/ClosedLoop.cpp)). |
| **Kirchhoff plate** | Thin-plate bending theory, normals stay normal. Used in [[commands/bend#bend — Kirchhoff plate bending (§13)]], [[commands/indent#indent — indent/emboss (§14)]]. |
| **Green-Lagrange strain** | Large-deformation strain tensor (`E = (FᵀF − I)/2`). |
| **Cauchy stress** | True stress per current area. |
| **EPS** | Effective plastic strain (LS-DYNA history variable). |
| **NPLANE / NTHICK** | Shell stress sampling: in-plane and through-thickness integration counts. |
| **TSSFAC** | Time-step safety factor in `*CONTROL_TIMESTEP`. |
| **IHQ** | Hourglass control type (1=standard, 4=Flanagan-Belytschko, 6=Belytschko-Bindeman). |
| **MUMPS** | Sparse direct solver (LS-DYNA implicit option). |
| **JWL** | Jones-Wilkins-Lee EOS for explosives ([[lsdyna/eos#LS-DYNA EOS (equation of state) in KooRemapper]]). |
| **FSI** | Fluid-Structure Interaction (LS-DYNA `*CONSTRAINED_LAGRANGE_IN_SOLID`). |
| **ALE** | Arbitrary Lagrangian-Eulerian. See [[commands/ale#ale — Lagrangian → ALE converter (§35)]]. |
| **IGA** | Isogeometric Analysis (NURBS-based). See [[commands/iga#iga — IGA NURBS box generation (§20)]]. |
| **prestress** | Initial stress state carried from a reference analysis (dynain). |
| **squeeze** | Compressing parts to remove interference, then injecting reverse prestress. |
| **restack** | Re-layering of plates/tiers — see [[commands/restack#restack — layer restacking (§12)]]. |
| **formstrain** | Plastic strain induced by sheet-metal forming, computed from shell dihedral curvature. |
| **warpage** | Thermal/cure-induced out-of-plane distortion. |
| **strip mode** | "Strip" flag removing solver-mode-specific cards without inserting replacements. |
