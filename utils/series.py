"""
Scalar Python series-processing routines for step 5.

These are direct ports of gistemp4.0/steps/series.py.  All arithmetic is
performed with scalar Python (no NumPy) to match gistemp4.0's sequential
summation and avoid FMA/SIMD divergence.
"""

MISSING = 9999.0


def valid(v):
    return v != MISSING


def invalid(v):
    return v == MISSING


def combine(composite, weight, new, new_weight, min_overlap):
    """GISTEMP combining algorithm (scalar Python port of v4 series.combine).

    Merges *new* into *composite* in place, adjusting for per-month bias.
    *new_weight* may be a scalar or a list matching *weight*.
    Returns a 12-element list of how many new data were combined per month.
    """
    if not hasattr(new_weight, '__getitem__'):
        new_weight = [new_weight] * len(weight)

    data_combined = [0] * 12
    for m in range(12):
        sum_new = 0.0
        sum_comp = 0.0
        count = 0
        for a, n in zip(composite[m::12], new[m::12]):
            if invalid(a) or invalid(n):
                continue
            count += 1
            sum_comp += a
            sum_new += n
        if count < min_overlap:
            continue
        bias = (sum_comp - sum_new) / count

        for i in range(m, len(new), 12):
            if invalid(new[i]):
                continue
            new_mo_wt = weight[i] + new_weight[i]
            composite[i] = (weight[i] * composite[i]
                            + new_weight[i] * (new[i] + bias)) / new_mo_wt
            weight[i] = new_mo_wt
            data_combined[m] += 1

    return data_combined


def valid_mean(seq, min_count=1):
    """Mean of valid elements in *seq*; MISSING if fewer than *min_count* valid."""
    total = 0.0
    count = 0
    for x in seq:
        if valid(x):
            total += x
            count += 1
    if count >= min_count:
        return total / count
    return MISSING


def anomalize(data, reference_period=None, base_year=-9999):
    """Convert *data* (flat list, one entry per month) to anomalies in place.

    Monthly means are computed over *reference_period* (first, last year inclusive).
    If a month has no data in the reference period, the whole-series mean is used.
    Port of gistemp4.0/steps/series.py::anomalize + monthly_anomalies.
    """
    years = len(data) // 12
    if reference_period:
        base  = reference_period[0] - base_year
        limit = reference_period[1] - base_year + 1
    else:
        base = limit = 0

    for m in range(12):
        row = data[m::12]
        mean = valid_mean(row[base:limit])
        if invalid(mean):
            mean = valid_mean(row)
        if invalid(mean):
            data[m::12] = [MISSING] * years
        else:
            data[m::12] = [(x - mean if valid(x) else MISSING) for x in row]
