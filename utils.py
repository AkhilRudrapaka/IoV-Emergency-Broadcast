import math

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
