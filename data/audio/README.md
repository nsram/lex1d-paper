# Audio data

Put `dharini-abhogi.txt.gz` in this folder, so the path is `data/audio/dharini-abhogi.txt.gz`.
The run scripts read it from here and nowhere else. The file is about 37 MB, under GitHub's 100 MB
per-file limit, so it can be committed as is.

- File: `dharini-abhogi.txt.gz` (36,885,053 bytes), SHA-256 of the `.gz`:
  `3576f34420b749818b1897971692354fa6ded5af23a456ffba1965e1d8725c27`
- Contents: 8,168,256 audio samples, one per line with 8 decimals (7,295,677 distinct values), from a
  recording of the varnam "Dharini" in raga Abhogi, gzip-compressed with `gzip -9 -n`.
- SHA-256 of the uncompressed text, checked by `run/data.py` before every run that uses the audio:
  `b19a45a308ba4758d8769b0d71e43ccf7503c0a0182e8d05e3ac5583586b2c3e`

To check the file by hand: `shasum -a 256 dharini-abhogi.txt.gz` (macOS) or
`sha256sum dharini-abhogi.txt.gz` (Linux), and `gunzip -c dharini-abhogi.txt.gz | shasum -a 256`
for the text.

## Source and license

Carnatic Varnam Dataset, by Xavier Serra, Gopala Krishna Koduri, Vignesh Ishwar and Joan Serrà (2025).
doi:[10.34810/DATA2311](https://doi.org/10.34810/DATA2311). Licensed under Creative Commons
Attribution 4.0 International (CC BY 4.0), https://creativecommons.org/licenses/by/4.0/.
The samples were extracted from the dataset's audio recording; nothing else was changed.

This file is covered by CC BY 4.0, not by the repository's MIT license (see the top-level LICENSE).
