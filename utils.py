import math

try:
    from config import V2V_DATA_RATE_BPS, BASE_MESSAGE_SIZE_BYTES, PER_HOP_PROCESSING_MS
except ImportError:
    V2V_DATA_RATE_BPS = 6_000_000
    BASE_MESSAGE_SIZE_BYTES = 300
    PER_HOP_PROCESSING_MS = 1.0


def compute_delay_ms(hops, signature_bytes=0, verification_ms=0.0):
    """
    Analytic end-to-end delay: per-hop 802.11p-typical transmission + processing
    time, plus real measured cryptographic verification time. Shared by both the
    PROPOSED and FLOODING arms of the evaluation harness so any delay difference
    between them comes from real per-run quantities (hop count, signature size,
    measured verify time), not from independently tuned per-algorithm constants.
    """
    message_bits = (BASE_MESSAGE_SIZE_BYTES + signature_bytes) * 8
    transmission_ms = (message_bits / V2V_DATA_RATE_BPS) * 1000.0
    return max(1, hops) * (transmission_ms + PER_HOP_PROCESSING_MS) + verification_ms


def euclidean_distance(pos1, pos2):
    """
    Calculates Euclidean distance between two 2D point coordinates (x, y).
    """
    return math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])


def sumo_angle_to_radians(angle_deg):
    """
    Converts a SUMO navigational heading (degrees, 0=North, clockwise-positive)
    into standard math radians (0=+x axis/East, counter-clockwise-positive)
    suitable for (cos, sin) velocity-vector decomposition.
    """
    return math.radians(90.0 - angle_deg)


def angle_diff_deg(a_deg, b_deg):
    """
    Returns the smallest wrapped angular difference between two headings
    given in degrees, in the range [0, 180].
    """
    diff = abs(a_deg - b_deg) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff
