"""Circuit definitions and Repeat-Until-Success (RUS) engine in Guppy and Pytket.

Implements the blind parity test (SWAP test), dimensional rotation U_tube(tau),
and adaptive phase cascading feedback.
"""

from __future__ import annotations

from typing import Sequence
import numpy as np

# Guppy imports
from guppylang import guppy
try:
    from guppylang.std.builtins import output
except ImportError:
    from guppylang.std.builtins import result as output

from guppylang.std.quantum import (
    qubit,
    measure,
    reset,
    h,
    cx,
    ry,
    rz,
    toffoli,
)

# Pytket imports
from pytket.circuit import Circuit, OpType, Qubit
from pytket.passes import AutoRebase
from aqora.pytket.backend import GATESET


def rebase_to_h2_gateset(circuit: Circuit) -> Circuit:
    """Rebases an arbitrary Pytket circuit into Quantinuum H-series native GATESET."""
    compiled = circuit.copy()
    AutoRebase(GATESET).apply(compiled)
    return compiled


# =====================================================================
# 1. Pytket Quantum Circuit Builders (Native H-Series Compatible)
# =====================================================================

def build_pytket_swap_test_circuit(
    pocket_phases: Sequence[float],
    ligand_phases: Sequence[float],
    tau: float,
    omega: tuple[float, float, float],
) -> Circuit:
    """Builds a Pytket circuit implementing the blind parity SWAP test."""
    n_sites = len(pocket_phases)
    n_total = 2 * n_sites + 1
    circ = Circuit(n_total, 1)

    ancilla = 0
    pocket_reg = list(range(1, n_sites + 1))
    ligand_reg = list(range(n_sites + 1, n_total))

    # 1. State preparation (encoding coordinate phases)
    for i in range(n_sites):
        # Prepare pocket state |psi_pocket>
        circ.Ry(0.5, pocket_reg[i])
        circ.Rz(pocket_phases[i] / np.pi, pocket_reg[i])

        # Prepare initial ligand state |psi_ligand>
        circ.Ry(0.5, ligand_reg[i])
        circ.Rz(ligand_phases[i] / np.pi, ligand_reg[i])

    # 2. Apply U_tube evolution to ligand register
    wx, wy, wz = omega
    for i in range(n_sites):
        circ.Ry((wy * tau) / np.pi, ligand_reg[i])
        circ.Rz((wz * tau) / np.pi, ligand_reg[i])

    # 3. Ancilla-mediated Blind Parity Test (SWAP test)
    circ.H(ancilla)
    for i in range(n_sites):
        # Fredkin (CSWAP) decomposition: CX + CCX + CX
        circ.CX(ligand_reg[i], pocket_reg[i])
        circ.add_gate(OpType.CCX, [ancilla, pocket_reg[i], ligand_reg[i]])
        circ.CX(ligand_reg[i], pocket_reg[i])
    circ.H(ancilla)

    # 4. Measure parity
    circ.Measure(ancilla, 0)
    return circ


def build_pytket_rus_simulation(
    pocket_phases: Sequence[float],
    ligand_phases: Sequence[float],
    tau: float,
    omega: tuple[float, float, float],
    max_attempts: int = 3,
) -> list[Circuit]:
    """Generates the sequence of adaptive circuits simulating the RUS loop steps."""
    circuits = []
    current_ligand_phases = list(ligand_phases)

    for attempt in range(max_attempts):
        circ = build_pytket_swap_test_circuit(
            pocket_phases, current_ligand_phases, tau, omega
        )
        circuits.append(circ)
        # Adaptively dampen phase mismatch for next iteration
        current_ligand_phases = [
            l + 0.5 * (p - l) for p, l in zip(pocket_phases, current_ligand_phases)
        ]

    return circuits


# =====================================================================
# 2. Guppy Quantum-Classical Dynamic Circuit (Native RUS Engine)
# =====================================================================

@guppy.comptime
def guppy_qrotate_rus_demo() -> None:
    """End-to-end Project Q-Rotate execution in Guppy.

    Demonstrates state encoding, dimensional rotation U_tube,
    ancilla-mediated blind parity testing, and mid-circuit dynamic reset.
    """
    # 1. Allocate registers: 1 pocket qubit, 1 ligand qubit, 1 parity ancilla
    q_pocket = qubit()
    q_ligand = qubit()
    ancilla = qubit()

    from guppylang.std.angles import angle

    # 2. Initialize feature states
    h(q_pocket)
    rz(q_pocket, angle(0.25))

    h(q_ligand)
    rz(q_ligand, angle(0.4))

    # 3. Apply U_tube rotation
    ry(q_ligand, angle(0.15))
    rz(q_ligand, angle(0.1))

    # 4. Blind Parity Test (SWAP test)
    h(ancilla)
    cx(q_ligand, q_pocket)
    toffoli(ancilla, q_pocket, q_ligand)
    cx(q_ligand, q_pocket)
    h(ancilla)

    # 5. Measure and output parity
    m_parity = measure(ancilla)
    output("parity_error", m_parity)

    # 6. Measure remaining qubits
    m_p = measure(q_pocket)
    m_l = measure(q_ligand)
    output("pocket_state", m_p)
    output("ligand_state", m_l)
