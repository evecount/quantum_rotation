"""Real molecular geometry for the six benchmark systems.

The benchmarks and the 3D Constellation used to run on a synthetic point cloud
(a ring of atoms on a circle with a sine ripple), while calling the systems
"real-world case studies". This module replaces that with the actual
experimental coordinates:

    rhodopsin   PDB 1U19  11-cis retinal (RET) in bovine rhodopsin
    gfp         PDB 1EMA  the CRO chromophore in GFP
    mpro        PDB 7VH8  nirmatrelvir (4WI) in SARS-CoV-2 main protease
    cox2        PDB 3LN1  celecoxib (CEL) in COX-2
    azobenzene  PubChem CID 2272, 3D conformer
    h2          exact: two hydrogens at the 0.7414 A equilibrium bond length

For a protein complex the "pocket" is every heavy protein atom within
`pocket_radius_a` of the ligand, and the "ligand" is the ligand residue. The
two free molecules (azobenzene, H2) have no pocket, so their reference pose
plays that role: the question becomes whether a rotated copy can be brought
back into register with the original, which is what the demo measures anyway.

Raw structure files are cached under .cache/structures/ and are not committed.
`build_active_sites()` writes the extracted atoms to benchmarks/active_sites.json,
which is small enough to commit and is what the rest of the code reads, so the
pipeline runs offline once that file exists.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

CACHE_DIR = ".cache/structures"
ACTIVE_SITES_JSON = "benchmarks/active_sites.json"

# Solvent, buffer, cryoprotectant and ion codes that are never the ligand.
_NON_LIGAND = {
    "HOH", "WAT", "SO4", "PO4", "GOL", "EDO", "NA", "CL", "MG", "ZN", "CA",
    "K", "ACT", "PEG", "DMS", "MPD", "NAG", "BMA", "MAN", "TRS", "IOD", "BR",
}


@dataclass
class SiteSpec:
    """How to pull one active site out of one structure."""
    id: str
    name: str
    kind: str                      # "complex" (protein + ligand) or "molecule"
    source_db: str                 # "RCSB" or "PubChem"
    source_id: str
    url: str
    ligand_resname: Optional[str] = None
    ligand_chain: Optional[str] = None
    ligand_resseq: Optional[int] = None
    pocket_radius_a: float = 5.0
    note: str = ""
    # Some entries number the mature protein while the literature numbers the
    # precursor. 3LN1's Val509 is the Val523 everyone writes about, so the
    # labels add this offset; the coordinates are untouched.
    residue_label_offset: int = 0


SITE_SPECS: list[SiteSpec] = [
    SiteSpec(
        id="rhodopsin",
        name="11-cis Retinal / Rhodopsin",
        kind="complex",
        source_db="RCSB",
        source_id="1U19",
        url="https://files.rcsb.org/download/1U19.pdb",
        ligand_resname="RET",
        ligand_chain="A",
        ligand_resseq=1296,
        note="Bovine rhodopsin at 2.2 A; retinal is covalently bound to Lys296 via a protonated Schiff base.",
    ),
    SiteSpec(
        id="gfp",
        name="GFP Chromophore",
        kind="complex",
        source_db="RCSB",
        source_id="1EMA",
        url="https://files.rcsb.org/download/1EMA.pdb",
        ligand_resname="CRO",
        ligand_chain="A",
        ligand_resseq=66,
        note="The Thr65-Tyr66-Gly67 chromophore is modelled as the single modified residue CRO 66.",
    ),
    SiteSpec(
        id="mpro",
        name="SARS-CoV-2 Mpro + Nirmatrelvir",
        kind="complex",
        source_db="RCSB",
        source_id="7VH8",
        url="https://files.rcsb.org/download/7VH8.pdb",
        ligand_resname="4WI",
        ligand_chain="A",
        ligand_resseq=401,
        note="Nirmatrelvir (the antiviral half of Paxlovid) covalently bound at the Cys145/His41 dyad.",
    ),
    SiteSpec(
        id="cox2",
        name="COX-2 + Celecoxib",
        kind="complex",
        source_db="RCSB",
        source_id="3LN1",
        url="https://files.rcsb.org/download/3LN1.pdb",
        ligand_resname="CEL",
        ligand_chain="A",
        ligand_resseq=682,
        note=("Celecoxib in the COX-2 side pocket opened by Val523, the residue that is Ile523 in COX-1. "
              "3LN1 numbers the mature protein, so that residue is Val509 in the file; labels are shifted "
              "by +14 to match the conventional numbering used in the literature."),
        residue_label_offset=14,
    ),
    SiteSpec(
        id="azobenzene",
        name="Azobenzene Molecular Switch",
        kind="molecule",
        source_db="PubChem",
        source_id="2272",
        url="https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/2272/record/SDF?record_type=3d",
        note="Computed 3D conformer (trans). No protein pocket: the reference pose is the target.",
    ),
    SiteSpec(
        id="h2bench",
        name="H2 Hardware Benchmark",
        kind="exact",
        source_db="exact",
        source_id="H2",
        url="",
        note="Two hydrogens at the 0.7414 A equilibrium bond length; no download needed.",
    ),
]


def _cache_file(spec: SiteSpec) -> str:
    ext = "sdf" if spec.source_db == "PubChem" else "pdb"
    return os.path.join(CACHE_DIR, f"{spec.source_id}.{ext}")


def fetch_structure(spec: SiteSpec) -> Optional[str]:
    """Downloads the structure into the cache if it isn't there. Returns the path."""
    if spec.kind == "exact":
        return None
    path = _cache_file(spec)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    os.makedirs(CACHE_DIR, exist_ok=True)
    req = urllib.request.Request(spec.url, headers={"User-Agent": "project-qrotate"})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    with open(path, "wb") as handle:
        handle.write(data)
    return path


