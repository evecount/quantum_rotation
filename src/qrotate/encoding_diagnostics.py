"""Measures what the phase encoding can and cannot tell apart.

The pose-recovery benchmark in `metrics.py` says how fast the blind loop finds
a known answer. It says nothing about whether the register actually describes
the molecule, and the encoder this project shipped for most of its life failed
exactly there: it chunked atoms by their order in the input file and used only
the azimuth, so a reordered copy of a ligand scored 0.52 against itself and a
mirror image scored 0.99.

This module measures those properties directly, on the six benchmark ligands,
and writes the numbers to benchmarks/encoding_diagnostics.json so the claims in
the README are reproducible rather than asserted:

    self          same molecule, same coordinates. The ceiling, which is below
                  1.0 because the SWAP-test circuit evolves the probe register
                  by U_tube(tau) and leaves the target alone.
    permuted      same molecule, atoms listed in a different order. Should
                  equal `self`: atom order is not chemistry.
    mirrored      the molecule reflected through z. Should be well below
                  `self`: enantiomers are different drugs.
    noise_0.1A    coordinates jittered by 0.1 A, about experimental
                  uncertainty. Should stay high, or the encoding is too
                  brittle to use on measured structures.
    cross         the worst overlap between two *different* ligands. Should be
                  low, or the method reports false matches.
"""

from __future__ import annotations

import json
import os
from typing import Optional

import numpy as np

try:
    from .hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases
    from .circuits import simulate_swap_test_statevector
    from .structures import load_active_sites
except ImportError:
    from src.qrotate.hpc_bridge import MolecularGeometry, pocket_ligand_to_qubit_phases
    from src.qrotate.circuits import simulate_swap_test_statevector
    from src.qrotate.structures import load_active_sites

TAU = 0.25
OMEGA = (1.0, 0.5, 0.25)


def _phases(elements, coords, n_qubits=4):
    return pocket_ligand_to_qubit_phases(
        MolecularGeometry("m", list(elements), np.asarray(coords, dtype=float)),
        n_qubits=n_qubits,
    )


def _overlap(a, b) -> float:
    return simulate_swap_test_statevector(a, b, TAU, OMEGA)


def run_encoding_diagnostics(
    n_qubits: int = 4,
    noise_sigma_a: float = 0.1,
    noise_repeats: int = 5,
    seed: int = 20260920,
    output_json_path: Optional[str] = "benchmarks/encoding_diagnostics.json",
) -> dict:
    sites = load_active_sites()
    if not sites:
        print("SKIP: benchmarks/active_sites.json missing; run `python -m src.qrotate.structures`")
        return {}

    rng = np.random.default_rng(seed)
    ids = list(sites)
    coords = {i: np.array(sites[i]["ligand"]["coords"], dtype=float) for i in ids}
    elements = {i: sites[i]["ligand"]["elements"] for i in ids}
    registers = {i: _phases(elements[i], coords[i], n_qubits) for i in ids}

    rows = []
    print("=" * 86)
    print("ENCODING DIAGNOSTICS: what the phase register can tell apart")
    print("=" * 86)
    print(f"{'system':<12} {'self':>7} {'permuted':>9} {'mirrored':>9} "
          f"{'noise':>7} {'worst cross-match':>19}")

    for sid in ids:
        c, e = coords[sid], elements[sid]
        self_overlap = _overlap(registers[sid], registers[sid])

        order = rng.permutation(len(c))
        permuted = _overlap(registers[sid], _phases([e[k] for k in order], c[order], n_qubits))

        flipped = c.copy()
        flipped[:, 2] *= -1.0
        mirrored = _overlap(registers[sid], _phases(e, flipped, n_qubits))

        noisy = float(np.mean([
            _overlap(registers[sid], _phases(e, c + rng.normal(0, noise_sigma_a, c.shape), n_qubits))
            for _ in range(noise_repeats)
        ]))

        others = [(other, _overlap(registers[sid], registers[other])) for other in ids if other != sid]
        worst_id, worst = max(others, key=lambda kv: kv[1])

        rows.append({
            "system_id": sid,
            "self": round(self_overlap, 4),
            "permuted": round(permuted, 4),
            "mirrored": round(mirrored, 4),
            f"noise_{noise_sigma_a}A": round(noisy, 4),
            "worst_cross_match": {"system_id": worst_id, "p0": round(worst, 4)},
        })
        print(f"{sid:<12} {self_overlap:7.3f} {permuted:9.3f} {mirrored:9.3f} "
              f"{noisy:7.3f} {worst:9.3f} ({worst_id})")

    payload = {
        "encoding_diagnostics": rows,
        "n_qubits": n_qubits,
        "noise_sigma_a": noise_sigma_a,
        "tau": TAU,
        "omega": list(OMEGA),
        "notes": (
            "self is the ceiling, below 1.0 because the circuit evolves the probe "
            "register only. permuted should equal self; mirrored and cross-match "
            "should be far below it."
        ),
        "source": "src/qrotate/encoding_diagnostics.py::run_encoding_diagnostics",
    }

    print("-" * 86)
    print(f"permuted vs self  : max gap {max(abs(r['self'] - r['permuted']) for r in rows):.4f} "
          "(0 means atom order is irrelevant, which is the point)")
    print(f"mirrored          : mean {np.mean([r['mirrored'] for r in rows]):.3f}")
    print(f"worst cross-match : {max(r['worst_cross_match']['p0'] for r in rows):.3f}")

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\n[Saved encoding diagnostics to {output_json_path}]")

    return payload


def run_all_register_sizes(
    output_json_path: Optional[str] = "benchmarks/encoding_diagnostics.json",
) -> dict:
    """Both register sizes the project offers, because they trade off against
    each other: more shells separate different molecules far better, but each
    shell then holds fewer atoms and is more easily moved by coordinate error.
    """
    payload = {"by_register_size": {}}
    for n_qubits in (4, 8):
        print()
        result = run_encoding_diagnostics(n_qubits=n_qubits, output_json_path=None)
        if not result:
            return {}
        payload["by_register_size"][str(n_qubits)] = result

    payload["source"] = "src/qrotate/encoding_diagnostics.py::run_all_register_sizes"
    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\n[Saved encoding diagnostics to {output_json_path}]")
    return payload


if __name__ == "__main__":
    run_all_register_sizes()
