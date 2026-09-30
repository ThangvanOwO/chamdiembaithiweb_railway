# Camera shadow regression

`1029.png` and `1048.png` are lossless grayscale crops from the user's
2026-09-30 camera captures, rectified with the exact corners detected by the
app. Crop coordinates in the 1400 x 1920 warp are x=[35,225), y=[1450,1900).
Only Part III question 1 is retained, without student name, identifier or
grading overlay. Pixel intensities have not been corrected or annotated.

The marked answer is -0.2. A shadow across row 9 (and near row 5 in 1048)
previously made blank cells uncertain. Tests also place a second mark or faint
erasure on copies of these pixels and require the answer to remain unresolved.

Run: `python -m unittest discover -s tests -p test_part3_shadow.py -v`