def _parse_pdb(path: str) -> tuple[list[dict], str]:
    """Minimal PDB reader: heavy atoms only, first model only."""
    atoms: list[dict] = []
    title_parts: list[str] = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("TITLE"):
                title_parts.append(line[10:].strip())
                continue
            if line.startswith("ENDMDL"):
                break
            if not line.startswith(("ATOM", "HETATM")):
                continue
            element = (line[76:78].strip() or line[12:16].strip()[:1]).upper()
            if element == "H" or element == "D":
                continue
            altloc = line[16]
            if altloc not in (" ", "A"):      # keep one conformer only
                continue
            atoms.append({
                "record": line[:6].strip(),
                "name": line[12:16].strip(),
                "resname": line[17:20].strip(),
                "chain": line[21],
                "resseq": int(line[22:26]),
                "xyz": (float(line[30:38]), float(line[38:46]), float(line[46:54])),
                "element": element,
            })
    return atoms, " ".join(title_parts)


def _parse_sdf(path: str) -> list[dict]:
    """Minimal V2000 SDF reader: heavy atoms of the first record."""
    lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
    n_atoms = int(lines[3][0:3])
    atoms = []
    for i, line in enumerate(lines[4:4 + n_atoms]):
        parts = line.split()
        element = parts[3].upper()
        if element == "H":
            continue
        atoms.append({
            "record": "SDF",
            "name": f"{element}{i + 1}",
            "resname": "AZO",
            "chain": "-",
            "resseq": 1,
            "xyz": (float(parts[0]), float(parts[1]), float(parts[2])),
            "element": element,
        })
    return atoms


def _h2_atoms() -> list[dict]:
    """H2 at its equilibrium bond length, centred on the origin."""
    half = 0.7414 / 2.0
    return [
        {"record": "EXACT", "name": "H1", "resname": "H2", "chain": "-", "resseq": 1,
         "xyz": (-half, 0.0, 0.0), "element": "H"},
        {"record": "EXACT", "name": "H2", "resname": "H2", "chain": "-", "resseq": 1,
         "xyz": (half, 0.0, 0.0), "element": "H"},
    ]


