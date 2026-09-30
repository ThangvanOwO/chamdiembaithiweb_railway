"""CPU-light preparation for the validated raw-paper Live reader.

The reader already aligns and measures the original warped pixels. Heavy
denoising/illumination passes cannot improve that evidence; they were used only
to seed the Part III offset and to produce discarded legacy answers. Keep the
original path whenever the local grids cannot be fitted reliably.
"""
import cv2


def raw_gray(warped):
    return cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) if warped.ndim == 3 else warped.copy()


def part3_grids_aligned(part3_details):
    """Only Part III depends on the offset seeded by legacy preprocessing.

IDs, Part I and Part II always use the same raw pixels and fixed zero offsets
in both routes, even when their local fit fails. Repeating heavy preprocessing
cannot change their result. Part III must fall back if any grid fit fails,
because its unaligned reader would otherwise measure at a different seed.
"""
    return all(detail.get('live_grid', {}).get('aligned', False) for detail in part3_details.values())
