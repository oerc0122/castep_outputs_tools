"""Process castep .md file for phononic information."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from itertools import product as cart_prod
from itertools import zip_longest
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, TextIO

import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
import periodictable
from castep_outputs.utilities.utility import get_only

try:
    from tqdm import tqdm
except ImportError:

    def tdqm(it, *_a, **_kw):
        """
        Drop all but iterator.

        Dummy function.
        """
        return it


from castep_outputs_tools.md_geom_parser import MDGeomParser

if TYPE_CHECKING:
    from collections.abc import Callable

    from castep_outputs.utilities.datatypes import ThreeByThreeMatrix


class Data(NamedTuple):
    """Container for processed data."""

    n_frames: int
    n_atoms: int
    n_samples: int
    n_discard: int
    species: Counter
    time_step: float
    time: npt.NDArray[np.floating]
    positions: npt.NDArray[np.floating]
    velocities: npt.NDArray[np.floating]
    masses: npt.NDArray[np.floating]
    temperature: npt.NDArray[np.floating]
    cell_vec: ThreeByThreeMatrix


SPEED_OF_LIGHT = 299_792_458
FSEC_TO_CM_1 = 1e15 / (100 * SPEED_OF_LIGHT)

HAU_TO_SI = {
    "T": 3.157746455e5,
    "t": 0.02418884328,
    "l": 0.529177,  # Ang
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyse a CASTEP molecular dynamics trajectory file to extract phonon information"
        ),
    )

    parser.add_argument(
        "md_file",
        type=Path,
        help="CASTEP molecular dynamics trajectory file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=argparse.FileType("w", encoding="utf-8"),
        default=sys.stdout,
        help="Output file to write, Default is to standard output",
    )
    parser.add_argument(
        "-d",
        "--discard",
        type=int,
        default=0,
        help="Discard n number of points from beginning of md file",
    )
    parser.add_argument(
        "-T",
        "--temperature",
        type=Path,
        help="Output temperature data file and graph",
    )
    parser.add_argument(
        "-cvt",
        "--c_v_t",
        type=Path,
        help="Output c_v_t data file and graph",
    )
    parser.add_argument(
        "-cw",
        "--c_w",
        type=Path,
        help="Output C_w data file and graph",
    )
    parser.add_argument(
        "-iw",
        "--i_w",
        type=Path,
        help="Output I_w data file and graph",
    )
    parser.add_argument(
        "-iqw",
        "--i_q_w",
        type=Path,
        help="Output I_q_w data file and graph",
    )
    parser.add_argument(
        "-w",
        "--write_data",
        action="store_false",
        help="Write data to file. Default is on.",
    )
    parser.add_argument(
        "-g",
        "--save_graphs",
        action="store_false",
        help="Toggle graphs off. Default is on.",
    )
    parser.add_argument(
        "-s",
        "--show_graphs",
        action="store_true",
        help="Toggle showing graphs on.",
    )
    parser.add_argument(
        "--supercell",
        nargs=3,
        type=int,
        help="Supercell for q-point phonon calc",
    )
    return parser


def restack_data(
    lag: npt.NDArray[np.floating],
    data: npt.NDArray[np.floating],
) -> npt.NDArray[np.floating]:
    return np.vstack((lag, *(row for block in data for row in block))).T


def read_data(
    md_file: Path | str,
    log_output: TextIO,
    discard: int = 0,
    supercell: tuple[int, int, int] | None = None,
) -> Data:
    configuration = MDGeomParser(md_file)

    first_frame, second_frame = configuration[discard : discard + 2]
    n_frames = len(configuration)
    species = Counter(spec for spec, _ in second_frame["ions"])
    n_atoms = species.total()
    time_step = (second_frame["time"] - first_frame["time"]) * HAU_TO_SI["t"]
    n_samples = n_frames - discard

    if supercell and any(count % np.prod(supercell) for count in species.values()):
        raise ValueError(
            f"All numbers of atoms ({', '.join(species.values())})"
            f"need to be divisible by supercelling ({supercell})",
        )

    # Total number of configurations from md files
    print(f"Total number of configurations: {n_frames}", file=log_output)
    print(f"Number of configurations to discard: {discard}", file=log_output)
    print(f"Number of samples: {n_samples}", file=log_output)

    # Number of species in each configuration
    print(f"Number of species: {len(species)}", file=log_output)
    print(f"Elements present: {', '.join(species)}", file=log_output)
    print(f"Total number of atoms: {n_atoms}", file=log_output)

    positions = np.empty((3, n_atoms, n_samples), dtype=float)
    velocities = np.empty((3, n_atoms, n_samples), dtype=float)
    masses = np.empty(n_atoms, dtype=float)
    temperature = np.empty(n_samples, dtype=float)
    time = np.empty(n_samples, dtype=float)

    frames = iter(configuration)
    if discard:
        next(frames)
        frames.send(discard - 1)

    for idx, frame in enumerate(tqdm(frames, total=n_samples)):
        temperature[idx] = get_only(*frame["temperature"])
        time[idx] = frame["time"]

        for atom_id, ((spec, _), atom) in enumerate(frame["ions"].items()):
            positions[:, atom_id, idx] = atom["position"]
            velocities[:, atom_id, idx] = atom["velocity"]
            masses[atom_id] = getattr(periodictable, spec).mass

    temperature *= HAU_TO_SI["T"]
    time *= HAU_TO_SI["t"]
    positions *= HAU_TO_SI["l"]
    velocities *= HAU_TO_SI["l"] / HAU_TO_SI["t"]

    return Data(
        n_frames=n_frames,
        n_atoms=n_atoms,
        n_samples=n_samples,
        n_discard=discard,
        species=species,
        time_step=time_step,
        time=time,
        positions=positions,
        velocities=velocities,
        masses=masses,
        temperature=temperature,
        cell_vec=np.array(first_frame["h"]),
    )


def compute_vaf(
    velocities: npt.NDArray[np.floating],
    time_step: float,
) -> tuple[
    tuple[npt.NDArray[np.floating], npt.NDArray[np.floating]],
    tuple[npt.NDArray[np.floating], npt.NDArray[np.floating]],
]:
    _, n_atoms, n_steps = velocities.shape

    c_v_tot = np.asarray(
        [
            [
                np.correlate(velocities[i, j, :], velocities[i, j, :], "full")[n_steps - 1 :]
                for j in range(n_atoms)
            ]
            for i in range(3)
        ],
    )

    c_v_tot /= n_steps - np.arange(n_steps)
    c_v_lags = np.arange(n_steps) * time_step

    c_w_tot = np.fft.rfft(c_v_tot, axis=2).real
    c_w_lags = np.fft.fftfreq(n_steps, time_step) * FSEC_TO_CM_1

    return (c_v_lags, c_v_tot), (c_w_lags, c_w_tot)


def compute_qspc_phonon(
    positions: npt.NDArray[np.floating],
    velocities: npt.NDArray[np.floating],
    latt: ThreeByThreeMatrix,
    supercell: tuple[int, int, int],
) -> tuple[
    npt.NDarray[np.floating],
    npt.NDarray[np.floating],
    npt.NDarray[np.floating],
]:
    def inv_space(par: int):
        return 0 if par == 0 else 1 / (par + 1)

    # Set up KPts
    k_points = tuple(cart_prod(*map(range, supercell)))
    q_points = np.array([[*map(inv_space, kpt)] for kpt in k_points])
    n_kpts = q_points.shape[0]

    print(f"The {n_kpts} k points are:\n{q_points}")

    # Setup lattice
    latt = np.array(latt)
    supercell = np.array(supercell, dtype=int)
    inv_latt = np.linalg.inv(latt)
    inv_supercell = 1 / supercell
    a_vec, b_vec, c_vec = red_latt = inv_supercell * latt
    a_prime, b_prime, c_prime = q_latt = 2 * np.pi * np.linalg.inv(red_latt.T)

    n_dim, n_atoms, n_frames = positions.shape

    # Set up indices
    i_index = range(n_atoms)
    b_index = []
    b_r_index = []

    for pos in np.nditer(positions[:, :, 0], ["external_loop"]):
        inv_position = pos @ inv_latt

        for i, b_indexed in enumerate(b_index):
            position = inv_position % inv_supercell[0]
            if round(position, 15) == round(b_indexed, 15):
                b_r_index += [[i, *map(int, inv_position * inv_supercell)]]
                break
        else:
            at_pos, loc_pos = divmod(position, inv_supercell)
            b_r_index.append([len(b_index), *map(int, at_pos)])
            b_index.append(loc_pos)

    ref = dict(zip(i_index, b_r_index, strict=True))

    v_b_q_tot = np.empty((n_kpts, 3, n_atoms, n_frames), dtype=np.complex_)

    # calculate v_b_q from Eq B18
    for k, qpt in q_points:
        q = q_latt @ qpt

        for i, (ind, *pos) in enumerate(ref.values()):
            q_r = np.dot(q, red_latt @ pos)
            exp = np.exp(1j * q_r)
            for n in range(velocities.shape[2]):
                v_b_q_tot[k, :, ind, n] = velocities[:, i, n] * exp

    c_v_b = np.empty((n_kpts, 3, n_atoms, n_frames), dtype=np.complex_)
    c_q_b = np.empty((n_kpts, 3, n_atoms, n_frames), dtype=np.complex_)

    # Calculation of equation B19
    for kpt_v in v_b_q_tot:
        ((_, c_v_b[k, :, :, :]), (_, c_q_b[k, :, :, :])) = compute_vaf(kpt_v, 1.0)

    return c_v_b, c_q_b


def output(
    x: tuple[str, npt.NDArray[np.floating]],
    y: tuple[str, npt.NDArray[np.floating]],
    *,
    title: str,
    out_file: Path | None,
    plot_graphs: bool,
    show_graphs: bool,
    write_data: bool,
    process_for_plot: Callable | None = None,
    process_for_write: Callable | None = None,
    labels: tuple[str] = (),
) -> None:
    """
    Output data and plot relevant graphs.

    Parameters
    ----------
    x
        Label and data.
    y
        Label and data.
    out_file : Path
        Path to write data and plot graph to.
    plot_graphs : bool
        Whether to plot graphs.
    show_graphs : bool
        Whether to display the graphs.
    """
    if not out_file:
        return

    xlabel, xdata = x
    ylabel, ydata = y

    if write_data:
        data = process_for_write(xdata, ydata)
        np.savetxt(out_file, data)

    if isinstance(ydata, np.ndarray):
        ydata = (ydata,)
    if process_for_plot is not None:
        ydata = map(process_for_plot, ydata)

    fig = plt.figure()
    ax = fig.gca()

    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    for line, label in zip_longest(ydata, labels):
        ax.plot(xdata, line, label=label)

    if labels:
        fig.legend()

    if show_graphs:
        fig.show()

    if plot_graphs:
        fig.savefig(out_file.with_suffix(".png"))


def main() -> None:
    args = build_parser().parse_args()

    graph_args = {
        "write_data": args.write_data,
        "plot_graphs": args.save_graphs,
        "show_graphs": args.show_graphs,
    }

    if not any(graph_args.values()):
        print("Nothing to do.")
        return

    if not args.md_file.exists():
        raise FileNotFoundError(f"Cannot find input .md file ({args.md_file})")

    data = read_data(args.md_file, args.output, args.discard, args.supercell)

    print(f"Average temperature is: {np.mean(data.temperature)} K", file=args.output)
    output(
        ("Time (fs)", data.time),
        ("Temperature (K)", data.temperature),
        title="Temperature vs time",
        out_file=args.temperature,
        process_for_write=lambda *x: np.vstack(x).T,
        **graph_args,
    )

    c_v, c_w = compute_vaf(data.velocities, data.time_step)
    half = (data.n_samples + 1) // 2
    c_w = c_w[0][:half], c_w[1]

    output(
        ("Time (fs)", c_v[0]),
        ("$C_{vv}$(t)", c_v[1]),
        title="Velocity Autocorrelation Function",
        out_file=args.c_v_t,
        process_for_write=restack_data,
        process_for_plot=lambda x: np.sum(np.average(x, axis=0), axis=0),
        **graph_args,
    )

    output(
        (r"$\omega$ (cm$^{-1}$)", c_w[0]),
        ("$C_{w}$(w)", c_w[1]),
        title="Phonon DOS",
        out_file=args.c_w,
        process_for_write=restack_data,
        process_for_plot=lambda x: np.average(np.sum(x, axis=1), axis=0),
        **graph_args,
    )

    i_w = c_w[0], np.einsum("ijk,j->ik", c_w[1].real, data.masses)

    output(
        (r"$\omega$ (cm$^{-1}$)", i_w[0]),
        ("$I_{w}$(w)", tuple(direc for direc in i_w[1])),
        title="Mass-weighted Phonon DOS",
        process_for_write=lambda x, y: np.vstack((x, *y)).T,
        out_file=args.i_w,
        labels="xyz",
        **graph_args,
    )

    if args.supercell:
        c_v_b, c_q_b = compute_qspc_phonon(
            data.positions,
            data.velocities,
            data.cell_vec,
            args.supercell,
        )
        i_q = np.einsum("ijkl,k->ijl", c_q_b, data.masses)

        # output_phonon(c_v_b, i_q,
        #               cw_file=


if __name__ == "__main__":
    main()