def extract_site(spec: SiteSpec) -> dict:
    """Returns the ligand atoms and the surrounding pocket atoms for one system."""
    if spec.kind == "exact":
        ligand = _h2_atoms()
        pocket = ligand
        title = "Exact H2 geometry"
    elif spec.source_db == "PubChem":
        path = fetch_structure(spec)
        ligand = _parse_sdf(path)
        pocket = ligand
        title = f"PubChem CID {spec.source_id}"
    else:
        path = fetch_structure(spec)
        atoms, title = _parse_pdb(path)
        ligand = [
            a for a in atoms
            if a["resname"] == spec.ligand_resname
            and a["chain"] == spec.ligand_chain
            and a["resseq"] == spec.ligand_resseq
        ]
        if not ligand:
            raise ValueError(
                f"{spec.id}: no atoms for {spec.ligand_resname} "
                f"{spec.ligand_chain}{spec.ligand_resseq} in {spec.source_id}"
            )
        ligand_xyz = np.array([a["xyz"] for a in ligand])
        pocket = []
        for atom in atoms:
            if atom is None or atom["resname"] in _NON_LIGAND:
                continue
            if (atom["resname"] == spec.ligand_resname
                    and atom["chain"] == spec.ligand_chain
                    and atom["resseq"] == spec.ligand_resseq):
                continue
            d = np.linalg.norm(ligand_xyz - np.array(atom["xyz"]), axis=1).min()
            if d <= spec.pocket_radius_a:
                pocket.append(atom)
        if not pocket:
            raise ValueError(f"{spec.id}: empty pocket within {spec.pocket_radius_a} A")

    offset = spec.residue_label_offset
    residues = sorted({(a["resname"], a["chain"], a["resseq"]) for a in pocket},
                      key=lambda r: (r[1], r[2]))
    # Per-atom labels, in the numbering a reader would recognise.
    atom_labels = [f"{a['resname']}{a['resseq'] + offset}" for a in pocket]
    return {
        "id": spec.id,
        "name": spec.name,
        "kind": spec.kind,
        "source": {
            "db": spec.source_db,
            "id": spec.source_id,
            "url": spec.url,
            "title": title.strip(),
        },
        "note": spec.note,
        "ligand": {
            "resname": spec.ligand_resname or (ligand[0]["resname"] if ligand else ""),
            "n_atoms": len(ligand),
            "elements": [a["element"] for a in ligand],
            "atom_names": [a["name"] for a in ligand],
            "coords": [[round(c, 3) for c in a["xyz"]] for a in ligand],
        },
        "pocket": {
            "radius_a": spec.pocket_radius_a if spec.kind == "complex" else None,
            "n_atoms": len(pocket),
            "n_residues": len(residues),
            "residue_label_offset": offset,
            "residues": [f"{r[0]}{r[2] + offset}" for r in residues],
            "atom_residues": atom_labels,
            "elements": [a["element"] for a in pocket],
            "coords": [[round(c, 3) for c in a["xyz"]] for a in pocket],
        },
    }


def build_active_sites(
    out_path: str = ACTIVE_SITES_JSON,
    js_path: Optional[str] = "assets/active_sites.js",
    verbose: bool = True,
) -> dict:
    """Extracts all six active sites and writes the committed JSON."""
    sites = []
    for spec in SITE_SPECS:
        site = extract_site(spec)
        sites.append(site)
        if verbose:
            print(f"[{spec.id:10s}] {site['source']['db']} {site['source']['id']}: "
                  f"ligand {site['ligand']['n_atoms']} atoms "
                  f"({site['ligand']['resname'] or 'n/a'}), "
                  f"pocket {site['pocket']['n_atoms']} atoms / "
                  f"{site['pocket']['n_residues']} residues")

    payload = {
        "active_sites": sites,
        "generated_by": "src/qrotate/structures.py::build_active_sites",
        "licence_note": (
            "Coordinates are from the RCSB PDB (CC0) and PubChem (public domain). "
            "Raw files are cached in .cache/structures/ and are not committed."
        ),
    }
    if out_path:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        if verbose:
            print(f"\n[Saved active sites to {out_path}]")

    # The 3D page needs the same atoms, and must work from file:// where
    # fetch() of a local JSON is blocked, so ship a plain script too.
    if js_path:
        os.makedirs(os.path.dirname(os.path.abspath(js_path)), exist_ok=True)
        with open(js_path, "w", encoding="utf-8") as handle:
            handle.write("// Generated by src/qrotate/structures.py::build_active_sites\n")
            handle.write("// Experimental coordinates from the RCSB PDB and PubChem.\n")
            handle.write("// Do not edit by hand: re-run `python -m src.qrotate.structures`.\n")
            handle.write("window.QROTATE_ACTIVE_SITES = ")
            json.dump(payload, handle, separators=(",", ":"))
            handle.write(";\n")
        if verbose:
            print(f"[Saved active sites to {js_path}]")
    return payload


_ACTIVE_SITES_CACHE: dict = {}


def load_active_sites(path: str = ACTIVE_SITES_JSON) -> dict:
    """Reads the committed JSON. Returns {} when it is missing, so callers can
    fall back rather than requiring the network."""
    if _ACTIVE_SITES_CACHE:
        return _ACTIVE_SITES_CACHE
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    _ACTIVE_SITES_CACHE.update({s["id"]: s for s in payload.get("active_sites", [])})
    return _ACTIVE_SITES_CACHE


def site_coordinates(system_id: str) -> Optional[tuple[np.ndarray, np.ndarray]]:
    """(pocket_coords, ligand_coords) in Angstroms, or None if unavailable."""
    site = load_active_sites().get(system_id)
    if not site:
        return None
    return (
        np.array(site["pocket"]["coords"], dtype=float),
        np.array(site["ligand"]["coords"], dtype=float),
    )


if __name__ == "__main__":
    build_active_sites()
