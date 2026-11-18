"""Generate 12 scalar quantization datasets and report the observed D by N.

N is the number of observations in a slice. D is the number of distinct
values in that slice. Each file contains seven consecutive, nonoverlapping
slices, in the order below, for a total of 2,080,768 observations.

Default-seed reference counts

          N  D (each of the 10 continuous datasets)  D (triangular)  D (zero spike)
     16,384                                  16,384           3,590           3,528
     32,768                                  32,768           3,839           4,026
     65,536                                  65,536           3,960           4,093
    131,072                                 131,072           4,032           4,096
    262,144                                 262,144           4,068           4,096
    524,288                                 524,288           4,082           4,096
  1,048,576                               1,048,576           4,087           4,096

Running the script writes the datasets to input/ in the current working
directory. It saves the observed D counts to dataset_slice_counts.csv
and prints a copy of that table.
"""

import csv
from pathlib import Path

import numpy as np


SAMPLE_SIZES = tuple(2 ** exponent for exponent in range(14, 21))
NSAMPLES = sum(SAMPLE_SIZES)
SEED = 2048


def dataset_rng(stream_id):
    # Fixed child stream IDs keep each dataset reproducible if the order changes.
    child_seed = np.random.SeedSequence(SEED, spawn_key=(stream_id,))
    return np.random.Generator(np.random.PCG64(child_seed))


def generate_datasets():
    half = NSAMPLES // 2

    # Uniform on [0, 1).
    yield "uniform_continuous", dataset_rng(0).uniform(0, 1, NSAMPLES)

    # Standard normal with mean 0 and standard deviation 1.
    yield "gaussian_continuous", dataset_rng(1).normal(0, 1, NSAMPLES)

    # Exponential with rate 1 (NumPy takes the reciprocal rate as its scale).
    yield "exponential_continuous", dataset_rng(2).exponential(1, NSAMPLES)

    # Weibull with shape 1.5 and unit scale.
    yield "weibull_continuous", dataset_rng(3).weibull(1.5, NSAMPLES)

    # Lognormal with underlying normal mean 0 and standard deviation 1.
    yield "lognormal_continuous", dataset_rng(4).lognormal(0, 1, NSAMPLES)

    # Gaussian mixture with 60% N(0, 1²) and 40% N(5, 2²).
    rng = dataset_rng(6)
    n_first = int(0.6 * NSAMPLES)
    mixture = np.concatenate((
        rng.normal(0, 1, n_first),
        rng.normal(5, 2, NSAMPLES - n_first),
    ))
    rng.shuffle(mixture)
    yield "gmm_continuous", mixture

    # Equal-weight mixture of Weibull(shape 1.5, scale 1) and N(-2, 1²).
    rng = dataset_rng(8)
    mixture = np.concatenate((
        rng.weibull(1.5, half),
        rng.normal(-2, 1, NSAMPLES - half),
    ))
    rng.shuffle(mixture)
    yield "wg_mixture_continuous", mixture

    # Equal-weight mixture of two separated normals N(-5, 1.5²) and N(5, 1.5²).
    rng = dataset_rng(9)
    mixture = np.concatenate((
        rng.normal(-5, 1.5, half),
        rng.normal(5, 1.5, NSAMPLES - half),
    ))
    rng.shuffle(mixture)
    yield "bimodal_gaussian_continuous", mixture

    # Equal-weight mixture of N(-2, 1²) and a continuous uniform on [2, 4).
    rng = dataset_rng(10)
    mixture = np.concatenate((
        rng.normal(-2, 1, half),
        rng.uniform(2, 4, NSAMPLES - half),
    ))
    rng.shuffle(mixture)
    yield "mixed_continuous", mixture

    # Truncated mixture of N(-5, 1²) and N(5, 1²) at roughly 2:1 weights.
    # Oversample both components, filter to (-7, 7), then shuffle before slicing.
    rng = dataset_rng(11)
    candidates = np.concatenate((
        rng.normal(-5, 1, int(0.8 * NSAMPLES)),
        rng.normal(5, 1, int(0.4 * NSAMPLES)),
    ))
    truncated = candidates[(candidates > -7) & (candidates < 7)]
    if truncated.size < NSAMPLES:
        raise RuntimeError("Too few candidates survived to fill the truncated dataset.")
    rng.shuffle(truncated)
    yield "truncated_continuous", truncated[:NSAMPLES]

    # Discrete triangular on integers -2,047 through 2,047. Adding two
    # independent uniform integer samples makes central values more frequent.
    rng = dataset_rng(12)
    triangular = rng.integers(0, 2048, NSAMPLES) + rng.integers(0, 2048, NSAMPLES)
    triangular -= 2047
    yield "triangular_discrete", triangular

    # Zero-spike mixture with exactly half the full sample set to zero.
    # Draw the other half uniformly from integers 1 through 4,095 and shuffle.
    rng = dataset_rng(13)
    spike_uniform = np.zeros(NSAMPLES, dtype=np.int64)
    spike_uniform[half:] = rng.integers(1, 4096, NSAMPLES - half)
    rng.shuffle(spike_uniform)
    yield "spike_uniform_discrete", spike_uniform


def distinct_counts(data):
    counts = []
    start = 0
    for size in SAMPLE_SIZES:
        stop = start + size
        counts.append(np.unique(data[start:stop]).size)
        start = stop
    return counts


def main():
    output_dir = Path("input")
    output_dir.mkdir(parents=True, exist_ok=True)
    distinct_by_dataset = {}
    for label, data in generate_datasets():
        print(f"generating {label}", flush=True)
        np.savetxt(output_dir / f"{label}.txt", data, fmt="%.18f")
        distinct_by_dataset[label] = distinct_counts(data)

    with Path("dataset_slice_counts.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["dataset", *(f"D_at_N_{size}" for size in SAMPLE_SIZES)])
        writer.writerows([label, *counts] for label, counts in distinct_by_dataset.items())

    print("\nDistinct values (D) by sample size (N)")
    print(f"{'Dataset':<29}" + "".join(f"{size:>11,}" for size in SAMPLE_SIZES))
    for label, counts in distinct_by_dataset.items():
        print(f"{label:<29}" + "".join(f"{count:>11,}" for count in counts))


if __name__ == "__main__":
    main()
